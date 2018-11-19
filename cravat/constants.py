import os
import copy

packagedir = os.path.dirname(os.path.abspath(__file__))
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

crm_def = [{'name':'original_line', 'title':'Original Line', 'type':'int'},
           {'name':'tags', 'title':'User Tags', 'type':'string'},
           {'name':'uid', 'title':'UID', 'type':'int'}]
crm_idx = [['uid'],['tags']]
crs_def = [{'name':'uid', 'title':'UID', 'type':'string'},
           {'name':'sample_id', 'title':'Sample', 'type':'string'}]
crs_idx = [['uid'], ['sample_id']]
crv_def = [{'name':'uid', 'title':'UID', 'type':'int'},
           {'name':'chrom', 'title':'Chrom', 'type':'string'},
           {'name':'pos', 'title':'Position', 'type':'int'},
           {'name':'ref_base', 'title':'Ref Base', 'type':'string'},
           {'name':'alt_base', 'title':'Alt Base', 'type':'string'}]
crv_idx = [['uid']]
crx_def = crv_def + \
          [{'name':'coding', 'title':'Coding', 'type':'string'},
           {'name':'hugo', 'title':'Hugo', 'type':'string'},
           {'name':'transcript', 'title':'Transcript', 'type':'string'},
           {'name':'so', 'title':'Sequence Ontology', 'type':'string'},
           {'name':'achange', 'title':'Protein Change', 'type':'string'},
           {'name':'all_mappings', 'title':'All Mappings', 'type':'string'},
           ]
crx_idx = [['uid']]
crg_def = [{'name':'hugo', 'title':'Hugo', 'type':'string'},
           {'name':'num_variants', 'title':'Variants in Gene', 'type':'int'},
           {'name':'so', 'title':'Sequence Ontology', 'type':'string'},
           {'name':'all_so', 'title':'All Sequence Ontologies', 'type':'string'}
          ]
crg_idx = [['hugo']]
crt_def = [{'name':'primary_transcript', 'title':'Primary transcript', 
            'type':'string'},
           {'name':'alt_transcript', 'title':'Alternate transcript',
            'type':'string'}]
crt_idx = [['primary_transcript']]
crl_def = [{'name':'uid', 'title':'UID', 'type':'int'},
           {'name':'chrom', 'title':'Chrom', 'type':'string'},
           {'name':'pos', 'title':'Pos', 'type':'int'},
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
