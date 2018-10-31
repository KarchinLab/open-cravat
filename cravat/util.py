import re
import os
import importlib
import sys
import yaml

def get_ucsc_bins (start, stop=None):
    if stop is None:
        stop = start + 1

    def range_per_level (start, stop):
            BIN_OFFSETS = [512 + 64 + 8 + 1, 64 + 8 + 1, 8 + 1, 1, 0]
            SHIFT_FIRST = 17
            SHIFT_NEXT = 3
            
            start_bin = start
            stop_bin = max(start, stop - 1)
            
            start_bin >>= SHIFT_FIRST
            stop_bin >>= SHIFT_FIRST
            
            for offset in BIN_OFFSETS:
                yield offset + start_bin, offset + stop_bin
                start_bin >>= SHIFT_NEXT
                stop_bin >>= SHIFT_NEXT
    return [x
            for first, last in range_per_level(start, stop)
            for x in range(first, last + 1)]

complementary_base = {'A':'T','T':'A','C':'G','G':'C','-':'-','':'','N':'N'}
def reverse_complement(bases):
    return ''.join([complementary_base[base] for base in bases[::-1]])
    
def switch_strand(bases, start_strand=None, dest_strand=None, pos=0):
    rev_comp = reverse_complement(bases)
    if start_strand == '-' or dest_strand == '+':
        new_pos = pos + len(bases.replace('-','')) - 1
    elif start_strand == '+' or dest_strand == '-':
        new_pos = pos - len(bases.replace('-','')) + 1
    else:
        err_msg = 'start_strand or dest_strand must be specified as + or -'
        raise ValueError(err_msg)
    return rev_comp, new_pos

aa_123 = {
          'A': 'Ala', 'C': 'Cys', 'E': 'Glu', 'D': 'Asp',
          'G': 'Gly', 'F': 'Phe', 'I': 'Ile', 'H': 'His',
          'K': 'Lys', 'M': 'Met', 'L': 'Leu', 'N': 'Asn',
          'Q': 'Gln', 'P': 'Pro', 'S': 'Ser', 'R': 'Arg',
          'T': 'Thr', 'W': 'Trp', 'V': 'Val', 'Y': 'Tyr',
          '*': 'Ter', '':''
         }
def aa_let_to_abbv(lets):
    return ''.join([aa_123[x] for x in lets])

aa_321 = {
          'Asp': 'D', 'Ser': 'S', 'Gln': 'Q', 'Lys': 'K',
          'Trp': 'W', 'Asn': 'N', 'Pro': 'P', 'Thr': 'T',
          'Phe': 'F', 'Ala': 'A', 'Gly': 'G', 'Cys': 'C',
          'Ile': 'I', 'Leu': 'L', 'His': 'H', 'Arg': 'R',
          'Met': 'M', 'Val': 'V', 'Glu': 'E', 'Tyr': 'Y',
          'Ter': '*','':''
         }
def aa_abbv_to_let(abbvs):
    if type(abbvs) != str:
        raise TypeError('Expected str not %s' %type(abbvs).__name__)
    if len(abbvs) % 3 != 0:
        raise ValueError('Must be evenly divisible by 3')
    out = ''
    for i in range(0,len(abbvs),3):
        abbv = abbvs[i].upper()+abbvs[i+1:i+3].lower()
        out += aa_321[abbv]
    return out

tmap_re = re.compile(
                     '\*?(?P<transcript>[A-Z_]+\d+\.\d+):'\
                     +'(?P<ref>[A-Z_\*]+)'\
                     +'(?P<pos>\d+|NA)'\
                     +'(?P<alt>[A-Z_\*]+)'\
                     +'\((?P<so>\w+)\)'\
                     +'\((?P<hugo>\w+)\)'
                     )

