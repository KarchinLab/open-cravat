#!/usr/bin/env python3

import sys, os, re, argparse, textwrap
import vcf
import sqlite3
import pandas as pd
import pyranges as pr

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=textwrap.dedent('''\

Read in VCF and bed, find overlaps based on VCF startpos and, if paired, mate location.
Keep in mind that bed is 0 based and VCF is 1 based

        '''))
group = parser.add_argument_group('required arguments')
group.add_argument('bedfile', type=str, help='Bed file')
group.add_argument('vcffile', type=str, help='VCF file')


def create_tables(dbpath, dbname):
    '''Create sqlite db and tables'''
    if not dbname.endswith('\.sql'):
        dbname += '.sql'
    dbpath = os.path.join(dbpath, dbname)
    conn = sqlite3.connect(dbpath)
    cursor = conn.cursor()
    q = "create table if not exists structuralvariants (START_ID text primary key, END_ID text)"
    cursor.execute(q)
    q = "create table if not exists breakpoints (STRUCTURAL_VARIANT_ID text primary key, CHROM text, POS integer)"
    cursor.execute(q)
    q = "create table if not exists affectedgenes (STRUCTURAL_VARIANT_ID text, GENE_NAME text, LOCATION text, SCORE numeric)"
    cursor.execute(q)
    return conn

def insert_many(sql, recordList, conn):
    '''Takes a simple sql statement and a list of tuples to insert, then runs executemany'''
    cursorObj = conn.cursor()
    try:
        cursorObj.executemany(sql, recordList)
        conn.commit()
    except sqlite3.Error as error:
        print("Failed to update", error, file=sys.stderr)
        sys.exit(1)

