import re
import os
import importlib
import sys
import oyaml as yaml
import chardet
import gzip
import types
import inspect
import logging
from distutils.version import LooseVersion
from cravat.cravat_util import max_version_supported_for_migration
import sqlite3
import pkg_resources
import datetime
import argparse
from types import SimpleNamespace
import math


def get_ucsc_bins(start, stop=None):
    if stop is None:
        stop = start + 1

    def range_per_level(start, stop):
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

    return [
        x
        for first, last in range_per_level(start, stop)
        for x in range(first, last + 1)
    ]


complementary_base = {
    "A": "T",
    "T": "A",
    "C": "G",
    "G": "C",
    "-": "-",
    "": "",
    "N": "N",
}


def reverse_complement(bases):
    return "".join([complementary_base[base] for base in bases[::-1]])


def switch_strand(bases, start_strand=None, dest_strand=None, pos=0):
    rev_comp = reverse_complement(bases)
    if start_strand == "-" or dest_strand == "+":
        new_pos = pos + len(bases.replace("-", "")) - 1
    elif start_strand == "+" or dest_strand == "-":
        new_pos = pos - len(bases.replace("-", "")) + 1
    else:
        err_msg = "start_strand or dest_strand must be specified as + or -"
        raise ValueError(err_msg)
    return rev_comp, new_pos


aa_123 = {
    "A": "Ala",
    "C": "Cys",
    "E": "Glu",
    "D": "Asp",
    "G": "Gly",
    "F": "Phe",
    "I": "Ile",
    "H": "His",
    "K": "Lys",
    "M": "Met",
    "L": "Leu",
    "N": "Asn",
    "Q": "Gln",
    "P": "Pro",
    "S": "Ser",
    "R": "Arg",
    "T": "Thr",
    "W": "Trp",
    "V": "Val",
    "Y": "Tyr",
    "*": "Ter",
    "": "",
}


def aa_let_to_abbv(lets):
    return "".join([aa_123[x] for x in lets])


aa_321 = {
    "Asp": "D",
    "Ser": "S",
    "Gln": "Q",
    "Lys": "K",
    "Trp": "W",
    "Asn": "N",
    "Pro": "P",
    "Thr": "T",
    "Phe": "F",
    "Ala": "A",
    "Gly": "G",
    "Cys": "C",
    "Ile": "I",
    "Leu": "L",
    "His": "H",
    "Arg": "R",
    "Met": "M",
    "Val": "V",
    "Glu": "E",
    "Tyr": "Y",
    "Ter": "*",
    "": "",
}


def aa_abbv_to_let(abbvs):
    if type(abbvs) != str:
        raise TypeError("Expected str not %s" % type(abbvs).__name__)
    if len(abbvs) % 3 != 0:
        raise ValueError("Must be evenly divisible by 3")
    out = ""
    for i in range(0, len(abbvs), 3):
        abbv = abbvs[i].upper() + abbvs[i + 1 : i + 3].lower()
        out += aa_321[abbv]
    return out


tmap_re = re.compile(
    "\*?(?P<transcript>[A-Z_]+\d+\.\d+):"
    + "(?P<ref>[A-Z_\*]+)"
    + "(?P<pos>\d+|NA)"
    + "(?P<alt>[A-Z_\*]+)"
    + "\((?P<so>\w+)\)"
    + "\((?P<hugo>\w+)\)"
)

