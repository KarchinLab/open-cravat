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
    # header
    print('SVTYPE\tID\tMATEID\tCHROM\tPOS1\tPOS2\tSIZE\tDEL_GENES\tBROKEN_GENES')
    with open(vcffile, 'r') as f:
        reader = vcf.Reader(f)
        for variant in reader:
#             if variant.ID.endswith('b'):
#                 print(variant.ID, variant.REF, variant.ALT[0])
#             continue
             if variant.ID in is_paired:
                 # we already have info for this variant (this may not remain true, deal with later)
                 continue
             print(variant.ID)
             if not variant.CHROM in chroms:
                 print('WARNING, chromosome not found in bed file:', variant.CHROM, file=sys.stderr)
                 continue
             if variant.CHROM != curChrom:
                 exonTree = bedExonTree[variant.CHROM]
                 txTree = bedTxTree[variant.CHROM]
                 curChrom = variant.CHROM
                 print(curChrom)
             # the below first prints all genes that are overlapped 
             # and then all the exons (with their transcript IDs). 
             # We might want to return a dict of exontrees from bedparse with gene ID as keys instead.
             mate_id = print_info(variant, txTree, exonTree)
             if mate_id:
                 is_paired.append(mate_id)

# TODO: see if ALT and ID ever have more entries
# ALT can have multiple entries in complex rearrangements, see p24 in
# https://samtools.github.io/hts-specs/VCFv4.4.pdf
# we might want to skip those
def print_info(variant, txTree, exonTree):
    '''Extract information from variant and overlapping genes for printing. Returns mate.ID if one is found'''
    # if this variant has a mate we must add its info
    # currently we only use info we extract from the variant, and mark the mate ID
    # for skipping once we encounter it
    variant.interrupted_genes = IntervalTree()
    variant.interrupted_genes.update(txTree[variant.POS])
    if 'MATEID' in variant.INFO:
        mate = mateinfo(variant, txTree)
        print(f"{mate.SVTYPE}\t{variant.ID}\t{mate.ID}\t{variant.CHROM}\t{variant.POS}\t{mate.POS}", end='')
        if mate.SVTYPE == 'SVDEL':
            print(f"\t{mate.POS-variant.POS}\t{mate.del_genes}\t{mate.broken_genes}")
        else:
            print('')
        return mate.ID
    else:
        # small insertion
        pattern = r'^\.*[ACTGN]+\.*$'
        if re.match(pattern, str(variant.ALT[0])):
            interrupted_genes = ';'.join([x.data for x in variant.interrupted_genes])
            print(f"SVINS\t{variant.ID}\tNA\t{variant.CHROM}\t{variant.POS}\tNA", end='')
            print(f"\tNA\tNA\t{interrupted_genes}")
        else:
            sys.stderr.print('WARNING, do not understand', variant.ID, variant.ALT)
            return False
    return False    
     
#    if exonTree[variant.POS]:
#         [print(f'\tExon: {x.begin}, {x.end}, {x.data}') for x in exonTree[variant.POS]]

class mateObject():
    '''mate information extraced from variant'''
    def __init__(self, name, chrom, coord, txTree, allele):
        self.ID = name[0]
        self.CHROM = chrom
        self.POS = coord
        self.SVTYPE = allele
        self.interrupted_genes = txTree[self.POS]
    def add_deltype(self, variant, txTree):
        self.SVTYPE = 'SVDEL'
        # check for region overlaps
        start = min(variant.POS, self.POS)
        end = max(variant.POS, self.POS)
        self.deleted_genes = txTree[start:end]
        self.deleted_genes.difference_update(self.interrupted_genes)
        if variant.interrupted_genes == self.interrupted_genes:
            # the deletion is fully inside one (or several overlapping) gene(s)
            pass
        else:
            self.interrupted_genes.update(variant.interrupted_genes)
            self.del_genes = ';'.join([x.data for x in self.deleted_genes])
        if not self.del_genes:
            self.del_genes = 'None'
        self.broken_genes = ';'.join([x.data for x in self.interrupted_genes])
        if not self.broken_genes:
            self.broken_genes = 'None'    


def mateinfo(variant, txTree):
    '''get type of SV from ALT field info if the variant has a mate'''
    # Find chr and coordinate in ALT field WARNING we must have chr in the chrom ID
    pattern = r'(chr\w+):(\d+)'
    match = re.search(pattern, str(variant.ALT[0]))
    if match:
        chrom = match.group(1)
        coord = int(match.group(2))
    else:
        print("No match found, cannot make MATE.", variant.ALT)
        sys.exit()
        return False
    mate = mateObject(variant.INFO['MATEID'], chrom, coord, txTree, variant.ALT[0])
    # NOTE must add other types
    add_info_if_del(variant, mate, txTree)
    return mate

# could add this as a mate.function()
# simplified this from an earlier version: consider this a DEL if
# there is [chr:pos[ or ]chr:pos]. TODO: figure out what every combination is
def add_info_if_del(variant, mate, txTree):
    '''See if the variant and mate are a deletion on a single chromosome'''
    # we're currently ignoring any inserts, which are strings before [ or after ]
#    simple_del = f"{variant.REF}\\[{variant.CHROM}:{mate.POS}\\["
    pattern = f"[\\[\\]]{variant.CHROM}:{mate.POS}[\\[\\]]"
    match = re.search(pattern, str(variant.ALT[0]))
    if match:
        mate.add_deltype(variant, txTree)
        return True
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