def vcfOverlap(bedfile, vcffile, dbpath='./', dbname='test'):
    '''Create pyranges objects from input bed (expects ucsc gencode format), then loop through vcf to find overlaps.
    Specify type of overlap (intron, coding/noncoding exon).
    Keep in mind that multiple genes may overlap the same nucleotide (TODO: order by priority)'''

    if not bedfile.endswith('.bed'):
        print(f'ERROR, {bedfile} does not look like a bed file', file=sys.stderr)
        sys.exit()

    # setup a database and table insert statements
    conn = create_tables(dbpath, dbname)
    structuralvariants_insert = "INSERT OR REPLACE INTO structuralvariants (START_ID, END_ID) VALUES (?, ?);"
    structuralvariants_entries = []
    breakpoints_insert = "INSERT OR REPLACE INTO breakpoints (STRUCTURAL_VARIANT_ID, CHROM, POS) values (?, ?, ?);"
    breakpoints_entries = []
    affectedgenes_insert = "INSERT OR REPLACE INTO affectedgenes (STRUCTURAL_VARIANT_ID, GENE_NAME, LOCATION, SCORE) values (?, ?, ?, ?);" 
    affectedgenes_entries = []

    # turn the bed file into a pyranges intervaltree
    bedTxTree = make_pyranges(bedfile)
    annotChroms = bedTxTree.df['Chromosome'].unique()
    bedExonTree = pr.PyRanges()
    isPaired = [] # translocation/deletion mates do not need to get parsed again

    # loop over the vcf file
    with open(vcffile, 'r') as f:
        reader = vcf.Reader(f)
        for variant in reader:  
            status = False
            # create a dict of all info in a single line first
            vcfrow = {}
            attribute_dict = vars(variant)
            for attribute, value in attribute_dict.items():
                # keep in mind that ALT, FILTER and samples are lists
                if attribute == 'ALT':
                    if len(value) >1:
                        sys.stderr.write('Complex rearrangement, skipping %s' % value)
                        status = 'Complex rearrangement, skipping'
                        continue
                    else:
                        vcfrow['ALT'] = value[0]
                # INFO is a dict; split it
                elif attribute == 'INFO':
                    for key, val in value.items():
                        vcfrow['INFO.' + key] = val
                # TODO? Split format and sample fields
                else:
                    vcfrow[attribute] = value

            if not 'INFO.SVTYPE' in vcfrow:
                sys.stderr.write('Does not appear to be SV' % svrow['ID'])
                status = 'Does not appear to be SV, skipping'
            elif not vcfrow['CHROM'] in annotChroms:
                status = 'Local breakpoint not in reference'
            if status is not False:
                print(vcfrow['ID'], status)
                continue
                
            # Now that we have a dict, extract relevant info and do overlaps

            localOnly = False
            endPos = False
            status = ''
            # gridss calls everything a BND
            if isinstance(vcfrow['ALT'], vcf.model._SingleBreakend):
                localOnly = True
                status = 'Unpaired breakend; '
            # skip partner if it's in a non-genome contig
            elif isinstance(vcfrow['ALT'], (vcf.model._Breakend)):
                if not vcfrow['ALT'].withinMainAssembly:
                    localOnly = True
                    status = 'Remote breakpoint not in reference; '
            elif 'INFO.END' in vcfrow:
                endPos = vcfrow['INFO.END']
            else:
                localOnly = True
 
            if vcfrow['ID'] in isPaired:
                status = 'part of a previous pair, skipping'
                print(vcfrow['ID'], status)
                continue

            # for every breakend we want to know the local overlap
            # Note: we're trying to be clever here and only create exon trees if we need them
            # so bedExonTree gets larger during the run (but will never come close to a full genome
            # version)
            localBND = breakPoint(vcfrow, bedTxTree, bedExonTree)
            breakpoints_entries.append((localBND.ID, localBND.CHROM, localBND.POS))
            for gene in localBND.geneinfo:
                affectedgenes_entries.append((localBND.ID, gene.Name, gene.location, 0.5))

            if not localBND.newExons.empty:
                bedExonTree = pr.concat([bedExonTree, localBND.newExons])
            if localOnly == True:
                status += makeStatus(localBND.geneinfo, location='local')
                print(vcfrow['ID'], status)
                continue

            # paired breakpoints have a local and a remote location;
            # single breakends or mates in non-reference locations are localOnly
            if 'INFO.MATEID' in vcfrow:
                isPaired.append(vcfrow['INFO.MATEID'][0])
            if endPos:
                remoteBND = breakPoint(vcfrow, bedTxTree, bedExonTree, alt='OTHERSV')
            else:
                remoteBND = breakPoint(vcfrow, bedTxTree, bedExonTree, alt='MATE')
            if remoteBND.CHROM not in annotChroms:
                status += 'Remote breakpoint not in reference; '
                status += makeStatus(localBND.geneinfo, location='local')
            else:
                status = pairInfo(localBND, remoteBND, bedExonTree)
            breakpoints_entries.append((remoteBND.ID, remoteBND.CHROM, remoteBND.POS))
            structuralvariants_entries.append((localBND.ID, remoteBND.ID))
            for gene in remoteBND.geneinfo:
                affectedgenes_entries.append((remoteBND.ID, gene.Name, gene.location, 0.5))
            print(vcfrow['ID'], status)
    insert_many(structuralvariants_insert, structuralvariants_entries, conn)
    insert_many(breakpoints_insert, breakpoints_entries, conn)
    insert_many(affectedgenes_insert, affectedgenes_entries, conn)
    conn.close()


def make_pyranges(bedfile):
    '''Turn the gencode bed file into three pyranges: gene, transcript, and exon'''
    # read the gencode bed file in as a dataframe
    # use bigBedInfo gencodeV43.bed to get column names
    names = ['Chromosome', 'Start', 'End', 'Name', 'score', 'Strand', 'thickStart', 'thickEnd', 'reserved',
             'blockCount', 'blockSizes', 'chromStarts', 'name2', 'cdsStartStat', 'cdsEndStat', 'exonFrames',
             'type', 'geneName', 'geneName2', 'geneType', 'transcriptClass', 'source', 'transcriptType', 'tag',
             'level', 'tier', 'rank']
    df = pd.read_csv(bedfile, header=None, names=names, sep="\t")
    return pr.PyRanges(df)
    
