#!/usr/bin/env python3

import sys, os, re, argparse, textwrap
import vcf
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
    isPaired = [] # translocation/deletion mates do not need to get parsed again
    # header
#    print('SVTYPE\tID\tMATEID\tCHROM\tMATECHROM\tPOS1\tPOS2\tSIZE\tDEL_GENES\tBROKEN_GENES')
    with open(vcffile, 'r') as f:
        reader = vcf.Reader(f)
        for variant in reader:  
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
            # vcfrow['INFO.MATEID']
            if not isinstance(ALT, (vcf.model._SingleBreakend, vcf.model._Breakend)):
                # sanity check - make sure all input vcfs are either one
                print('WARNING, do not understand SV annotation', vcfrow, 'AND', str(ALT))
                continue
            # for every breakend we want to know the local overlap
            localBND = breakPoint(vcfrow, bedTxTree, bedExonTree)

            if isinstance(ALT, (vcf.model._Breakend)):
                if vcfrow['ID'] in isPaired:
                    print(vcfrow['ID'], 'Skipping')
                    continue
                isPaired.append(vcfrow['INFO.MATEID'][0])
                # skip partner if it's in a non-genome contig
                if ALT.withinMainAssembly:
                    remoteBND = breakPoint(vcfrow, bedTxTree, bedExonTree, alt=ALT)
                    pairInfo(localBND, remoteBND)

class breakPoint:
    def __init__(self, vcfrow, bedTxTree, bedExonTree, alt=False):
        self.location = 'INTERGENIC'
        self.geneList = ''
        if alt == False:
            self.ID = vcfrow['ID']
            self.CHROM = vcfrow['CHROM']
            self.POS = vcfrow['POS']-1 # go to zero-based
        else:
            self.ID = vcfrow['INFO.MATEID']
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
            self.checkExons(bedExonTree)

    def checkExons(self, bedExonTree):
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
            print(self.ID, self.POS, 'Single breakend found in', self.location, 'of', self.geneList)

def pairInfo(localBND, remoteBND):
    '''Checks if a fusion gene or intergenic deletion is possible between BND objects'''
    if localBND.location == 'INTERGENIC' or remoteBND.location == 'INTERGENIC':
        return False
    if localBND.transcripts.df.equals(remoteBND.transcripts.df):
        # same gene(s)
        geneList = ';'.join(localBND.transcripts.df['geneName'].unique())
        print('Paired breakpoints are in the same gene(s):', geneList)
        if localBND.location = remoteBND.location = 'INTRON':
            print('Hm')
        #if localBND.exons.df.equals(remoteBND.exons.df):
        # TODO: see if different exons are overlapped
    else:
        print('Paired breakpoints not in same gene.')
        fusionObjects = fusion_possible(self.ALT, self.transcripts, self.mateTranscripts)
        for f in fusionObjects:
            print(f.geneCombis)
#        elif not self.transcripts.empty:
#            geneList =: ';'.join(self.transcripts.df['geneName'].unique())
#            print('Local breakpoint in:', geneList)


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


