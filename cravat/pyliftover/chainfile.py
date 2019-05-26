'''
Pure-python implementation of UCSC "liftover" genome coordinate conversion.
Class for dealing with "xx.over.chain" files.

Copyright 2013, Konstantin Tretyakov.
http://kt.era.ee/

Licensed under MIT license.
'''

import os.path
import gzip
import urllib
import shutil
import sys
import ncls
import numpy as np

if sys.version_info >= (3, 0):
    import urllib.request

if sys.version_info < (3, 3):
    FancyURLopener = urllib.FancyURLopener if sys.version_info < (3, 0) else urllib.request.FancyURLopener

    class ErrorAwareURLOpener(FancyURLopener):
      def http_error_default(self, url, fp, errcode, errmsg, headers):
        raise Exception("404")

    _urlopener = ErrorAwareURLOpener()
    urlretrieve = _urlopener.retrieve
else:
    urlretrieve = urllib.request.urlretrieve

def open_liftover_chain_file(from_db, to_db, search_dir='.', cache_dir=os.path.expanduser("~/.pyliftover"), use_web=True, write_cache=True):
    '''
    A "smart" way of obtaining liftover chain files.
    By default acts as follows:
     1. If the file ``<from_db>To<to_db>.over.chain.gz`` exists in <search_dir>,
        opens it for reading via gzip.open.
     2. Otherwise, if the file ``<from_db>To<to_db>.over.chain`` exists
        in the <search_dir> opens it (as uncompressed file).
        Steps 1 and 2 may be disabled if search_dir is set to None.
     3. Otherwise, checks whether ``<cache_dir>/<from_db>To<to_db>.over.chain.gz`` exists.
        This step may be disabled by specifying cache_dir = None.
     4. If file still not found attempts to download the file from the URL
        'http://hgdownload.cse.ucsc.edu/goldenPath/<from_db>/liftOver/<from_db>To<to_db>.over.chain.gz'
        to a temporary location. This step may be disabled by specifying use_web=False. In this case the operation fails and 
        the function returns None.
     5. At this point, if write_cache=True and cache_dir is not None and writable, the file is copied to cache_dir and opened from there.
        Otherwise it is opened from the temporary location.
        
    In case of errors (e.g. URL cannot be opened), None is returned.
    '''
    to_db = to_db[0].upper() + to_db[1:]
    FILE_NAME_GZ = '%sTo%s.over.chain.gz' % (from_db, to_db)
    FILE_NAME = '%sTo%s.over.chain' % (from_db, to_db)
    
    if search_dir is not None:
        FILE_GZ = os.path.join(search_dir, FILE_NAME_GZ)
        FILE = os.path.join(search_dir, FILE_NAME)
        if os.path.isfile(FILE_GZ):
            return gzip.open(FILE_GZ, 'rb')
        elif os.path.isfile(FILE):
            return open(FILE, 'rb')
    if cache_dir is not None:
        FILE_GZ = os.path.join(cache_dir, FILE_NAME_GZ)
        if os.path.isfile(FILE_GZ):
            return gzip.open(FILE_GZ, 'rb')
    if use_web:
        # Download file from the web.
        try:
            url = 'http://hgdownload.cse.ucsc.edu/goldenPath/%s/liftOver/%sTo%s.over.chain.gz' % (from_db, from_db, to_db)
            (filename, headers) = urlretrieve(url)
        except:
            # Download failed, exit
            return None
        # Move the file to cache?
        if write_cache and (cache_dir is not None):
            try:
                if not os.path.isdir(cache_dir):
                    os.mkdir(cache_dir)
                shutil.move(filename, FILE_GZ)
                # Move successful, open from cache
                return gzip.open(FILE_GZ, 'rb')
            except:
                # Move failed, open file from temp location
                return gzip.open(filename, 'rb')
        else:
            # Open from temp location
            return gzip.open(filename, 'rb')
    # If we didn't quit before this place, all failed.
    return None


