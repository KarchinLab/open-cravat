import os
import copy
import pathlib
import shutil
import sys
import platform
import yaml

# Directories
custom_modules_dir = None
custom_system_conf_path = None
modules_dir_env_key = 'OPENCRAVAT_MD'
system_conf_path_env_key = 'OPENCRAVAT_SYSTEM_CONF_PATH'
packagedir = os.path.dirname(os.path.abspath(__file__))
pl = platform.platform()
if pl.startswith("Windows"):
    oc_root_dir = os.path.join(
        os.path.expandvars("%systemdrive%"), os.sep, "open-cravat"
    )
elif pl.startswith("Linux"):
    oc_root_dir = packagedir
elif pl.startswith("Darwin") or pl.startswith("macOS"):
    oc_root_dir = "/Users/Shared/open-cravat"
if os.path.exists(oc_root_dir) == False:
    os.mkdir(oc_root_dir)
# conf dir
conf_dir_name = "conf"
conf_dir_key = "conf_dir"
default_conf_dir = os.path.join(oc_root_dir, conf_dir_name)
if os.path.exists(default_conf_dir) == False:
    os.mkdir(default_conf_dir)
admindb_path = os.path.join(default_conf_dir, "admin.sqlite")
system_conf_fname = "cravat-system.yml"
system_conf_path = os.path.join(default_conf_dir, system_conf_fname)
system_conf_template_fname = "cravat-system.template.yml"
system_conf_template_path = os.path.join(packagedir, system_conf_template_fname)
if os.path.exists(system_conf_path) == False:
    shutil.copyfile(system_conf_template_path, system_conf_path)
# conf
f = open(system_conf_path)
conf = yaml.safe_load(f)
f.close()
# modules dir
modules_dir_key = "modules_dir"
modules_dir_name = "modules"
if not modules_dir_key in conf:
    default_modules_dir = os.path.join(oc_root_dir, modules_dir_name)
    if os.path.exists(default_modules_dir) == False:
        os.mkdir(default_modules_dir)
    conf[modules_dir_key] = default_modules_dir
    wf = open(system_conf_path, "w")
    yaml.dump(conf, wf, default_flow_style=False)
    wf.close()
# jobs dir
jobs_dir_key = "jobs_dir"
jobs_dir_name = "jobs"
if not jobs_dir_key in conf:
    default_jobs_dir = os.path.join(oc_root_dir, jobs_dir_name)
    if os.path.exists(default_jobs_dir) == False:
        os.mkdir(default_jobs_dir)
    conf[jobs_dir_key] = default_jobs_dir
# log dir
log_dir_key = "log_dir"
log_dir_name = "logs"
if not log_dir_key in conf:
    default_log_dir = os.path.join(oc_root_dir, log_dir_name)
    if os.path.exists(default_log_dir) == False:
        os.mkdir(default_log_dir)
    conf[log_dir_key] = default_log_dir
# Live conf
live_conf_fname = "live.yml"

base_modules_key = "base_modules"
main_conf_fname = "cravat.yml"
main_conf_path = os.path.join(default_conf_dir, main_conf_fname)
if os.path.exists(main_conf_path) == False:
    shutil.copyfile(os.path.join(packagedir, main_conf_fname), main_conf_path)

# liftover
liftover_chains_dir = os.path.join(packagedir, "liftover")
liftover_chain_paths = {
    "hg19": os.path.join(liftover_chains_dir, "hg19ToHg38.over.chain"),
    "hg18": os.path.join(liftover_chains_dir, "hg18ToHg38.over.chain"),
}

# built-in file column definitions
crm_def = [
    {"name": "original_line", "title": "Original Line", "type": "int", "width": 90},
    {"name": "tags", "title": "User Tags", "type": "string", "width": 90},
    {"name": "uid", "title": "UID", "type": "int", "width": 70},
    {
        "name": "fileno",
        "title": "Input File Number",
        "type": "int",
        "width": 90,
        "filterable": False,
        "hidden": True,
    },
]
crm_idx = [["uid"], ["tags"]]
crs_def = [
    {"name": "uid", "title": "UID", "type": "int", "width": 70},
    {"name": "sample_id", "title": "Sample", "type": "string", "width": 90},
]
crs_idx = [["uid"], ["sample_id"], ["sample_id", "uid"]]
crv_def = [
    {
        "name": "uid",
        "title": "UID",
        "type": "int",
        "width": 60,
        "hidden": True,
        "filterable": False,
    },
    {
        "name": "chrom",
        "title": "Chrom",
        "type": "string",
        "width": 50,
        "category": "single",
        "filterable": True,
    },
    {
        "name": "pos",
        "title": "Position",
        "type": "int",
        "width": 80,
        "filterable": True,
    },
    {
        "name": "ref_base",
        "title": "Ref Base",
        "type": "string",
        "width": 50,
        "filterable": False,
    },
    {
        "name": "alt_base",
        "title": "Alt Base",
        "type": "string",
        "width": 50,
        "filterable": False,
    },
    {"name": "note", "title": "Note", "type": "string", "width": 50},
]
crv_idx = [["uid"]]
crx_def = crv_def + [
    {
        "name": "coding",
        "title": "Coding",
        "type": "string",
        "width": 50,
        "category": "single",
        "categories": ["Y"],
    },
    {
        "name": "hugo",
        "title": "Gene",
        "type": "string",
        "width": 70,
        "filterable": True,
    },
    {
        "name": "transcript",
        "title": "Transcript",
        "type": "string",
        "width": 135,
        "hidden": False,
        "filterable": False,
    },
    {
        "name": "so",
        "title": "Sequence Ontology",
        "type": "string",
        "width": 120,
        "category": "single",
        "filterable": True,
    },
    {
        "name": "cchange",
        "title": "cDNA change",
        "type": "string",
        "width": 70,
        "filterable": False,
    },
    {
        "name": "achange",
        "title": "Protein Change",
        "type": "string",
        "width": 55,
        "filterable": False,
    },
    {
        "name": "all_mappings",
        "title": "All Mappings",
        "type": "string",
        "width": 100,
        "hidden": True,
        "filterable": False,
    },
]
crx_idx = [["uid"]]
crg_def = [
    {
        "name": "hugo",
        "title": "Gene",
        "type": "string",
        "width": 70,
        "filterable": True,
    },
    {"name": "note", "title": "Note", "type": "string", "width": 50},
]
crg_idx = [["hugo"]]
crt_def = [
    {"name": "primary_transcript", "title": "Primary transcript", "type": "string"},
    {"name": "alt_transcript", "title": "Alternate transcript", "type": "string"},
]
crt_idx = [["primary_transcript"]]
crl_def = [
    {"name": "uid", "title": "UID", "type": "int", "width": 70},
    {"name": "chrom", "title": "Chrom", "type": "string", "width": 80},
    {"name": "pos", "title": "Pos", "type": "int", "width": 80},
    {"name": "ref_base", "title": "Reference allele", "type": "string", "width": 80},
    {"name": "alt_base", "title": "Alternate allele", "type": "string", "width": 80},
]