codon_table = {
    "ATG": "M",
    "GCT": "A",
    "GCC": "A",
    "GCA": "A",
    "GCG": "A",
    "TGT": "C",
    "TGC": "C",
    "GAT": "D",
    "GAC": "D",
    "GAA": "E",
    "GAG": "E",
    "TTT": "F",
    "TTC": "F",
    "GGT": "G",
    "GGC": "G",
    "GGA": "G",
    "GGG": "G",
    "CAT": "H",
    "CAC": "H",
    "ATT": "I",
    "ATC": "I",
    "ATA": "I",
    "AAA": "K",
    "AAG": "K",
    "TTA": "L",
    "TTG": "L",
    "CTT": "L",
    "CTC": "L",
    "CTA": "L",
    "CTG": "L",
    "AAT": "N",
    "AAC": "N",
    "CCT": "P",
    "CCC": "P",
    "CCA": "P",
    "CCG": "P",
    "CAA": "Q",
    "CAG": "Q",
    "TCT": "S",
    "TCC": "S",
    "TCA": "S",
    "TCG": "S",
    "AGT": "S",
    "AGC": "S",
    "ACT": "T",
    "ACC": "T",
    "ACA": "T",
    "ACG": "T",
    "CGT": "R",
    "CGC": "R",
    "CGA": "R",
    "CGG": "R",
    "AGA": "R",
    "AGG": "R",
    "GTT": "V",
    "GTC": "V",
    "GTA": "V",
    "GTG": "V",
    "TGG": "W",
    "TAT": "Y",
    "TAC": "Y",
    "TGA": "*",
    "TAA": "*",
    "TAG": "*",
    "AUG": "M",
    "GCU": "A",
    "GCC": "A",
    "GCA": "A",
    "GCG": "A",
    "UGU": "C",
    "UGC": "C",
    "GAU": "D",
    "GAC": "D",
    "GAA": "E",
    "GAG": "E",
    "UUU": "F",
    "UUC": "F",
    "GGU": "G",
    "GGC": "G",
    "GGA": "G",
    "GGG": "G",
    "CAU": "H",
    "CAC": "H",
    "AUU": "I",
    "AUC": "I",
    "AUA": "I",
    "AAA": "K",
    "AAG": "K",
    "UUA": "L",
    "UUG": "L",
    "CUU": "L",
    "CUC": "L",
    "CUA": "L",
    "CUG": "L",
    "AAU": "N",
    "AAC": "N",
    "CCU": "P",
    "CCC": "P",
    "CCA": "P",
    "CCG": "P",
    "CAA": "Q",
    "CAG": "Q",
    "UCU": "S",
    "UCC": "S",
    "UCA": "S",
    "UCG": "S",
    "AGU": "S",
    "AGC": "S",
    "ACU": "T",
    "ACC": "T",
    "ACA": "T",
    "ACG": "T",
    "CGU": "R",
    "CGC": "R",
    "CGA": "R",
    "CGG": "R",
    "AGA": "R",
    "AGG": "R",
    "GUU": "V",
    "GUC": "V",
    "GUA": "V",
    "GUG": "V",
    "UGG": "W",
    "UAU": "Y",
    "UAC": "Y",
    "UGA": "*",
    "UAA": "*",
    "UAG": "*",
}


def translate_codon(bases, fallback=None):
    if len(bases) != 3:
        if fallback is None:
            return KeyError(bases)
        else:
            return fallback
    else:
        return codon_table[bases]


def valid_so(so):
    return so in so_severity


def get_caller_name(path):
    path = os.path.abspath(path)
    basename = os.path.basename(path)
    if "." in basename:
        module_name = ".".join(basename.split(".")[:-1])
    else:
        module_name = basename
    return module_name


def load_class(path, class_name=None):
    """Load a class from the class's name and path. (dynamic importing)"""
    path_dir = os.path.dirname(path)
    sys.path = [path_dir] + sys.path
    module = None
    module_class = None
    module_name = os.path.basename(path).split(".")[0]
    try:
        module = __import__(module_name)
    except:
        try:
            spec = importlib.util.spec_from_file_location(class_name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except:
            raise
            logger = logging.getLogger("cravat")
            logger.exception(f"{module_name} could not be loaded.")
            print(f"{module_name} is not found")
    if module is not None:
        if class_name is not None:
            module_class = getattr(module, class_name)
        else:
            for n in dir(module):
                if n.startswith("Cravat") or n == "Mapper" or n == "Reporter":
                    c = getattr(module, n)
                    if inspect.isclass(c):
                        module_class = c
                        break
    del sys.path[0]
    return module_class


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
        action.dest: action.default
        for action in parser._actions
        if action.dest != "help"
    }


