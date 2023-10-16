#!/usr/bin/env python3

import sys, os, re, argparse, textwrap
import vcf
import pandas as pd
import pyranges as pr
from prBedparse import make_pyranges
#from intervaltree import IntervalTree

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=textwrap.dedent('''\

Read in VCF and bed, find overlaps based on VCF startpos and direction
Keep in mind that bed is 0 based and VCF is 1 based

        '''))
group = parser.add_argument_group('required arguments')
group.add_argument('bedfile', type=str, help='Bed file')
group.add_argument('vcffile', type=str, help='VCF file')


def vcfType(vcffile):
    '''Try to determine program that was used to create this VCF'''
    # manta gives a lot more information than gridss, so it
    # might be useful to know this ahead of time so we don't have to 
    # do all the work
    # on the other hand, this might lead to different results
    pass

# see https://bioconductor.org/packages/release/bioc/vignettes/StructuralVariantAnnotation/inst/doc/vignettes.html
# todo: make sure we ignore SNPs

def vcfOverlap(bedfile, vcffile):
    bedGeneTree, bedTxTree, bedExonTree = make_pyranges(bedfile)
    bedExonTree = pr.PyRanges()
    isPaired = [] # translocation/deletion mates do not need to get parsed again
    with open(vcffile, 'r') as f:
        reader = vcf.Reader(f)
        for variant in reader:  
            # create a dict of all info in a single line first
            vcfrow = {}
            attribute_dict = vars(variant)
            for attribute, value in attribute_dict.items():
                # keep in mind that ALT, FILTER and samples are lists
                if attribute == 'ALT':
                    if len(value) >1:
                        sys.stderr.write('Complex rearrangement, skipping %s' % value)
                        continue
                    else:
                        ALT = value[0]
                # INFO is a dict; split it
                if attribute == 'INFO':
                    for key, val in value.items():
                        vcfrow['INFO.' + key] = val
                # todo? Split format and sample fields
                else:
                    vcfrow[attribute] = value

            # Now that we have a dict, extract relevant info and do overlaps
            if not isinstance(ALT, (vcf.model._SingleBreakend, vcf.model._Breakend)):
                print(vcfrow['ID'], 'does not look like a BND annotation, skipping')
                continue
            # for every breakend we want to know the local overlap
            # Note: we're trying to be clever here and only create exon trees if we need them
            # so bedExonTree gets larger during the run (but will never come close to a full genome
            # version)
            localBND = breakPoint(vcfrow, bedTxTree, bedExonTree)
            if not localBND.newExons.empty:
                bedExonTree = pr.concat([bedExonTree, localBND.newExons])

            if isinstance(ALT, (vcf.model._SingleBreakend)):
                if localBND.location == 'INTERGENIC':
                    print(vcfrow['ID'], 'Single breakpoint is intergenic')
                else:
                    print(vcfrow['ID'], 'Single breakpoint in', localBND.location, 
                          'of', localBND.geneList)
            elif isinstance(ALT, (vcf.model._Breakend)):
                if vcfrow['ID'] in isPaired:
                    print(vcfrow['ID'], 'part of a previous pair, skipping')
                    continue
                isPaired.append(vcfrow['INFO.MATEID'][0])
                # skip partner if it's in a non-genome contig
                if ALT.withinMainAssembly:
                    remoteBND = breakPoint(vcfrow, bedTxTree, bedExonTree, alt=ALT)
                    if not remoteBND.newExons.empty:
                        bedExonTree = pr.concat([bedExonTree, remoteBND.newExons])
                    if localBND.location == remoteBND.location == 'INTERGENIC':
                        print(vcfrow['ID'], 'both breakpoints are intergenic')
                    elif localBND.location == 'INTERGENIC':
                        print(vcfrow['ID'], 'local side is intergenic, remote breakpoint in', remoteBND.location, 
                              'of', remoteBND.geneList)
                    elif remoteBND.location == 'INTERGENIC':
                        print(vcfrow['ID'], 'remote side is intergenic, local breakpoint in', localBND.location, 
                              'of', localBND.geneList)
                    else:
                        status = pairInfo(localBND, remoteBND, bedExonTree)
                        print(vcfrow['ID'], status)
                else:
                    # we can't say anything about the remote breakend
                    if localBND.location == 'INTERGENIC':
                        print(vcfrow['ID'], 'remote breakpoint not in reference, local breakpoint is intergenic')
                    else:
                        print(vcfrow['ID'], 'remote breakpoint not in reference, local breakpoint in', localBND.location, 
                              'of', localBND.geneList)


