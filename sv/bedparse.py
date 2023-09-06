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
    def __init__(self, tx):
        self.name = tx.gene
        if not self.name:
            self.name = tx.name  # use transcript ID
        self.chromstart = tx.chromStart
        self.chromend = tx.chromEnd
        self.exonIV = []
    def update(self, tx):
        self.start = min(self.chromstart, tx.chromStart)
        self.end = max(self.chromend, tx.chromEnd)
        # exons are kept with the transcript ID
        for start, size in zip(tx.starts, tx.sizes):
            end = start+size
            self.exonIV.append(Interval(start, end, tx.gene))
    def makeInterval(self):
        '''This interval should only be created when all transcripts have been added'''
        self.interval = Interval(self.chromstart, self.chromend, self.name)
        self.exonTree = IntervalTree(self.exonIV)
        # merge identical exons, keeping all transcript IDs
        # NOTE: merge_equals automatically sends the data (=name) for the existing and the new intervals
        # to whatever function you specify as the data_reducer. This is only explained
        # in help(IntervalTree.merge_equals) - this in case someone else spends a morning figuring this out
        # also lambda simply means 'unnamed function'
        self.exonTree.merge_equals(data_reducer=lambda currentdata, newdata: f'{currentdata};{newdata}')      

class chromGeneRanges():
    '''Contains gene objects for a single chromosome'''
    def __init__(self, chrom):
        self.genedict = dict()
        self.chrom = chrom
#        self.exonIV = []
    def add(self, tx):
        '''Adds all exons for a transcript and extends gene boundaries if necessary.'''
        if tx.gene in self.genedict:
            self.genedict[tx.gene].update(tx)
        else:
            self.genedict[tx.gene] = geneObj(tx)
    def makeTrees(self):
        '''IntervalTree merges identical intervals while keeping all transcript names'''
        [val.makeInterval() for val in self.genedict.values()]
        self.geneTree = IntervalTree([gene.interval for gene in self.genedict.values()])
        # the exons are already intervaltrees so we must concatenate them without merging
        self.exonTree = IntervalTree()
        trees = [gene.exonTree for gene in self.genedict.values()]
        for tree in trees:
                self.exonTree |= tree

class bedObj():
    '''Extracts transcript info from a bed file. By default expects gencode from UCSC, which has
       a gene name in field 17. To change this behavior, set genefield=3.'''
    def __init__(self, line, genefield=17):
        fields = line.strip().split("\t")
        self.chrom      = fields[0]
        self.chromStart = int(fields[1])
        self.chromEnd   = int(fields[2])
        self.name       = fields[3]
        blockSizes      = fields[10]
        blockStarts     = fields[11]
        self.starts     = [int(start) + self.chromStart for start in blockStarts.rstrip(',').split(',')]
        self.sizes      = [int(size) for size in blockSizes.rstrip(',').split(',')]
        # use the transcript ID by default
        self.gene = self.name 
        # but try to get the gene ID
        if genefield and genefield != '':
            self.gene = fields[genefield]

def chromIntervalTreesFromBed(bedfile, genefield=17):
    '''Returns two dictionaries of chromosome interval trees with gene name tuples.
       One tree contains exons, the other transcript boundaries'''
    curChrom = False
    chromGenes = False
    chromExonTree = dict()
    chromTxTree = dict()
    with open(bedfile, 'r') as f:
        for line in f:
            tx = bedObj(line, genefield)
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
    chromExonTree, chromTxTree = chromIntervalTreesFromBed(args.bedfile)
    print(chromTxTree)