def makeExonRanges(transcripts, bedExonTree):
    '''Create an exon pyranges object from a transcript pyranges object if the transcript 
       is not already in bedExonTree'''
    exon_data = []
    txIntrons = dict()
    if bedExonTree.empty:
        newtx = transcripts.df
    else:
        newtx = transcripts.df[~transcripts.df['Name'].isin(bedExonTree.df['Name'])]

    for index, row in newtx.iterrows():
        prevstart = None
        Name = row['Name']
        chrom = row['Chromosome']
        chrstart = int(row['Start'])
        starts = [chrstart+int(start) for start in row['chromStarts'].rstrip(',').split(',')]
        bsizes = [int(bsize) for bsize in row['blockSizes'].rstrip(',').split(',')]
        exonframes = [int(exonframe) for exonframe in row['exonFrames'].rstrip(',').split(',')]

        # Create rows for each exon
        for start, bsize, exonframe in zip(starts, bsizes, exonframes):
            exon_data.append([row['Name'], row['geneName'], row['Chromosome'], start, start+bsize, row['Strand'], exonframe])

    # Create a new DataFrame from the transformed data
    exon_df = pd.DataFrame(exon_data, columns=['Name', 'geneName', 'Chromosome', 'Start', 'End', 'Strand', 'Frame'])
    exonRanges = pr.PyRanges(exon_df)
    return exonRanges # , txIntrons



class breakPoint:
    def __init__(self, vcfrow, bedTxTree, bedExonTree, alt=False):
        '''
        Does overlaps with a single breakpoint. If a gene overlap is found, check exons to see
        if the overlap occurs in an intron or (coding) exon.
        vcfrow: pyvcf object
        bedTxTree, bedExonTree: PyRanges objects of gencode transcripts and exons
        alt: MATE (This breakend is a mate (derived from the ALT column in the VCF))
             or OTHERSV (non translocation but annotated with SVTYPE)
        '''
        self.geneinfo = []
        self.newExons = pr.PyRanges()
#    self.structuralvariants_entry = (ID, MATE)
#    self.affectedgenes_entry = (ID, GeneName, 0.5)
        if alt == False:
            self.ID = vcfrow['ID']
            self.CHROM = vcfrow['CHROM']
            self.POS = vcfrow['POS']-1 # go to zero-based
        elif alt == 'OTHERSV':
            self.ID = vcfrow['ID']+'.END'
            self.CHROM = vcfrow['CHROM']
            self.POS = int(vcfrow['INFO.END'])-1 # go to zero-based
        elif alt == 'MATE':
            alt = vcfrow['ALT']
            self.ID = vcfrow['INFO.MATEID'][0]
            pattern = r'[\]\[]?(\w+):(\d+)' 
            match = re.search(pattern, str(alt))
            if match:
                self.CHROM = match.group(1)
                self.POS = int(match.group(2))-1
            else:
                print(f'WARNING, do not understand {str(alt)}, skipping mate analysis', file=sys.stderr)
                self.transcripts = pr.PyRanges()
                return
        # add chr to standard chromosomes if necessary
        if self.CHROM.isdigit() or self.CHROM == 'M':
            self.CHROM = 'chr'+self.CHROM

        # pyranges is open ended, meaning the end coordinate is not included in the range
        self.transcripts = bedTxTree[self.CHROM, self.POS:self.POS+1]
        if not self.transcripts.empty:
            self.geneinfo = [geneObject(gene) for gene in self.transcripts.df['geneName'].unique()]
            self.newExons = makeExonRanges(self.transcripts, bedExonTree)
            self.checkExons(pr.concat([bedExonTree, self.newExons]))
            
    def checkExons(self, bedExonTree):
        '''Determines if the breakpoint overlaps a coding or noncoding exon. Since this function only gets
           called if a transcript was already found, the default is intron.'''
        self.location = 'INTRON'
        self.exons = bedExonTree[self.CHROM, self.POS:self.POS+1]
        if len(self.exons) == 0:
            return
        for gene in self.geneinfo:
        # is the breakpoint in an exon?
            exons = self.exons[self.exons.geneName == gene.Name]
            if len(exons) > 0:
                # there can be multiple overlapping exons because we're looking at multiple transcripts
                # noncoding exons are -1, coding are 0,1,2
                if (exons.df['Frame'] >= 0).any():
                    gene.addEnds(exons, 'CODING EXON')
                else:
                    gene.addEnds(exons, 'NONCODING EXON')

    def getGene(self, geneName):
        '''Return gene object if name matches'''
        for gene in self.geneinfo:
            if gene.Name == geneName:
                return gene