def detect_encoding(path):
    if " " not in path:
        path = path.strip('"')
    if path.endswith(".gz"):
        f = gzip.open(path)
    else:
        f = open(path, "rb")
    detector = chardet.universaldetector.UniversalDetector()
    for n, line in enumerate(f):
        if n > 100:
            break
        detector.feed(line)
        if detector.done:
            break
    detector.close()
    f.close()
    encoding = detector.result["encoding"]
    # utf-8 is superset of ascii that may include chars
    # not in the first 100 lines
    if encoding == "ascii":
        return "utf-8"
    else:
        return encoding


def is_compatible_version(dbpath):
    db = sqlite3.connect(dbpath)
    c = db.cursor()
    oc_version = LooseVersion(pkg_resources.get_distribution("open-cravat").version)
    sql = 'select colval from info where colkey="open-cravat"'
    c.execute(sql)
    r = c.fetchone()
    compatible = None
    db_version = "0.0.0"
    if r is None:
        compatible = False
    else:
        db_version = LooseVersion(r[0])
        if db_version < max_version_supported_for_migration:
            compatible = False
        else:
            compatible = True
    return compatible, db_version, oc_version


def is_url(s):
    if s.startswith("http://") or s.startswith("https://"):
        return True
    else:
        return False


def get_current_time_str():
    t = datetime.datetime.now()
    return t.strftime("%Y:%m:%d %H:%M:%S")


def get_args(parser, inargs, inkwargs):
    # Combines arguments in various formats.
    inarg_dict = {}
    for inarg in inargs:
        t = type(inarg)
        if t == list:  # ['-t', 'text']
            if inarg[0].endswith(".py"):
                inarg = inarg[1:]
            inarg_dict.update(**vars(parser.parse_args(inarg)))
        elif t == argparse.Namespace:  # already parsed by a parser.
            inarg_dict.update(**vars(inarg))
        elif t == types.SimpleNamespace:
            inarg_dict.update(**vars(inarg))
        elif t == dict:  # {'output_dir': '/rt'}
            inarg_dict.update(inarg)
    inarg_dict.update(inkwargs)
    arg_dict = get_argument_parser_defaults(parser)
    arg_dict.update(inarg_dict)
    args = SimpleNamespace(**arg_dict)
    return args


def filter_affected_cols(filter):
    cols = set()
    if "column" in filter:
        cols.add(filter["column"])
    else:
        for rule in filter["rules"]:
            cols.update(filter_affected_cols(rule))
    return cols


def humanize_bytes(num, binary=False):
    """Human friendly file size"""
    exp2unit_dec = {0: "B", 1: "kB", 2: "MB", 3: "GB"}
    exp2unit_bin = {0: "B", 1: "KiB", 2: "MiB", 3: "GiB"}
    max_exponent = 3
    if binary:
        base = 1024
    else:
        base = 1000
    if num > 0:
        exponent = math.floor(math.log(num, base))
        if exponent > max_exponent:
            exponent = max_exponent
    else:
        exponent = 0
    quotient = float(num) / base ** exponent
    if binary:
        unit = exp2unit_bin[exponent]
    else:
        unit = exp2unit_dec[exponent]
    quot_str = "{:.1f}".format(quotient)
    # No decimal for byte level sizes
    if exponent == 0:
        quot_str = quot_str.rstrip("0").rstrip(".")
    return "{quotient} {unit}".format(quotient=quot_str, unit=unit)

def write_log_msg(logger, e):
    if hasattr(e, "msg"):
        if type(e.msg) == list:
            for l in e.msg:
                logger.info(l)
                print(l)
        else:
            logger.info(e)
            print(e)
    else:
        logger.info(e)
        print(e)

