#! /usr/bin/env python3

import vcf
import os
import sys
import argparse
import textwrap
import pandas as pd
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=textwrap.dedent('''\

Turn a vcf into a pandas dataframe, splitting INFO and FORMAT fields

        '''))
group = parser.add_argument_group('required arguments')
group.add_argument('vcffile', type=str, help='VCF file')

# TODO: get all info fields from the vcf

def vcfToDf(vcffile):
    data = []
    vcf_reader = vcf.Reader(open(vcffile))
    for rec in vcf_reader:
        vcfrow = {}
        attribute_dict = vars(rec)
        for attribute, value in attribute_dict.items():
            # keep in mind that ALT, FILTER and samples are lists
            if attribute == 'ALT' and len(value) >1:
                sys.stderr.write('Complex rearrangement, skipping %s' % value)
                continue
            # INFO is a dict; split it
            if attribute == 'INFO':
                for key, val in value.items():
                    vcfrow['INFO.' + key] = val
            # todo? Split format and sample fields (see potential code below)
            else:
                vcfrow[attribute] = value
        if not isinstance(vcfrow['ALT'][0], (vcf.model._SingleBreakend, vcf.model._Breakend)):
            print(vcfrow, 'AND', str(vcfrow['ALT'][0]))
        data.append(vcfrow)
    return pd.DataFrame(data)

### POTENTIAL CODE
#            # samples is a list of Call data
#            # https://pyvcf.readthedocs.io/en/latest/API.html#vcf-model-call
#            # call doesn't have __dict__ so is harder to access. This works:
#            if attribute == 'samples':
#                # Use dir() to list attributes and methods of the object
#                attributes_and_methods = dir(value[0])
#                
#                # Print all attributes and their values
#                for attr in attributes_and_methods:
#                    # Check if it's not a method (functions)
#                    if not callable(getattr(value[0], attr)):
#                        print('SAMPLE', attr, getattr(value[0], attr))
#                    else:
#                        print('oh but callable', attr)
#                # but in my example all fields are empty (could be that they're filled
#                # by pyvcf during the filtering call or so
###

if __name__ == "__main__":
    if len(sys.argv)==1:
        parser.print_help()
        sys.exit(1)
    args = parser.parse_args()
    vcf = vcfToDf(args.vcffile)

