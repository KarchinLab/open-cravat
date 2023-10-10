#!/usr/bin/env python3

import sys, os, re, argparse, textwrap
import vcf
import pyranges
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
            print(vcfrow['ID'])
            if isinstance(ALT, (vcf.model._SingleBreakend)):
                # insertion, small deletion - we only care about this one location
                inExon, transcripts = annotOverlap(txRanges=bedTxTree, exonRanges=bedExonTree, 
                    chrom=vcfrow['CHROM'], pos=vcfrow['POS'])
                if transcripts:
                    geneList = ';'.join(transcripts.df['geneName'].unique())
                    print('Single breakend found in:', geneList)
            elif isinstance(ALT, (vcf.model._Breakend)):
                #print('YO', vcfrow['ID'], vcfrow['INFO.MATEID'][0], isPaired)
                if vcfrow['ID'] in isPaired:
                    print('Skipping')
                    continue
                isPaired.append(vcfrow['INFO.MATEID'][0])
                # paired breakend, now we care about both sides and their directions
                print('here', ALT.orientation, 'there', ALT.remoteOrientation)
                inExon, transcripts = annotOverlap(txRanges=bedTxTree, exonRanges=bedExonTree, 
                    chrom=vcfrow['CHROM'], pos=vcfrow['POS'])
                # skip partner if it's in a non-genome contig
                if ALT.withinMainAssembly:
                    # note: may also be able to get this from MATEPOS in INFO
                    pattern = r'[\]\[]?(\w+):(\d+)' 
                    match = re.search(pattern, str(ALT))
                    if not match:
                        print(f'WARNING, do not understand {str(ALT)}, skipping mate analysis', file=sys.stderr)
                        continue
                    matechrom = match.group(1)
                    matepos = int(match.group(2))
                    if matechrom.isdigit() or matechrom == 'M':
                        matechrom = 'chr'+matechrom
                    inExon, mateTranscripts = annotOverlap(txRanges=bedTxTree, exonRanges=bedExonTree, 
                        chrom=matechrom, pos=matepos)
                    if transcripts is not False and mateTranscripts is not False:
                        if transcripts.df.equals(mateTranscripts.df):
                            geneList = ';'.join(transcripts.df['geneName'].unique())
                            print('Paired breakpoints are in the same gene(s):', geneList)
                        else:
                            print('Paired breakpoints not in same gene.')
                            fusionObjects = fusion_possible(ALT, transcripts, mateTranscripts)
                            for f in fusionObjects:
                                print(f.geneCombis)
                    elif transcripts is not False:
                        geneList = ';'.join(transcripts.df['geneName'].unique())
                        print('Local breakpoint in:', geneList)
                    elif mateTranscripts is not False:
                        geneList = ';'.join(mateTranscripts.df['geneName'].unique())
                        print('Mate breakpoint in:', geneList)
                else:
                    if len(transcripts) > 0:
                        geneList = ';'.join(transcripts.df['geneName'].unique())
                        print('Breakend found in:', geneList)
            else:
                # sanity check - make sure all input vcfs are either one
                print('WARNING, do not understand SV annotation', vcfrow, 'AND', str(ALT))


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
    if len(txRangesLocal) == 0 or len(txRangesRemote)==0:
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
        


# TODO: list type of gene.  e.g ENST00000454360.1 is a pseudogene
def annotOverlap(txRanges, exonRanges, chrom, pos):
    '''find overlaps in transcript and exon pyranges object. Returns True if an exon pyrange 
    was found, and the transcript dataframe'''
    # vcf is one based, pyranges is zero based
    transcripts = txRanges[chrom, pos-1:pos]
    # even though we're only checking 1 nt, we can still hit different genes
    # an example is ENSG00000285314 and LZTR1, where the former is a lncRNA of the latter
    # with mostly identical exons
    if len(transcripts) > 0:
        # note: we could check exons first but that is a much larger dataset
        exons = exonRanges[chrom, pos-1:pos]
        if len(exons) > 0:
            genes = exons.df['geneName'].unique()
            if len(genes) > 1:
                print('TODO: overlapping more than one gene, please check', pos)
            else:
                # return only the transcripts that contain this exon
                return(True, transcripts[transcripts.Name.isin(exons.df['Name'])])
        else:
            return(False, transcripts)
    return(False, False) # todo: this ain't pretty