class LiftOverChainFile:
    '''
    The class, which loads and indexes USCS's .over.chain files.
    
    Specification of the chain format can be found here: http://genome.ucsc.edu/goldenPath/help/chain.html
    '''
    
    def __init__(self, f, show_progress=False):
        '''
        Reads chain data from the file and initializes an interval index.
        f must be a file object open for reading.
        If any errors are detected, an Exception is thrown.
        
        If show_progress == True, a progress bar is shown in the console.
        Requires tqdm to be installed.
        '''
        self.source_names = []
        self.num_blocks_by_source_name = {}
        self.chains_by_id = {}
        self.blocks_by_id = {}
        self.chains = self._load_chains(f, self.source_names, self.num_blocks_by_source_name, self.chains_by_id, show_progress)
        self.chain_index = self._index_chains(self.chains, self.source_names, self.num_blocks_by_source_name, self.blocks_by_id, show_progress)

    @staticmethod
    def _load_chains(f, source_names, num_blocks_by_source_name, chains_by_id, show_progress=False):
        '''
        Loads all LiftOverChain objects from a file into an array. Returns the result.
        '''
        chains = []
        chain_id = 0
        if show_progress:
            from tqdm import tqdm
            pbar = tqdm(total = float('inf'), desc="Reading file", unit=" chains")
        while True:
            line = f.readline()
            if not line:
                break
            if line.startswith(b'#') or line.startswith(b'\n') or line.startswith(b'\r'):
                continue
            if line.startswith(b'chain'):
                # Read chain
                chain = LiftOverChain(line, f)
                chain.id = chain_id
                chains_by_id[chain_id] = chain
                chains.append(chain)
                if chain.source_name not in num_blocks_by_source_name:
                    num_blocks_by_source_name[chain.source_name] = 0
                num_blocks_by_source_name[chain.source_name] += chain.num_blocks
                if chain.source_name not in source_names:
                    source_names.append(chain.source_name)
                if show_progress:
                    pbar.update(1)
                chain_id += 1
                continue
        return chains

    @staticmethod
    def _index_chains(chains, source_names, num_blocks_by_source_name, blocks_by_id, show_progress=False):
        chain_index = {}
        if show_progress:
            from tqdm import tqdm
            chains = tqdm(chains, desc="Indexing", unit=" chains")
        block_id = 0
        for source_name in source_names:
            num_blocks = num_blocks_by_source_name[source_name]
            source_starts = np.empty([num_blocks], dtype=np.int64)
            source_ends = np.empty([num_blocks], dtype=np.int64)
            block_ids = np.empty([num_blocks], dtype=np.int64)
            block_no = 0
            for chain in chains:
                if chain.source_name == source_name:
                    for block in chain.blocks:
                        (sfrom, sto, tfrom) = block
                        source_starts[block_no] = sfrom
                        source_ends[block_no] = sto
                        block_ids[block_no] = block_id
                        blocks_by_id[block_id] = (chain, block)
                        block_no += 1
                        block_id += 1
            chain_index[source_name] = ncls.NCLS(source_starts, source_ends, block_ids)
        return chain_index

    def query(self, chromosome, position):
        '''
        Given a chromosome and position, returns all matching records from the chain index.
        Each record is an interval (source_from, source_to, data)
        where data = (target_from, target_to, chain). Note that depending on chain.target_strand, the target values may need to be reversed (e.g. pos --> chain.target_size - pos).
        
        If chromosome is not found in the index, None is returned.
        '''
        # A somewhat-ugly hack to allow both 'bytes' and 'str' objects to be used as
        # chromosome names in Python 3. As we store chromosome names as strings,
        # we'll transparently translate the query to a string too.
        if type(chromosome).__name__ == 'bytes':
            chromosome = chromosome.decode('ascii')
        if chromosome not in self.chain_index:
            return None
        else:
            chains = self.chain_index[chromosome].all_overlaps_both(np.array([position]), np.array([position + 1]), np.array([-1]))
            return chains

class LiftOverChain:
    '''
    Represents a single chain from an .over.chain file.
    A chain basically maps a set of intervals from "source" coordinates to corresponding coordinates in "target" coordinates.
    The "source" and "target" are somehow referred to in the specs (http://genome.ucsc.edu/goldenPath/help/chain.html)
    as "target" and "query" respectively.
    '''
    __slots__ = ['score', 'source_name', 'source_size', 'source_start', 'source_end',
	             'target_name', 'target_size', 'target_strand', 'target_start', 'target_end', 'id', 'blocks', 'num_blocks']

    def __init__(self, header, f):
        '''
        Reads the chain from a stream given the first line and a file opened at all remaining lines.
        On error throws an exception.
        '''
        if sys.version_info >= (3, 0):
            header = header.decode('ascii') # In Python 2, work with usual strings.
        fields = header.split()
        if fields[0] != 'chain' and len(fields) not in [12, 13]:
            raise Exception("Invalid chain format. (%s)" % header)
        # chain 4900 chrY 58368225 + 25985403 25985638 chr5 151006098 - 43257292 43257528 1
        self.score = int(fields[1])        # Alignment score
        self.source_name = fields[2]       # E.g. chrY
        self.source_size = int(fields[3])  # Full length of the chromosome
        source_strand = fields[4]          # Must be +
        if source_strand != '+':
            raise Exception("Source strand in an .over.chain file must be +. (%s)" % header)
        self.source_start = int(fields[5]) # Start of source region
        self.source_end = int(fields[6])   # End of source region
        self.target_name = fields[7]       # E.g. chr5
        self.target_size = int(fields[8])  # Full length of the chromosome
        self.target_strand = fields[9]     # + or -
        if self.target_strand not in ['+', '-']:
            raise Exception("Target strand must be - or +. (%s)" % header)
        self.target_start = int(fields[10])
        self.target_end = int(fields[11])
        self.id = None if len(fields) == 12 else fields[12].strip()
        
        # Now read the alignment chain from the file and store it as a list (source_from, source_to) -> (target_from, target_to)
        sfrom, tfrom = self.source_start, self.target_start
        self.blocks = []
        fields = f.readline().decode('ascii').split()
        while len(fields) == 3:
            size, sgap, tgap = int(fields[0]), int(fields[1]), int(fields[2])
            self.blocks.append((sfrom, sfrom+size, tfrom))
            sfrom += size + sgap
            tfrom += size + tgap
            fields = f.readline().split()
        if len(fields) != 1:
            raise Exception("Expecting one number on the last line of alignments block. (%s)" % header)
        size = int(fields[0])
        self.blocks.append((sfrom, sfrom+size, tfrom))
        self.num_blocks = len(self.blocks)
        if (sfrom + size) != self.source_end  or (tfrom + size) != self.target_end:
            raise Exception("Alignment blocks do not match specified block sizes. (%s)" % header)

    def __repr__ (self):
        return '{}:{}-{} => {}:{}-{}'.format(self.source_name, self.source_start, self.source_end, self.target_name, self.target_start, self.target_end)
