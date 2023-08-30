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
                 print('WARNING, chromosome not found in bed file:', variant.CHROM)
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
                 print('Variant:',variant.POS, variant.CHROM, variant.ALT, variant.REF)
                 [print(f'Gene: {x.begin}, {x.end}, {x.data}') for x in txTree[variant.POS]]
                 if exonTree[variant.POS]:
                     [print(f'\tExon: {x.begin}, {x.end}, {x.data}') for x in exonTree[variant.POS]]
			
#             print(sorted(bedIntervalTreesByChrom[variant.CHROM][variant.POS]]))
#             print(variant.INFO, variant.var_type)


if __name__ == "__main__":
    if len(sys.argv)==1:
        parser.print_help()
        sys.exit(1)
    args = parser.parse_args()
    vcfOverlap(args.bedfile, args.vcffile)