class geneObject:
    '''Holds information on genes extraced from pyranges objects'''
    def __init__(self, name):
        '''Set gene name and assume the overlap is in an intron for now'''
        self.Name = name
        self.location = 'INTRON'
        self.exonstart = False
        self.exonend = False
    def addEnds(self, prExons, location):
        '''
           Add exonstart and exonend to the gene object
           prExons: pyranges object of exons with a Frame column (-1 if noncoding)
           location: 'CODING EXON' or 'NONCODING EXON'
        '''
        self.location = location
        if location == 'CODING EXON':
            self.exonstart = prExons.df.loc[prExons.df['Frame'] >= 0, 'Start'].min()
            self.exonend   = prExons.df.loc[prExons.df['Frame'] >= 0, 'End'].min()
        elif location == 'NONCODING EXON':
            self.exonstart = prExons.df['Start'].min()
            self.exonend   = prExons.df['End'].max()
    def inSameExon(self, geneobj):
        '''Find matching gene object by name'''
        if self.name == geneobj.name:
            if self.exonstart == geneobj.exonstart and self.exonend == geneobj.exonend:
                return True
        return False
    

def pairInfo(localBND, remoteBND, bedExonTree):
    '''
    Checks for intragenic deletions.
    localBND: Breakpoint object containing overlapped genes
    remoteBND: Breakpoint object for mate
    bedExonTree: PyRanges object with exons
    Code checks if both breakends affect the same gene(s). If so, it determines where each
    breakend occurs (intron, coding exon, noncoding exon) and if both are in the same exon or intron, or
    if they delete one or more exons. 
    This code does not determine how many exons are deleted, and it prioritizes coding exons (so if coding 
    and noncoding exons are deleted, only coding are reported)
    '''
    status = ''
    sharedGenes = [gene.Name for gene in localBND.geneinfo if gene.Name in [gene.Name for gene in remoteBND.geneinfo]]
    if len(sharedGenes) == 0:
        status = 'No shared genes; '
        status += makeStatus(localBND.geneinfo, location='local')
        status += makeStatus(remoteBND.geneinfo, location='remote')
        if not re.search('INTERGENIC', status):
            status += 'Fusion gene possible'
        return status
    # we're not going to worry about individual transcripts
    # note: we may be skipping genes here if only one of the breakpoints is in it
    for gene in sharedGenes:
        localgene = localBND.getGene(gene)
        remotegene = remoteBND.getGene(gene)
        if localgene.location == remotegene.location == 'INTRON':
            # Does the range overlap an exon?
            exons = bedExonTree[localBND.CHROM, localBND.POS:remoteBND.POS]
            if exons.empty or len(exons[exons.geneName == gene]) == 0:
                status += f'Breakpoints cause deletion inside INTRON of {gene}; '
            else:
                exons = exons[exons.geneName == gene]
                if exons[exons.Frame >= 0]:
                    status += f'CODING EXON(s) of {gene} deleted; '
                else:
                    status += f'NONCODING EXON(s) of {gene} deleted; '
        elif localgene.exonstart == remotegene.exonstart and localgene.exonend == remotegene.exonend:
            status += f'Breakpoints cause deletion in {localgene.location} of {gene}; '
        else:
            # NOTE: this catch-all contains all combinations of intron and (non)coding exons
            status += f'{gene} local {localgene.location}, remote {remotegene.location}, different locations; '
    return status

def makeStatus(genelist, location):
    '''
        Create status string for a single variant.
        genelist: a list of gene objects
        location: local or remote, where remote is the mate of a paired breakpoint
    '''
    status = f'{location}: '
    if len(genelist) > 0:
        strings = [f'{gene.location} of {gene.Name}; ' for gene in genelist]
        status += ''.join(strings)
    else:
        status += 'INTERGENIC '
    return status


if __name__ == "__main__":
    if len(sys.argv)==1:
        parser.print_help()
        sys.exit(1)
    args = parser.parse_args()
    vcfOverlap(args.bedfile, args.vcffile)


