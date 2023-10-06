#!/usr/bin/env python3

import sys, os, re, argparse, textwrap
import pyranges as pr
import pandas as pd

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=textwrap.dedent('''\

Turn UCSC's gencode bed file into pyranges
This bed file has several extra fields, one of which contains a gene name.

        '''))
group = parser.add_argument_group('required arguments')
group.add_argument('bedfile', type=str, help='Input bed file')


def make_pyranges(bedfile):
    '''Turn the gencode bed file into three pyranges: gene, transcript, and exon'''
    # read the gencode bed file in as a dataframe
    # use bigBedInfo gencodeV43.bed to get column names
    names = ['Chromosome', 'Start', 'End', 'Name', 'score', 'Strand', 'thickStart', 'thickEnd', 'reserved',
             'blockCount', 'blockSizes', 'chromStarts', 'name2', 'cdsStartStat', 'cdsEndStat', 'exonFrames',
             'type', 'geneName', 'geneName2', 'geneType', 'transcriptClass', 'source', 'transcriptType', 'tag',
             'level', 'tier', 'rank']
    df = pd.read_csv(bedfile, header=None, names=names, sep="\t")
    transcriptRanges = pr.PyRanges(df)
    # a less bulky transcript ranges could be created like this
    #txRanges = pr.PyRanges(df[['Chromosome', 'Start', 'End', 'Name', 'Strand', 'thickStart', 'thickEnd',
    #                         'blockSizes', 'chromStarts', 'cdsStartStat', 'cdsEndStat', 'exonFrames', 'geneName' ]])
    
    
    # To create gene ranges, group by 'geneName' and aggregate the 'start' and 'end' columns
    gene_df = df.groupby(['geneName', 'Chromosome', 'Strand',]).agg({'Start': 'min', 'End': 'max'}).reset_index()
    
    geneRanges = pr.PyRanges(gene_df)
    
    # Exons must be extracted from chromStarts and blockSizes
    # Initialize an empty list to store the transformed data
    exon_data = []
    
    # Iterate through each row and split the data into separate rows
    # TODO: add cds info or create separate track
    for index, row in df.iterrows():
        Name = row['Name']
        chrom = row['Chromosome']
        chrstart = int(row['Start'])
        starts = [chrstart+int(start) for start in row['chromStarts'].rstrip(',').split(',')]
        bsizes = [int(bsize) for bsize in row['blockSizes'].rstrip(',').split(',')]
        
        # Create rows for each exon
        for start, bsize in zip(starts, bsizes):
            exon_data.append([row['Name'], row['geneName'], row['Chromosome'], start, start+bsize, row['Strand']])
    
    # Create a new DataFrame from the transformed data
    exon_df = pd.DataFrame(exon_data, columns=['Name', 'geneName', 'Chromosome', 'Start', 'End', 'Strand'])
    exonRanges = pr.PyRanges(exon_df)
    return geneRanges, transcriptRanges, exonRanges

if __name__ == "__main__":
    if len(sys.argv)==1:
        parser.print_help()
        sys.exit(1)
    args = parser.parse_args()
    geneRanges, transcriptRanges, exonRanges = make_pyranges(args.bedfile)
#    chromExonTree, chromTxTree = chromIntervalTreesFromBed(args.bedfile)
    print(geneRanges)