exit_codes = {"alreadycrv": 2, 2: "alreadycrv"}

all_mappings_col_name = "all_mappings"
mapping_parser_name = "mapping_parser"

VARIANT = 0
GENE = 1
LEVELS = {"variant": VARIANT, "gene": GENE}

gene_level_so_exclude = ["2KU", "2KD"]

base_smartfilters = [
    {
        "name": "popstats",
        "title": "Population AF <=",
        "description": "Set a maximum allele frequency.",
        "allowPartial": True,
        "selector": {
            "type": "inputFloat",
            "defaultValue": "0.1",
        },
        "filter": {
            "operator": "and",
            "rules": [
                {
                    "operator": "or",
                    "rules": [
                        {
                            "column": "gnomad3__af",
                            "test": "lessThanEq",
                            "value": "${value}",
                        },
                        {"column": "gnomad3__af", "test": "noData"},
                    ],
                },
                {
                    "operator": "or",
                    "rules": [
                        {
                            "column": "gnomad__af",
                            "test": "lessThanEq",
                            "value": "${value}",
                        },
                        {"column": "gnomad__af", "test": "noData"},
                    ],
                },
                {
                    "operator": "or",
                    "rules": [
                        {
                            "column": "thousandgenomes__af",
                            "test": "lessThanEq",
                            "value": "${value}",
                        },
                        {
                            "column": "thousandgenomes__af",
                            "test": "noData",
                        },
                    ],
                },
            ],
        },
    },
    {
        "name": "so",
        "title": "Sequence Ontology",
        "description": "Select sequence ontologies.",
        "selector": {
            "type": "select",
            "optionsColumn": "base__so",
            "multiple": True,
            "defaultValue": ["MIS"],
        },
        "filter": {"column": "base__so", "test": "select", "value": "${value}"},
    },
    {
        "name": "chrom",
        "title": "Chromosome",
        "description": "Select chromosome(s).",
        "selector": {
            "type": "select",
            "multiple": True,
            "optionsColumn": "base__chrom",
        },
        "filter": {"column": "base__chrom", "test": "select", "value": "${value}"},
    },
    {
        "name": "coding",
        "title": "Coding",
        "description": "Include only coding/noncoding variants",
        "selector": {
            "type": "select",
            "options": {"No": True, "Yes": False},
            "defaultValue": False,
        },
        "filter": {"column": "base__coding", "test": "hasData", "negate": "${value}"},
    },
]

module_tag_desc = {
    "allele frequency": "modules for studying allele frequency across populations",
    "cancer": "tools for cancer research",
    "clinical relevance": "tools for assessing clinical relevance of variants",
    "converters": "modules for using the result of other tools as open-cravat input",
    "dbnsfp": "modules ported from dbNSFP",
    "denovo": "modules related to denovo variants",
    "evolution": "modules for studying variants in evolutionary context",
    "genes": "modules for studying variants at the gene level",
    "genomic features": "modules for studying genomic features",
    "interaction": "modules for studying molecular interactions",
    "literature": "modules for variant-related literature",
    "multiple assays": "modules for multiplex assays",
    "non coding": "modules for studying noncoding variants",
    "protein visualization": "modules to visualize variants on protein structures",
    "reporters": "modules for generating output formats",
    "variant effect prediction": "modules to predict variant effects",
    "variants": "modules to study variants at the variant level",
    "visualization widgets": "modules for visualizing variants",
}

legacy_gene_level_cols_to_skip = ["base__num_variants", "base__so", "base__all_so"]
default_num_input_line_warning_cutoff = 25000
default_settings_gui_input_size_limit = 500
default_max_num_concurrent_jobs = 4
default_max_num_concurrent_annotators_per_job = max(1, os.cpu_count() - 1)
default_multicore_mapper_mode = True
default_assembly = "hg38"
default_assembly_key = "default_assembly"
assembly_choices = ["hg38", "hg19", "hg18"]
publish_time_fmt = "%Y-%m-%dT%H:%M:%S.%f%z"

install_tempdir_name = "temp"

cannonical_chroms = ["chr" + str(n) for n in range(1, 23)] + ["chrX", "chrY"]
default_postaggregator_names = ["tagsampler", "casecontrol", "varmeta", "vcfinfo"]