def makeExonRanges(transcripts, bedExonTree):
    '''Create an exon pyranges object from a transcript pyranges object if the transcript 
       is not already in bedExonTree'''
    exon_data = []
    txIntrons = dict()
    if bedExonTree.empty:
        newtx = transcripts.df
    else:
        newtx = transcripts.df[~transcripts.df['Name'].isin(bedExonTree.df['Name'])]

    for index, row in newtx.iterrows():
        prevstart = None
        Name = row['Name']
        chrom = row['Chromosome']
        chrstart = int(row['Start'])
        starts = [chrstart+int(start) for start in row['chromStarts'].rstrip(',').split(',')]
        bsizes = [int(bsize) for bsize in row['blockSizes'].rstrip(',').split(',')]
        exonframes = [int(exonframe) for exonframe in row['exonFrames'].rstrip(',').split(',')]

        # Create rows for each exon
        for start, bsize, exonframe in zip(starts, bsizes, exonframes):
            exon_data.append([row['Name'], row['geneName'], row['Chromosome'], start, start+bsize, row['Strand'], exonframe])
#            if prevstart:
#                introncount += 1
#                introns.append([row['Name'], row['geneName'], row['Chromosome'], prevstart, start, introncount])
#            prevstart = start + bsize
#        intron_df = pd.DataFrame(introns, columns=['Name', 'geneName', 'Chromosome', 'Start', 'End', 'IntronNumber'])
#        txIntrons[row['Name']] = pr.PyRanges(intron_df)

    # Create a new DataFrame from the transformed data
    exon_df = pd.DataFrame(exon_data, columns=['Name', 'geneName', 'Chromosome', 'Start', 'End', 'Strand', 'Frame'])
    exonRanges = pr.PyRanges(exon_df)
    return exonRanges # , txIntrons



class breakPoint:
    def __init__(self, vcfrow, bedTxTree, bedExonTree, alt=False):
        '''Do overlaps with a single breakpoint. If a gene overlap is found, check exons to see
        if the overlap occurs in an intron or (coding) exon'''
        self.location = 'INTERGENIC'
        self.geneList = ''
        self.newExons = pr.PyRanges()
        if alt == False:
            self.ID = vcfrow['ID']
            self.CHROM = vcfrow['CHROM']
            self.POS = vcfrow['POS']-1 # go to zero-based
        else:
            self.ID = vcfrow['INFO.MATEID'][0]
            pattern = r'[\]\[]?(\w+):(\d+)' 
            match = re.search(pattern, str(alt))
            if match:
                self.CHROM = match.group(1)
                self.POS = int(match.group(2))
            else:
                print(f'WARNING, do not understand {str(alt)}, skipping mate analysis', file=sys.stderr)
                self.transcripts = pr.PyRanges()
                return
        # add chr to standard chromosomes if necessary
        if self.CHROM.isdigit() or self.CHROM == 'M':
            self.CHROM = 'chr'+self.CHROM

        # pyranges is open ended, meaning the end coordinate is not included in the range
        self.transcripts = bedTxTree[self.CHROM, self.POS:self.POS+1]
        if not self.transcripts.empty:
            self.newExons = makeExonRanges(self.transcripts, bedExonTree)
            self.checkExons(pr.concat([bedExonTree, self.newExons]))
    def checkExons(self, bedExonTree):
        '''Determines if the breakpoing overlaps a coding or noncoding exon. Since this function only gets
           called if a transcript was already found, the default is intron.'''
        # is the breakpoint in an exon?
        self.location = 'INTRON'
        self.exons = bedExonTree[self.CHROM, self.POS:self.POS+1]
        if not self.exons.empty:
            # does it overlap a cds?
            self.transcripts = self.transcripts[self.transcripts.Name.isin(self.exons.df['Name'])]
            inCds = self.transcripts[(self.transcripts.thickStart<= self.POS) & (self.transcripts.thickEnd > self.POS)]
            if inCds.empty:
                self.location = 'NONCODING EXON'
            else:
                self.location = 'CODING EXON'
                self.transcripts = inCds
        self.geneList = ';'.join(self.transcripts.df['geneName'].unique())
        #print(self.ID, self.POS, 'Single breakend found in', self.location, 'of', self.geneList)

