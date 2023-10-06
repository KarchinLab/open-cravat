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
# TODO  bed is 0 based and VCF is 1 based

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
    bedExonTree, bedTxTree = chromIntervalTreesFromBed(bedfile)
    is_paired = [] # translocation/deletion mates do not need to get parsed again
    # header
    print('SVTYPE\tID\tMATEID\tCHROM\tMATECHROM\tPOS1\tPOS2\tSIZE\tDEL_GENES\tBROKEN_GENES')
    with open(vcffile, 'r') as f:
        reader = vcf.Reader(f)
        for variant in reader:
            if variant.ID in is_paired:
                 # we already have info for this variant (this may not remain true, deal with later)
                 continue
#            if variant['INFO']['SVTYPE'] != 'BND'
            hasMate = add_mateinfo(variant, bedTxTree)
            brokenGenes, deletedGenes = geneOverlap(variant, bedTxTree)
            if brokenGenes == False:
                # chromosome not in bed file, we can't say anything about this variant
                continue
            if hasMate:
                is_paired.append(variant.INFO['MATEID'])
                print(
                    f"{variant.SVTYPE}\t"
                    f"{variant.ID}\t"
                    f"{variant.INFO['MATEID']}\t"
                    f"{variant.CHROM}\t"
                    f"{variant.INFO['MATECHROM']}\t"
                    f"{variant.POS}\t"
                    f"{variant.INFO['MATEPOS']}\t",
                    end=''
                )
                if variant.SVTYPE == 'SVDEL':
                    print(
                        f"{variant.INFO['MATEPOS'] - variant.POS}\t"
                        f"{deletedGenes}\t"
                        f"{brokenGenes}"
                    )
                elif variant.SVTYPE in ['BND', 'TRANSLOC']:
                    print(
                        f"NA\t"
                        f"NA\t"
                        f"{brokenGenes}"
                    )
                else:
                    print('NOT SURE THIS IS RIGHT')
            else:    
                # Insertion
                print(
                    f"{variant.SVTYPE}\t"
                    f"{variant.ID}\t"
                    f"NA\t"
                    f"{variant.CHROM}\t"
                    f"NA\t"
                    f"{variant.POS}\t"
                    f"NA\t",
                    f"NA\t"
                    f"NA\t"
                    f"{brokenGenes}"
                )
                
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
            variant.SVTYPE = 'SAMECHR_TRANSLOC'	# TODO: replace this back to BND
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


