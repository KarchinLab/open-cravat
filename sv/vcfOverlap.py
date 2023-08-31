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
             if variant.ID in is_paired:
                 # we already have info for this variant (this may not remain true, deal with later)
                 continue
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
                 mate_id = print_info(variant, txTree, exonTree)
                 if mate_id:
                     is_paired.append(mate_id)

# TODO: see if ALT and ID ever have more entries
# SVTYPE ID MATEID CHROM POS1 POS2 SIZE DEL_GENES BROKEN_GENES
def print_info(variant, txTree, exonTree):
    '''Extract information from variant and overlapping genes for printing. Returns mate.ID if one is found'''
    # if this variant has a mate we must add its info
    # currently we only use info we extract from the variant, and mark the mate ID
    # for skipping once we encounter it
    interrupted_genes = IntervalTree()
    interrupted_genes.update(txTree[variant.POS])
#    if not interrupted_genes:
#       return False
    mate = mateinfo(variant, txTree)
    # check exons
    if mate:
        # the mate only removed its own interrupted genes from the deleted set
        mate.deleted_genes.difference_update(interrupted_genes)
        if interrupted_genes == mate.interrupted_genes:
            # the deletion is fully inside one (or several overlapping) gene(s)
            pass
        else:
            interrupted_genes.update(mate.interrupted_genes)
            del_genes = ';'.join([x.data for x in mate.deleted_genes])
            if not del_genes:
                del_genes = 'None'
            broken_genes = ';'.join([x.data for x in interrupted_genes])
            if not broken_genes:
                broken_genes = 'None'
            interr_genes = [(f'{x.data} {variant.CHROM}:{x.begin}-{x.end}') for x in interrupted_genes]
            print(f"{mate.SVTYPE}\t{variant.ID}\t{mate.ID}\t{variant.CHROM}\t{variant.POS}\t{mate.POS}\t", end='')
            print(f"{mate.POS-variant.POS}\t{del_genes}\t{broken_genes}")
            return mate.ID
    else:
        # do other stuff
        pass
    return False    
     
#    if exonTree[variant.POS]:
#         [print(f'\tExon: {x.begin}, {x.end}, {x.data}') for x in exonTree[variant.POS]]

class mateObject():
    '''mate information extraced from variant'''
    def __init__(self, name, startpos, endpos, svtype, txTree):
        self.ID = name[0]
        # NOTE: if this is not a DEL, endpos is not the appropriate name
        self.POS = endpos
        self.SVTYPE = svtype
        # check for overlaps
        self.interrupted_genes = txTree[self.POS]
        if self.SVTYPE == 'DEL':
            # NOTE: we may want to create a DEL object instead
            self.deleted_genes = txTree[startpos:self.POS]
            self.deleted_genes.difference_update(self.interrupted_genes)


# NOTE currently only returns True if the mate is a deletion with the other end downstream
def mateinfo(variant, txTree):
    '''get type of SV from ALT field info if the variant has a mate'''
    if not 'MATEID' in variant.INFO:
        return False
    # this regexp captures the chromosome position
    simple_del = f"{variant.REF}\\[{variant.CHROM}:(\\d+)\\["
    match = re.match(simple_del, str(variant.ALT[0]))
    if match:
        chrom_coord = int(match.group(1))
        mate = mateObject(variant.INFO['MATEID'], variant.POS, chrom_coord, 'DEL', txTree)
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