def pairInfo(localBND, remoteBND, bedExonTree):
    '''Checks if a fusion gene or intragenic deletion is possible between BND objects'''
    status = 'Unknown'
    if localBND.location == 'INTERGENIC' or remoteBND.location == 'INTERGENIC':
        return False
    # are there any identical transcripts?
    intersection_df = pd.merge(localBND.transcripts.df, remoteBND.transcripts.df, how='inner')
    if intersection_df.empty:
        # TODO: check for gene names as well, since two different tx of the same gene can be affected
        geneString1 = ';'.join(localBND.transcripts.df['geneName'].unique())
        geneString2 = ';'.join(remoteBND.transcripts.df['geneName'].unique())
        status = 'Paired breakpoints located in different genes. Local: ' + geneString1 + ' Remote: ' + geneString2
        return status
    #if localBND.transcripts.df.equals(remoteBND.transcripts.df):
    else:
        # TODO: reduce this to shared tx only
        # same gene(s)
        # subtract self.exons from the contained ones
        containedExons = bedExonTree[localBND.CHROM, localBND.POS:remoteBND.POS].subtract(localBND.exons)
        geneList = localBND.transcripts.df['geneName'].unique()
        geneString = ';'.join(geneList)
        if localBND.location == remoteBND.location == 'INTRON':
            if containedExons.empty:
                status = 'Paired breakpoints are in an intron of the same gene(s): ' + geneString
            else:
                geneList = containedExons.df['geneName'].unique()
                geneString = ';'.join(geneList)
                # noncoding exons are -1, coding are 0,1,2
                if (containedExons.df['Frame'] >= 0).any():
                    status = 'Paired breakpoints delete at least one CODING exon of gene(s): ' + geneString
                else: 
                    status = 'Paired breakpoints delete at least one noncoding exon of gene(s): ' + geneString
        elif localBND.location == remoteBND.location == 'CODING EXON': 
            if containedExons.empty: 
                status = 'Paired breakpoints are in the same CODING exon of the same gene(s): ' + geneString
            else: 
                status = 'Paired breakpoints in different coding exons may create a new protein of the same gene(s): ' + geneString
        else: 
            if containedExons.empty: 
                status = 'Paired breakpoints are in the same exon of the same gene(s): ' + geneString #, localBND.location, remoteBND.location)
            else: 
                status = 'Paired breakpoints affect at least one exon of gene(s): ' + geneString  
                print(localBND.location, remoteBND.location)

#    else:
#        # are there any identical transcripts?
#        intersection_df = pd.merge(localBND.transcripts.df, remoteBND.transcripts.df, how='inner')
#        if intersection_df.empty:
#            # TODO: check for gene names as well, since two different tx of the same gene can be affected
#            geneString1 = ';'.join(localBND.transcripts.df['geneName'].unique())
#            geneString2 = ';'.join(remoteBND.transcripts.df['geneName'].unique())
#            status = 'Paired breakpoints located in different genes. Local: ' + geneString1 + ' Remote: ' + geneString2
        # skip finding fusion genes, there are annotators for that
        #fusionObjects = fusion_possible(self.ALT, self.transcripts, self.mateTranscripts)
        #for f in fusionObjects:
        #    print(f.geneCombis)
    return status


def fusion_possible(ALT, txRangesLocal, txRangesRemote):
    '''
    Takes ALT Breakend object and local and remote overlapping genes.
    Returns a list with fusion objects
      
             orientations are booleans, where True means upstream replaced
             and False means downstream replaced
             this means that if there's one True and one False, a fusion gene
             is possible if the strands match
             and if both are True (or False), strands must not match
             see also print(gr.set_intersect(gr2, strandedness="opposite"))
    '''
    if txRangesLocal.empty or txRangesRemote.empty:
        return False 
    # it is possible that the transcripts belong to multiple genes on different strands
    fusionObjects = []
    if ALT.orientation == ALT.remoteOrientation:
        fObj = fusionObject(txRangesLocal[txRangesLocal.Strand == '+'], txRangesRemote[txRangesRemote.Strand == '-'])
        if fObj.geneCombis != '':
            fusionObjects.append(fObj)
        fObj = fusionObject(txRangesLocal[txRangesLocal.Strand == '-'], txRangesRemote[txRangesRemote.Strand == '+'])
        if fObj.geneCombis != '':
            fusionObjects.append(fObj)
    else:
        fObj = fusionObject(txRangesLocal[txRangesLocal.Strand == '+'], txRangesRemote[txRangesRemote.Strand == '+'])
        if fObj is not None:
            fusionObjects.append(fObj)
        fObj = fusionObject(txRangesLocal[txRangesLocal.Strand == '-'], txRangesRemote[txRangesRemote.Strand == '-'])
        if fObj is not None:
            fusionObjects.append(fObj)
    return fusionObjects


class fusionObject():
    '''Fusion object'''
    def __init__(self, txLocal, txRemote):
        self.geneCombis = ''
        if len(txLocal) == 0 or len(txRemote)==0:
            return None
        txLocalGenes = txLocal.df['geneName'].unique()
        txRemoteGenes = txRemote.df['geneName'].unique()
        self.geneCombis = 'fusion genes possible'
        for gene in txLocalGenes:
            for rgene in txRemoteGenes:
                self.geneCombis += f' between local {gene} and remote {rgene};'
        




if __name__ == "__main__":
    if len(sys.argv)==1:
        parser.print_help()
        sys.exit(1)
    args = parser.parse_args()
    vcfOverlap(args.bedfile, args.vcffile)


