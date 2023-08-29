#!/usr/bin/env python3

import sys, os, re, argparse, textwrap
from intervaltree import Interval, IntervalTree

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=textwrap.dedent('''\

Turn UCSC's gencode bed file into two interval trees, one for exons and another for genes. 
This bed file has several extra fields, one of which contains a gene name.

        '''))
group = parser.add_argument_group('required arguments')
group.add_argument('bedfile', type=str, help='Input bed file')

class geneObj():
    '''A gene coordinate object that can be updated with additional transcripts'''
    def __init__(self, name, start, end):
        self.name = name
        self.chromstart = start
        self.chromend = end
    def update(self, start, end):
        self.start = min(self.chromstart, start)
        self.end = max(self.chromend, end)
    def makeInterval(self):
        '''This interval should only be created when all transcripts have been added'''
        self.interval = Interval(self.chromstart, self.chromend, self.name)

class chromGeneRanges():
    '''Contains gene objects for a single chromosome'''
    def __init__(self, chrom):
        self.genedict = dict()
        self.chrom = chrom
        self.exonIV = []
    def add(self, tx):
        '''Adds all exons for a transcript and extends gene boundaries if necessary.'''
        if tx.gene in self.genedict:
            self.genedict[tx.gene].update(tx.chromStart, tx.chromEnd)
        else:
            self.genedict[tx.gene] = geneObj(tx.gene, tx.chromStart, tx.chromEnd)
        # exons are kept with the transcript ID
        for start, size in zip(tx.starts, tx.sizes):
            end = start+size
            self.exonIV.append(Interval(start, end, tx.name))
    def makeTrees(self):
        '''IntervalTree merges identical intervals while keeping all transcript names'''
        [val.makeInterval() for val in self.genedict.values()]
        self.geneTree = IntervalTree([gene.interval for gene in self.genedict.values()]) 
        self.exonTree = IntervalTree(self.exonIV) 

class bedObj():
    '''Extracts info from the gencode (v43) bed file from UCSC, which has a gene name in field 17'''
    def __init__(self, line):
        fields = line.strip().split("\t")
        self.chrom      = fields[0] 
        self.chromStart = int(fields[1])
        self.chromEnd   = int(fields[2])
        self.name       = fields[3]
        blockSizes      = fields[10]
        blockStarts     = fields[11]
        self.gene       = fields[17]
        self.starts     = [int(start) + self.chromStart for start in blockStarts.rstrip(',').split(',')]
        self.sizes      = [int(size) for size in blockSizes.rstrip(',').split(',')]
    

def chromIntervalTreesFromBed(bedfile, genefield=False):
    '''Returns two dictionaries of chromosome interval trees with gene name tuples.
       One tree contains exons, the other transcript boundaries'''
    curChrom = False
    chromGenes = False
    chromExonTree = dict()
    chromTxTree = dict()
    with open(bedfile, 'r') as f:
        for line in f:
            tx = bedObj(line)
            if not curChrom:
                curChrom = tx.chrom
                chromGenes = chromGeneRanges(curChrom)
            # create the trees after we have all the interval tuples so that any identical ranges
            # get added with all relevant transcript names
            elif tx.chrom != curChrom:
                # done with previous chromosome, create trees
                if tx.chrom in chromExonTree:
                    print('ERROR, please sort bed input before running this program', file=sys.stderr)
                    sys.exit(1)
                chromGenes.makeTrees()
                chromExonTree[curChrom] = chromGenes.exonTree
                chromTxTree[curChrom] = chromGenes.geneTree
                # and reset
                curChrom = tx.chrom
                chromGenes = chromGeneRanges(curChrom)
            # add bed line to current chromosome object
            chromGenes.add(tx)
            
    f.close
    chromGenes.makeTrees()
    chromExonTree[curChrom] = chromGenes.exonTree
    chromTxTree[curChrom] = chromGenes.geneTree
    return(chromExonTree, chromTxTree)


if __name__ == "__main__":
    if len(sys.argv)==1:
        parser.print_help()
        sys.exit(1)
    args = parser.parse_args()
    chromIntervalTreesFromBed(args.bedfile)
