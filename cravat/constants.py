import os
import copy
import pathlib
import shutil
import sys

packagedir = os.path.dirname(os.path.abspath(__file__))
user_dir = str(pathlib.Path.home())
cravat_data_dir = os.path.join(user_dir, 'open-cravat')
if os.path.exists(cravat_data_dir) == False:
    os.mkdir(cravat_data_dir)
>>>>>>> b6eb7e249b39c18bd178947ad4c5ff1f5888908b
system_conf_fname = 'cravat-system-dev.yml'
system_conf_path = os.path.join(packagedir, system_conf_fname)
if os.path.exists(system_conf_path) == False:
    system_conf_fname = 'cravat-system.yml'
    system_conf_path = os.path.join(packagedir, system_conf_fname)
system_conf_template_fname = 'cravat-system.template.yml'
system_conf_template_path = os.path.join(packagedir, system_conf_template_fname)
modules_dir_key = 'modules_dir'
default_modules_dir_relative = os.path.join('modules')
default_modules_dir = os.path.join(packagedir, default_modules_dir_relative)
if os.path.exists(default_modules_dir) == False:
    os.mkdir(default_modules_dir)
base_modules_key = 'base_modules'
main_conf_fname = 'cravat.yml'
liftover_chains_dir = os.path.join(packagedir, 'liftover')
liftover_chain_paths = {
                        'hg19': os.path.join(liftover_chains_dir,
                                             'hg19ToHg38.over.chain'
                                             ),
                        'hg18': os.path.join(liftover_chains_dir,
                                             'hg18ToHg38.over.chain'
                                             )
                        }

crm_def = [{'name':'original_line', 'title':'Original Line', 'type':'int', 'width': 90},
           {'name':'tags', 'title':'User Tags', 'type':'string', 'width': 90},
           {'name':'uid', 'title':'UID', 'type':'int', 'width': 70}]
crm_idx = [['uid'],['tags']]
crs_def = [{'name':'uid', 'title':'UID', 'type':'string', 'width': 70},
           {'name':'sample_id', 'title':'Sample', 'type':'string', 'width': 90, 'category': 'multi'}]
crs_idx = [['uid'], ['sample_id']]
crv_def = [{'name':'uid', 'title':'UID', 'type':'int', 'width': 70, 'filterable': False},
           {'name':'chrom', 'title':'Chrom', 'type':'string', 'width': 80, 'category': 'single', 'filterable': True},
           {'name':'pos', 'title':'Position', 'type':'int', 'width': 80, 'filterable': True},
           {'name':'ref_base', 'title':'Ref Base', 'type':'string', 'width': 80, 'filterable': False},
           {'name':'alt_base', 'title':'Alt Base', 'type':'string', 'width': 80, 'filterable': False},
           {'name': 'note', 'title': 'Note', 'type': 'string', 'width': 100},
           ]
crv_idx = [['uid']]
crx_def = crv_def + \
          [{'name':'coding', 'title':'Coding', 'type':'string', 'width': 50, 'category': 'single'},
           {'name':'hugo', 'title':'Hugo', 'type':'string', 'width': 70, 'filterable': True},
           {'name':'transcript', 'title':'Transcript', 'type':'string', 'width': 150, 'filterable': False},
           {'name':'so', 'title':'Sequence Ontology', 'type':'string', 'width': 200, 'category': 'single',
               'categories': [
                   '2KD',
                   '2KU', 
                   'UT3', 
                   'UT5', 
                   'INT', 
                   'UNK', 
                   'SYN', 
                   'MIS', 
                   'CSS', 
                   'IND', 
                   'INI', 
                   'STL', 
                   'SPL', 
                   'STG', 
                   'FSD', 
                   'FSI'], 'filterable': True},
           {'name':'achange', 'title':'Protein Change', 'type':'string', 'width': 70, 'filterable': False},
           {'name':'all_mappings', 'title':'All Mappings', 'type':'string', 'width': 100, 'hidden':True, 'filterable': False},
           ]
crx_idx = [['uid']]
crg_def = [{'name':'hugo', 'title':'Hugo', 'type':'string', 'width': 70, 'filterable': True},
           {'name':'num_variants', 'title':'Variants in Gene', 'type':'int', 'width': 130, 'filterable': False},
           {'name':'so', 'title':'Sequence Ontology', 'type':'string', 'width': 200, 'category': 'single',
               'categories': [
                   '2KD',
                   '2KU', 
                   'UT3', 
                   'UT5', 
                   'INT', 
                   'UNK', 
                   'SYN', 
                   'MIS', 
                   'CSS', 
                   'IND', 
                   'INI', 
                   'STL', 
                   'SPL', 
                   'STG', 
                   'FSD', 
                   'FSI'], 'filterable': True},
           {'name':'all_so', 'title':'All Sequence Ontologies', 'type':'string', 'width': 190, 'filterable': False},
           {'name': 'note', 'title': 'Note', 'type': 'string', 'width': 100},
          ]
crg_idx = [['hugo']]
crt_def = [{'name':'primary_transcript', 'title':'Primary transcript', 
            'type':'string'},
           {'name':'alt_transcript', 'title':'Alternate transcript',
            'type':'string'}]
crt_idx = [['primary_transcript']]
crl_def = [{'name':'uid', 'title':'UID', 'type':'int', 'width': 70},
           {'name':'chrom', 'title':'Chrom', 'type':'string', 'width': 80},
           {'name':'pos', 'title':'Pos', 'type':'int', 'width': 80},
           ]

exit_codes = {
    'alreadycrv':2,
    2:'alreadycrv'
}

all_mappings_col_name = 'all_mappings'
mapping_parser_name = 'mapping_parser'

VARIANT = 0
GENE = 1
LEVELS = {'variant': VARIANT, 'gene': GENE}

viewer_effective_digits = 3
