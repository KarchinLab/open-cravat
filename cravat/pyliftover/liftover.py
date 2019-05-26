'''
Pure-python implementation of UCSC "liftover" genome coordinate conversion.
Main class, which is actually a convenience wrapper around chainfile.py's LiftOverChainFile

Copyright 2013, Konstantin Tretyakov.
http://kt.era.ee/

Licensed under MIT license.
'''

import os.path
import gzip
from .chainfile import open_liftover_chain_file, LiftOverChainFile

class LiftOver:
    def __init__(self, from_db, to_db=None, search_dir='.', cache_dir=os.path.expanduser("~/.pyliftover"), use_web=True, write_cache=True, use_gzip=None, show_progress=False):
        '''
        LiftOver can be initialized in multiple ways.
         * By providing a filename as a single argument: LiftOver("hg17ToHg18.over.chain.gz")
           The file may be a usual or a gzip-compressed file. The compression is automatically detected from the .gz extension.
           If you want to override the way this is handled (e.g. open a file with non-gz extension as gzipped file), use use_gzip=True or use_gzip=False as needed.
         * By providing an opened file opbject as a single argument: LiftOver(open("hg17ToHg18.over.chain"))
         * By providing name of from_db and to_db, e.g. LiftOver('hg18', 'hg19').
           In this case, LiftOver will "intelligently" search for the best available over.chain file for converting between the assemblies.
           The file will be searched in local directory, cache directory, or even downloaded from the web, if possible.
           The exact way this is handled (as well as all the other parameters of the constructor) is documented in 
           :see:`pyliftover.chainfile.open_liftover_chain_file`.
        If show_progress == True, a progress bar will be shown in the console. This requires tqdm to be installed (not installed automatically with the package).
        
        Test providing filename:
        >>> lo = LiftOver('tests/data/mds42.to.mg1655.liftOver')
        >>> lo.convert_coordinate('AP012306.1', 16000) #doctest: +ELLIPSIS (because on 32-bit systems there's an L qualifier after the number and on 64-bit ones there's nothing.
        [('Chromosome', 21175, '+', 378954552...)]

        Test providing from_db and to_db:
        >>> lo = LiftOver('hg17', 'hg18')
        >>> lo.convert_coordinate('chr1', 1000000)
        [('chr1', 949796, '+', 21057807908...)]
        >>> lo.convert_coordinate('chr1', 0)
        [('chr1', 0, '+', 21057807908...)]
        >>> lo.convert_coordinate('chr1', 0, '-')
        [('chr1', 0, '-', 21057807908...)]
        >>> lo.convert_coordinate('chr1', 103786442)
        [('chr20', 20668001, '-', 14732...)]
        >>> lo.convert_coordinate('chr1', 103786443, '-')
        [('chr20', 20668000, '+', 14732...)]
        >>> lo.convert_coordinate('chr1', 103786441, '+')
        []
        '''
        if to_db is None:
            # A file name or a file object was provided
            if isinstance(from_db, str):
                do_gzip = use_gzip if use_gzip is not None else from_db.lower().endswith('.gz')
                if do_gzip:
                    f = gzip.open(from_db, 'rb')
                else:
                    f = open(from_db, 'rb')
            else:
                f = from_db
        else:
            # From- and To- db names were provided.
            f = open_liftover_chain_file(from_db=from_db, to_db=to_db, search_dir=search_dir, cache_dir=cache_dir, use_web=use_web, write_cache=write_cache)
        self.chain_file = LiftOverChainFile(f, show_progress=show_progress)
        f.close()
        
    def convert_coordinate(self, chromosome, position, strand='+'):
        '''
        Returns a *list* of possible conversions for a given chromosome position.
        The list may be empty (no conversion), have a single element (unique conversion), or several elements (position mapped to several chains).
        The list contains tuples (target_chromosome, target_position, target_strand, conversion_chain_score),
        where conversion_chain_score is the "alignment score" field specified at the chain used to perform conversion. If there
        are several possible conversions, they are sorted by decreasing conversion_chain_score.
        
        IF chromosome is completely unknown to the LiftOver, None is returned.
        
        Note that coordinates are 0-based, and even at negative strand are relative to the beginning of the genome.
        I.e. position 0 strand + is the first position of the genome. Position 0 strand - is also the first position of the genome 
        (and the last position of reverse-complemented genome).
        '''
        results = self.chain_file.query(chromosome, position)
        if results == None:
            return None
        (dummy, block_ids) = results
        if block_ids.size == 0:
            return None
        else:
            # query_results contains intervals which contain the query point. We simply have to remap to corresponding targets.
            results = []
            for block_id in block_ids:
                (chain, block) = self.chain_file.blocks_by_id[block_id]
                (source_start, source_end, target_start) = block
                result_position = target_start + (position - source_start)
                #result_position = chain.target_start + (position - chain.source_start)
                if chain.target_strand == '-':
                    result_position = target_size - 1 - result_position
                result_strand = chain.target_strand if strand == '+' else ('+' if chain.target_strand == '-' else '-')
                results.append((chain.target_name, result_position, result_strand, chain.score))
            #if len(results) > 1:
            results.sort(key=lambda x: x[3], reverse=True)
            return results