#def oldoverlap():
#            if variant.ID in is_paired:
#                 # we already have info for this variant (this may not remain true, deal with later)
#                 continue
##            if variant['INFO']['SVTYPE'] != 'BND'
#            hasMate = add_mateinfo(variant, bedTxTree)
#            brokenGenes, deletedGenes = geneOverlap(variant, bedTxTree)
#            if brokenGenes == False:
#                # chromosome not in bed file, we can't say anything about this variant
#                continue
#            if hasMate:
#                is_paired.append(variant.INFO['MATEID'])
#                print(
#                    f"{variant.SVTYPE}\t"
#                    f"{variant.ID}\t"
#                    f"{variant.INFO['MATEID']}\t"
#                    f"{variant.CHROM}\t"
#                    f"{variant.INFO['MATECHROM']}\t"
#                    f"{variant.POS}\t"
#                    f"{variant.INFO['MATEPOS']}\t",
#                    end=''
#                )
#                if variant.SVTYPE == 'SVDEL':
#                    print(
#                        f"{variant.INFO['MATEPOS'] - variant.POS}\t"
#                        f"{deletedGenes}\t"
#                        f"{brokenGenes}"
#                    )
#                elif variant.SVTYPE in ['BND', 'TRANSLOC']:
#                    print(
#                        f"NA\t"
#                        f"NA\t"
#                        f"{brokenGenes}"
#                    )
#                else:
#                    print('NOT SURE THIS IS RIGHT')
#            else:    
#                # Insertion
#                print(
#                    f"{variant.SVTYPE}\t"
#                    f"{variant.ID}\t"
#                    f"NA\t"
#                    f"{variant.CHROM}\t"
#                    f"NA\t"
#                    f"{variant.POS}\t"
#                    f"NA\t",
#                    f"NA\t"
#                    f"NA\t"
#                    f"{brokenGenes}"
#                )
#                
# gridss within chromosome deletions can be inferred from the ALT field
# and they have a MATEID
# manta actually calls DEL

def geneOverlap(variant, bedTxTree):
    '''Find interrupted and deleted genes for the input variant and a gene startpos-endpos intervaltree'''
    if not variant.CHROM in bedTxTree:
        sys.stderr.write(f'WARNING, chromosome {variant.CHROM} not found in bed file\n')
        return False, False
    txTree = bedTxTree[variant.CHROM]
    interrupted_genes = txTree[variant.POS]
    deleted_genes = 'None'
    if variant.SVTYPE == 'SVINS':
        pass
    elif variant.SVTYPE == 'SVDEL':
        interrupted_genes.update(txTree[variant.INFO['MATEPOS']])
        # check if the deleted fragment contains complete genes
        start, end = sorted([variant.POS, variant.INFO['MATEPOS']])
        contained_genes = txTree[start:end].difference_update(interrupted_genes)
        if contained_genes:
            deleted_genes = ';'.join([x.data for x in contained_genes])
    elif variant.SVTYPE == 'TRANSLOC':
        # the mate is on a different chromosome
        if not 'MATECHROM' in variant.INFO:
            sys.stderr.write(f'{variant.ID} {variant.INFO}\n')
            sys.exit()
        chrom = variant.INFO['MATECHROM']
        if chrom in bedTxTree:
            txTree = bedTxTree[chrom]
            interrupted_genes.update(txTree[variant.INFO['MATEPOS']])
    broken_genes = ';'.join([x.data for x in interrupted_genes]) if interrupted_genes else 'None'
    return broken_genes, deleted_genes
    
def add_mateinfo(variant, bedTxTree):
    '''parse ALT field if the variant has a mate and add to the variant INFO field'''
    if not 'MATEID' in variant.INFO:
        variant.SVTYPE = 'BND'
        return False
    variant.INFO['MATEID'] = variant.INFO['MATEID'][0]
    # Find chr and coordinate in ALT field
    # WARNING we must have chr in the chrom ID
    pattern = r'(chr\w+):(\d+)'
    match = re.search(pattern, str(variant.ALT[0]))
    if match:
        variant.INFO['MATECHROM'] = match.group(1)
        variant.INFO['MATEPOS'] = int(match.group(2))
        # it's only a deletion when the first mate has [ brackets,
        # and the ref allele comes before those brackets
        # and the chromosome is the same
        delpattern = f".\]{variant.CHROM}:{variant.INFO['MATEPOS']}\]"
        delmatch = re.match(delpattern, str(variant.ALT[0]))
        if delmatch:
        # gridss calls all SVTYPEs BND, overwrite. TODO: for manta, check if the type agrees
            variant.SVTYPE = 'SVDEL'
        elif variant.CHROM == variant.INFO['MATECHROM']:
            variant.SVTYPE = 'SAMECHR_TRANSLOC'        # TODO: replace this back to BND
        # default is translocation
        else:
            variant.SVTYPE = 'TRANSLOC' # should be BND, TODO replace later
        return True
    else:
        # small insertion
        pattern = r'^\.*[ACTGN]+\.*$'
        if re.match(pattern, str(variant.ALT[0])):
            variant.SVTYPE == 'SVINS'
        else:
            sys.stderr.print(f'WARNING, do not understand {variant.ID} {variant.ALT}\n')
        return False


# note: https://gatk.broadinstitute.org/hc/en-us/articles/5334587352219-How-to-interpret-SV-VCFs
# https://samtools.github.io/hts-specs/VCFv4.4.pdf p22
#REF ALT Meaning
#s t[p[ piece extending to the right of p is joined after t
#s t]p] reverse comp piece extending left of p is joined after t
#s ]p]t piece extending to the left of p is joined before t
#s [p[t reverse comp piece extending right of p is joined before t



if __name__ == "__main__":
    if len(sys.argv)==1:
        parser.print_help()
        sys.exit(1)
    args = parser.parse_args()
    vcfOverlap(args.bedfile, args.vcffile)