codon_table = {"ATG":"M", "GCT":"A", "GCC":"A", "GCA":"A", "GCG":"A", "TGT":"C", "TGC":"C",
               "GAT":"D", "GAC":"D", "GAA":"E", "GAG":"E", "TTT":"F", "TTC":"F", "GGT":"G",
               "GGC":"G", "GGA":"G", "GGG":"G", "CAT":"H", "CAC":"H", "ATT":"I", "ATC":"I",
               "ATA":"I", "AAA":"K", "AAG":"K", "TTA":"L", "TTG":"L", "CTT":"L", "CTC":"L",
               "CTA":"L", "CTG":"L", "AAT":"N", "AAC":"N", "CCT":"P", "CCC":"P", "CCA":"P",
               "CCG":"P", "CAA":"Q", "CAG":"Q", "TCT":"S", "TCC":"S", "TCA":"S", "TCG":"S",
               "AGT":"S", "AGC":"S", "ACT":"T", "ACC":"T", "ACA":"T", "ACG":"T", "CGT":"R",
               "CGC":"R", "CGA":"R", "CGG":"R", "AGA":"R", "AGG":"R", "GTT":"V", "GTC":"V",
               "GTA":"V", "GTG":"V", "TGG":"W", "TAT":"Y", "TAC":"Y", "TGA":"*", "TAA":"*",
               "TAG":"*","AUG":"M", "GCU":"A", "GCC":"A", "GCA":"A", "GCG":"A", "UGU":"C",
               "UGC":"C", "GAU":"D", "GAC":"D", "GAA":"E", "GAG":"E", "UUU":"F", "UUC":"F",
               "GGU":"G", "GGC":"G", "GGA":"G", "GGG":"G", "CAU":"H", "CAC":"H", "AUU":"I",
               "AUC":"I", "AUA":"I", "AAA":"K", "AAG":"K", "UUA":"L", "UUG":"L", "CUU":"L",
               "CUC":"L", "CUA":"L", "CUG":"L", "AAU":"N", "AAC":"N", "CCU":"P", "CCC":"P",
               "CCA":"P", "CCG":"P", "CAA":"Q", "CAG":"Q", "UCU":"S", "UCC":"S", "UCA":"S",
               "UCG":"S", "AGU":"S", "AGC":"S", "ACU":"T", "ACC":"T", "ACA":"T", "ACG":"T",
               "CGU":"R", "CGC":"R", "CGA":"R", "CGG":"R", "AGA":"R", "AGG":"R", "GUU":"V",
               "GUC":"V", "GUA":"V", "GUG":"V", "UGG":"W", "UAU":"Y", "UAC":"Y", "UGA":"*",
               "UAA":"*", "UAG":"*"}
def translate_codon(bases, fallback=None):
    if len(bases) != 3:
        if fallback is None:
            return KeyError(bases)
        else:
            return fallback
    else:
        return codon_table[bases]

so_severity = ['',
               '2KD',
               '2KU',
               'UT3',
               'UT5',
               'INT',
               'UNK',
               'SYN',
               'MIS',
               'CSS',
               'IDV',
               'IIV',
               'STL',
               'SPL',
               'STG',
               'FD2',
               'FD1',
               'FI2',
               'FI1']

def valid_so(so):
    return so in so_severity

def most_severe_so(so_list):
    return sort_so_severity(so_list)[-1]
        
def sort_so_severity(so_list, reverse=False):
    return sorted(so_list,key=so_severity.index)

def more_severe_so (so1, so2):
    soi1 = so_severity.index(so1)
    soi2 = so_severity.index(so2)
    return soi1 > soi2

def get_caller_name (path):
    path = os.path.abspath(path)
    basename = os.path.basename(path)
    if '.' in basename:
        module_name = '.'.join(basename.split('.')[:-1])
    else:
        module_name = basename
    return module_name

def load_class(class_name, path):
    """Load a class from the class's name and path. (dynamic importing)"""
    path_dir = os.path.dirname(path)
    sys.path = [path_dir] + sys.path
    spec = importlib.util.spec_from_file_location(class_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    del sys.path[0]
    return getattr(mod, class_name)

def get_directory_size(start_path):
    """
    Recursively get directory filesize.
    """
    total_size = 0
    for dirpath, _, filenames in os.walk(start_path):
        for fname in filenames:
            fp = os.path.join(dirpath, fname)
            total_size += os.path.getsize(fp)
    return total_size

def get_argument_parser_defaults(parser):
    return { 
             action.dest : action.default
             for action in parser._actions
             if action.dest != 'help'
            }
