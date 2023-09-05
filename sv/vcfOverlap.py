#!/usr/bin/env python3

import sys, os, re, argparse, textwrap
import vcf
from bedparse import chromIntervalTreesFromBed
from intervaltree import IntervalTree

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=textwrap.dedent('''\

Read in VCF and bed, find overlaps based on VCF startpos
Keep in mind that bed is 0 based and VCF is 1 based

        '''))
group = parser.add_argument_group('required arguments')
group.add_argument('bedfile', type=str, help='Bed file')
group.add_argument('vcffile', type=str, help='VCF file')

# TODO: deal with chr vs nonchr

is_paired = []
def vcfOverlap(bedfile, vcffile):
    bedExonTree, bedTxTree = chromIntervalTreesFromBed(bedfile)
    chroms = bedTxTree.keys()
    # attempt to speed up lookups (VCF is generally in chr order)
    curChrom, exonTree, txTree = None, None, None
    # header
    print('SVTYPE\tID\tMATEID\tCHROM\tMATECHROM\tPOS1\tPOS2\tSIZE\tDEL_GENES\tBROKEN_GENES')
    with open(vcffile, 'r') as f:
        reader = vcf.Reader(f)
        for variant in reader:
#             if variant.ID.endswith('b'):
#                 print(variant.ID, variant.REF, variant.ALT[0])
#             continue
             if variant.ID in is_paired:
                 # we already have info for this variant (this may not remain true, deal with later)
                 continue
             if not variant.CHROM in chroms:
                 sys.stderr.write('WARNING, chromosome not found in bed file:', variant.CHROM)
                 continue
             if variant.CHROM != curChrom:
                 exonTree = bedExonTree[variant.CHROM]
                 txTree = bedTxTree[variant.CHROM]
                 curChrom = variant.CHROM
             mate_id = print_info(variant, txTree, exonTree, bedTxTree)
             if mate_id:
                 is_paired.append(mate_id)

# TODO: see if ALT and ID ever have more entries
# ALT can have multiple entries in complex rearrangements, see p24 in
# https://samtools.github.io/hts-specs/VCFv4.4.pdf
# we might want to skip those
def print_info(variant, txTree, exonTree, bedTxTree):
    '''Extract information from variant and overlapping genes for printing. Returns mate.ID if one is found'''
    # if this variant has a mate we must add its info
    # currently we only use info we extract from the variant, and mark the mate ID
    # for skipping once we encounter it
    variant.interrupted_genes = IntervalTree()
    variant.interrupted_genes.update(txTree[variant.POS])
    if 'MATEID' in variant.INFO:
        mate = mateinfo(variant, txTree, bedTxTree)
        broken_genes = ';'.join([x.data for x in mate.interrupted_genes]) if mate.interrupted_genes else 'None'
        del_genes = ';'.join([x.data for x in mate.deleted_genes]) if mate.deleted_genes else 'None'
        print(f"{mate.SVTYPE}\t{variant.ID}\t{mate.ID}\t{variant.CHROM}\t{mate.CHROM}\t{variant.POS}\t{mate.POS}", end='')
        if mate.SVTYPE == 'SVDEL':
            print(f"\t{mate.POS-variant.POS}\t{del_genes}\t{broken_genes}")
        elif mate.SVTYPE == 'BND':
            print(f"\tNA\tNA\t{broken_genes}")
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
    def __init__(self, name, chrom, coord, bedTxTree, allele):
        self.ID = name[0]
        self.CHROM = chrom
        self.POS = coord
        self.SVTYPE = 'UNKNOWN_'+allele
        self.interrupted_genes = IntervalTree()
        self.deleted_genes = IntervalTree()
        if self.CHROM in bedTxTree:
            txTree = bedTxTree[self.CHROM]
            self.interrupted_genes = txTree[self.POS]
    def is_deletion(self, variant, txTree):
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
    def is_translocation(self):
        self.SVTYPE = 'BND'


# TODO: decide to keep or ditch having txTree separately
# if it's a DEL it's on the same chr, so same bedTxTree[chr] so we wouldn't have to try it
# but if it's a BND we need another bedTxTree[chr] (and test if it exists)
def mateinfo(variant, txTree, bedTxTree):
    '''parse ALT field if the variant has a mate'''
    # Find chr and coordinate in ALT field WARNING we must have chr in the chrom ID
    pattern = r'(chr\w+):(\d+)'
    match = re.search(pattern, str(variant.ALT[0]))
    if match:
        chrom = match.group(1)
        coord = int(match.group(2))
    else:
        sys.stderr.write("WARNING, No match found, cannot make MATE.", variant.ALT)
        return False
    mate = mateObject(variant.INFO['MATEID'], chrom, coord, bedTxTree, str(variant.ALT[0]))

    ## DELETION ##
    # if mate and variant are on the same chromosome, this is a deletion
    # simplified this from an earlier version: consider this a DEL if
    # there is [chr:pos[ or ]chr:pos]. TODO: figure out what every combination is
    pattern = f"[\\[\\]]{variant.CHROM}:{mate.POS}[\\[\\]]"
    match = re.search(pattern, str(variant.ALT[0]))
    if match:
        mate.is_deletion(variant, txTree)
        return mate
    # sanity check
    if mate.CHROM == variant.CHROM:
        sys.stderr.write("Missed something, is this a deletion?", variant.ALT, variant.CHROM, variant.POS)
    ## TRANSLOCATION ##
    # if the chromosome is different this is a translocation
    mate.is_translocation()
    return mate

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


