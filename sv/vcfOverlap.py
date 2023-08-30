#!/usr/bin/env python3

import sys, os, re, argparse, textwrap
import vcf
from bedparse import chromIntervalTreesFromBed
from intervaltree import IntervalTree
#import pickle

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=textwrap.dedent('''\

Read in VCF and bed, find overlaps based on VCF startpos
Keep in mind that bed is 0 based and VCF is 1 based

        '''))
group = parser.add_argument_group('required arguments')
group.add_argument('vcffile', type=str, help='VCF file')
group.add_argument('bedfile', type=str, help='Bed file')

# TODO: deal with chr vs nonchr

is_paired = []
def vcfOverlap(bedfile, vcffile):
    bedExonTree, bedTxTree = chromIntervalTreesFromBed(bedfile)
#    with open('bedfile.pkl', 'wb') as pfile:
#        pickle.dump([bedExonTree, bedTxTree], pfile)
#    with open('bedfile.pkl', 'rb') as pfile:
#        [bedExonTree, bedTxTree] = pickle.load(pfile)
    chroms = bedTxTree.keys()
    # attempt to speed up lookups (VCF is generally in chr order)
    curChrom, exonTree, txTree = None, None, None
    with open(vcffile, 'r') as f:
        reader = vcf.Reader(f)
        for variant in reader:
             if not variant.CHROM in chroms:
                 print('WARNING, chromosome not found in bed file:', variant.CHROM, file=sys.stderr)
                 continue
             if variant.CHROM != curChrom:
                 exonTree = bedExonTree[variant.CHROM]
                 txTree = bedTxTree[variant.CHROM]
                 curChrom = variant.CHROM
                 print(curChrom)
             # the loop below first prints all genes that are overlapped 
             # and then all the exons (with their transcript IDs). 
             # We might want to return a dict of exontrees from bedparse with gene ID as keys instead.
             if txTree[variant.POS]:
                 print_info(variant, txTree, exonTree)

def print_info(variant, txTree, exonTree):
     '''Extract information from variant and overlapping genes for printing'''
     # if this variant has a mate we must add its info
     # currently we only use info we extract from the variant, and mark the mate ID
     # for skipping once we encounter it
     # TODO: see if ALT ever has more entries
     print('Variant:', variant.ID, variant.POS, variant.CHROM, variant.ALT[0], variant.REF)
     # get all overlapping genes
     [print(f'Gene: {x.begin}, {x.end}, {x.data}') for x in txTree[variant.POS]]
     mate = mateinfo(variant)
     if mate: # and mate.POS in txTree:
         [print(f'Gene: {x.begin}, {x.end}, {x.data} for mate {mate.ID[0]}') for x in txTree[mate.POS]]
     # get all overlapping exons
     if exonTree[variant.POS]:
         [print(f'\tExon: {x.begin}, {x.end}, {x.data}') for x in exonTree[variant.POS]]
 # with translocations and larger deletions we can get information from the ALT field
 # this is important with GRIDSS because all its SVTYPE are BND (Manta has DEL, etc)

class mateObject():
    '''mate information extraced from variant'''
    def __init__(self, name, pos, svtype):
        self.ID = name
        self.POS = pos
        self.SVTYPE = svtype


# NOTE currently only returns True if the mate is a deletion with the other end downstream
def mateinfo(variant):
    '''get type of SV from ALT field info if the variant has a mate'''
    if not 'MATEID' in variant.INFO:
        return False
    # this regexp captures the chromosome position
    simple_del = f"{variant.REF}\\[{variant.CHROM}:(\\d+)\\["
    match = re.match(simple_del, str(variant.ALT[0]))
    if match:
        chrom_coord = int(match.group(1))
        mate = mateObject(variant.INFO['MATEID'], chrom_coord, 'DEL')
        return mate
    return False
    


# note: https://gatk.broadinstitute.org/hc/en-us/articles/5334587352219-How-to-interpret-SV-VCFs
# https://samtools.github.io/hts-specs/VCFv4.4.pdf p22
#REF ALT Meaning
#s t[p[ piece extending to the right of p is joined after t
#s t]p] reverse comp piece extending left of p is joined after t
#s ]p]t piece extending to the left of p is joined before t
#s [p[t reverse comp piece extending right of p is joined before t

			
#             print(sorted(bedIntervalTreesByChrom[variant.CHROM][variant.POS]]))
#             print(variant.INFO, variant.var_type)


if __name__ == "__main__":
    if len(sys.argv)==1:
        parser.print_help()
        sys.exit(1)
    args = parser.parse_args()
    vcfOverlap(args.bedfile, args.vcffile)


