import subprocess
import sqlite3
import cravat.constants as constants
import pyliftover
import argparse
import os
import sys
import json
import traceback
import shutil
import tempfile
import time
import concurrent.futures
import urllib.parse
from pathlib import Path
import datetime
from . import admin_util as au
from . import cravat_filter
from looseversion import LooseVersion
from cravat import util
import asyncio


def get_args():
    args = parser.parse_args()
    return args


def converttohg38(args):
    if args.sourcegenome not in ["hg18", "hg19"]:
        print("Source genome should be either hg18 or hg19.")
        exit()
    if os.path.exists(args.db) == False:
        print(args.db, "does not exist.")
        exit()
    liftover = pyliftover.LiftOver(
        constants.get_liftover_chain_path_for_src_genome(args.sourcegenome)
    )
    print("Extracting table schema from DB...")
    cmd = ["sqlite3", args.db, ".schema"]
    output = subprocess.check_output(cmd)
    sqlpath = args.db + ".newdb.sql"
    wf = open(sqlpath, "w")
    wf.write(output.decode())
    wf.close()
    newdbpath = ".".join(args.db.split(".")[:-1]) + ".hg38.sqlite"
    if os.path.exists(newdbpath):
        print("Deleting existing hg38 DB...")
        os.remove(newdbpath)
    print("Creating " + newdbpath + "...")
    newdb = sqlite3.connect(newdbpath)
    newc = newdb.cursor()
    print("Creating same table(s) in " + newdbpath + "...")
    cmd = ["sqlite3", newdbpath, ".read " + sqlpath]
    output = subprocess.check_output(cmd)
    db = sqlite3.connect(args.db)
    c = db.cursor()
    if args.tables == None:
        print("tables not given. All tables will be tried.")
        output = subprocess.check_output(["sqlite3", args.db, ".table"])
        args.tables = output.decode().split()
        args.tables.sort()
        print("The following tables will be examined:", ", ".join(args.tables))
    tables_toconvert = []
    tables_tocopy = []
    for table in args.tables:
        c.execute("select * from " + table + " limit 1")
        cols = [v[0] for v in c.description]
        hit = False
        if args.chromcol is not None and args.chromcol not in cols:
            tables_tocopy.append(table)
            continue
        for col in args.cols:
            if col in cols:
                hit = True
                break
        if hit:
            tables_toconvert.append(table)
        else:
            tables_tocopy.append(table)
    print(
        "Tables to convert:",
        ", ".join(tables_toconvert) if len(tables_toconvert) > 0 else "none",
    )
    print(
        "Tables to copy:",
        ", ".join(tables_tocopy) if len(tables_tocopy) > 0 else "none",
    )
    wf = open(newdbpath + ".noconversion", "w")
    count_interval = 10000
    for table in tables_toconvert:
        print("Converting " + table + "...")
        c.execute("select * from " + table)
        allcols = [v[0] for v in c.description]
        colnos = []
        for col in args.cols:
            if col in allcols:
                colnos.append(allcols.index(col))
        if args.chromcol is None:
            chromcolno = None
        else:
            chromcolno = allcols.index(args.chromcol)
        count = 0
        for row in c.fetchall():
            row = list(row)
            if chromcolno is not None:
                chrom = row[chromcolno]
            else:
                chrom = table
            if chrom.startswith("chr") == False:
                chrom = "chr" + chrom
            for colno in colnos:
                pos = int(row[colno])
                liftover_out = liftover.convert_coordinate(chrom, pos)
                if liftover_out == None:
                    print("- no liftover mapping:", chrom + ":" + str(pos))
                    continue
                if liftover_out == []:
                    wf.write(table + ":" + ",".join([str(v) for v in row]) + "\n")
                    continue
                newpos = liftover_out[0][1]
                row[colno] = newpos
            q = (
                "insert into "
                + table
                + " values("
                + ",".join(
                    ['"' + v + '"' if type(v) == type("a") else str(v) for v in row]
                )
                + ")"
            )
            newc.execute(q)
            count += 1
            if count % count_interval == 0:
                print("  " + str(count) + "...")
        print("  " + table + ": done.", count, "rows converted")
    wf.close()
    for table in tables_tocopy:
        count = 0
        print("Copying " + table + "...")
        c.execute("select * from " + table)
        for row in c.fetchall():
            row = list(row)
            q = (
                "insert into "
                + table
                + " values("
                + ",".join(
                    ['"' + v + '"' if type(v) == type("a") else str(v) for v in row]
                )
                + ")"
            )
            newc.execute(q)
            count += 1
            if count % count_interval == 0:
                print("  " + str(count) + "...")
        print("  " + table + ": done.", count, "rows converted")
    newdb.commit()


def migrate_result_144_to_145(dbpath):
    db = sqlite3.connect(dbpath)
    cursor = db.cursor()
    cursor.execute('update info set colval="1.4.5" where colkey="open-cravat"')
    db.commit()
    cursor.close()
    db.close()


def migrate_result_145_to_150(dbpath):
    db = sqlite3.connect(dbpath)
    cursor = db.cursor()
    # gene
    q = "select * from gene limit 1"
    cursor.execute(q)
    cols = [v[0] for v in cursor.description]
    gene_cols_to_retrieve = []
    note_to_add = True
    for col in cols:
        module = col.split("__")[0]
        if module == "base":
            if col == "base__hugo":
                gene_cols_to_retrieve.append(col)
            elif col == "base__note":
                gene_cols_to_retrieve.append(col)
                note_to_add = False
        else:
            gene_cols_to_retrieve.append(col)
    cursor.execute("alter table gene rename to gene_old")
    cursor.execute(
        "create table gene as select {} from gene_old".format(
            ",".join(gene_cols_to_retrieve)
        )
    )
    if note_to_add:
        cursor.execute("alter table gene add column base__note text")
    cursor.execute("drop table gene_old")
    cursor.execute("create index gene_idx_0 on gene (base__hugo)")
    # variant_header, gene_header, mapping_header, sample_header
    for table in ["variant", "gene", "mapping", "sample"]:
        q = "select * from {}_header".format(table)
        cursor.execute(q)
        rs = cursor.fetchall()
        cols = [v[0] for v in cursor.description]
        if len(cols) == 2 and "col_name" in cols and "col_def" in cols:
            pass
        else:
            q = "alter table {}_header rename to {}_header_old".format(table, table)
            cursor.execute(q)
            q = "create table {}_header (col_name text, col_def text)".format(table)
            cursor.execute(q)
            old_colkeys = [
                "col_name",
                "col_title",
                "col_type",
                "col_cats",
                "col_width",
                "col_desc",
                "col_hidden",
                "col_ctg",
                "col_filterable",
                "col_link_format",
            ]
            old_to_new_colkey = {
                "col_name": "name",
                "col_title": "title",
                "col_type": "type",
                "col_cats": "categories",
                "col_width": "width",
                "col_desc": "desc",
                "col_hidden": "hidden",
                "col_ctg": "category",
                "col_filterable": "filterable",
                "col_link_format": "link_format",
            }
            colnos = {}
            for c in old_colkeys:
                try:
                    colnos[c] = cols.index(c)
                except:
                    colnos[c] = None
            colidx = {}
            for r in rs:
                col_name = r[colnos["col_name"]]
                if table == "gene" and col_name not in gene_cols_to_retrieve:
                    continue
                module = col_name.split("__")[0]
                if module not in colidx:
                    colidx[module] = 0
                else:
                    colidx[module] += 1
                col_def = {}
                for c in old_colkeys:
                    if colnos[c] is not None:
                        value = r[colnos[c]]
                    else:
                        value = None
                    col_def[old_to_new_colkey[c]] = value
                col_def["index"] = colidx[module]
                col_def["genesummary"] = False
                if col_def["categories"] is None:
                    col_def["categories"] = []
                else:
                    col_def["categories"] = json.loads(col_def["categories"])
                if col_def["hidden"] is None:
                    col_def["hidden"] = False
                if col_def["hidden"] == 1:
                    col_def["hidden"] = True
                elif col_def["hidden"] == 0:
                    col_def["hidden"] = False
                if col_def["filterable"] is None:
                    col_def["filterable"] = True
                q = "insert into {}_header values ('{}', '{}')".format(
                    table, col_name, json.dumps(col_def)
                )
                cursor.execute(q)
            if table == "gene" and note_to_add:
                q = 'insert into gene_header (\'base__note\', \'{"name": "base__note", "index": 1, "title": "Note", "type": "string", "categories": [], "width": 50, "desc": null, "hidden": false, "category": null, "filterable": true, "link_format": null, "genesummary": false}\')'
                cursor.execute(q)
            q = "drop table {}_header_old".format(table)
        cursor.execute(q)
        db.commit()
    # mapping
    # base__fileno cannot be determined. set to 0.
    q = "select * from mapping limit 1"
    cursor.execute(q)
    cols = [v[0] for v in cursor.description]
    if "base__fileno" not in cols:
        q = "alter table mapping add column base__fileno integer"
        cursor.execute(q)
        q = "update mapping set base__fileno=0"
        cursor.execute(q)
    db.commit()
    # smartfilters
    try:
        cursor.execute("select * from smartfilters")
    except:
        q = "create table smartfilters (name text, definition text)"
        cursor.execute(q)
        db.commit()
    # info
    q = 'select colval from info where colkey="_converter_format"'
    cursor.execute(q)
    r = cursor.fetchone()
    if r is None:
        q = 'insert into info values ("_converter_format", "")'
        cursor.execute(q)
    q = 'select colval from info where colkey="_mapper"'
    cursor.execute(q)
    r = cursor.fetchone()
    if r is None:
        q = 'select colval from info where colkey="Gene mapper"'
        cursor.execute(q)
        r = cursor.fetchone()
        hg38ver = r[0].split("(")[1].strip(")")
        q = 'insert into info values ("_mapper", "hg38:{}")'.format(hg38ver)
        cursor.execute(q)
    q = 'select colval from info where colkey="_input_paths"'
    cursor.execute(q)
    r = cursor.fetchone()
    if r is None:
        q = 'select colval from info where colkey="Input file name"'
        cursor.execute(q)
        r = cursor.fetchone()
        ips = r[0].split(";")
        input_paths = {}
        for i in range(len(ips)):
            input_paths[i] = ips[i]
        q = 'insert into info values ("_input_paths", "{}")'.format(
            json.dumps(input_paths).replace('"', "'")
        )
        cursor.execute(q)
    q = 'select colval from info where colkey="_annotator_desc"'
    cursor.execute(q)
    r = cursor.fetchone()
    if r is None:
        q = 'insert into info values ("_annotator_desc", "{}")'
        cursor.execute(q)
    q = 'update info set colval="1.5.0" where colkey="open-cravat"'
    cursor.execute(q)
    db.commit()
    cursor.close()
    db.close()


def migrate_result_150_to_151(dbpath):
    db = sqlite3.connect(dbpath)
    cursor = db.cursor()
    cursor.execute('update info set colval="1.5.1" where colkey="open-cravat"')
    db.commit()
    cursor.close()
    db.close()


def migrate_result_151_to_152(dbpath):
    db = sqlite3.connect(dbpath)
    cursor = db.cursor()
    cursor.execute('update info set colval="1.5.2" where colkey="open-cravat"')
    db.commit()
    cursor.close()
    db.close()


def migrate_result_152_to_153(dbpath):
    db = sqlite3.connect(dbpath)
    cursor = db.cursor()
    q = 'select col_def from variant_header where col_name="base__coding"'
    cursor.execute(q)
    r = cursor.fetchone()
    coldef = json.loads(r[0])
    coldef["categories"] = ["Yes"]
    q = 'update variant_header set col_def=? where col_name="base__coding"'
    cursor.execute(q, [json.dumps(coldef)])
    cursor.execute('update info set colval="1.5.3" where colkey="open-cravat"')
    db.commit()
    cursor.close()
    db.close()


def migrate_result_153_to_160(dbpath):
    db = sqlite3.connect(dbpath)
    c = db.cursor()
    c.execute('update info set colval="1.6.0" where colkey="open-cravat"')


def migrate_result_160_to_161(dbpath):
    db = sqlite3.connect(dbpath)
    c = db.cursor()
    c.execute('update info set colval="1.6.1" where colkey="open-cravat"')


def migrate_result_161_to_170(dbpath):
    db = sqlite3.connect(dbpath)
    c = db.cursor()
    for level in ("gene", "mapping", "sample", "variant"):
        c.execute(
            f"create unique index unq_{level}_annotator_name on {level}_annotator (name)"
        )
        c.execute(
            f"create unique index unq_{level}_header_col_name on {level}_header (col_name)"
        )
        if level in ("gene", "variant"):
            c.execute(
                f"create unique index unq_{level}_reportsub_module on {level}_reportsub (module)"
            )
    c.execute("create unique index unq_smartfilters_name on smartfilters (name)")
    c.execute("create unique index unq_info_colkey on info (colkey)")
    c.execute('update info set colval="1.7.0" where colkey="open-cravat"')


def migrate_result_170_to_180(dbpath):
    db = sqlite3.connect(dbpath)
    c = db.cursor()
    c.execute('update info set colval="1.8.0" where colkey="open-cravat"')
    db.commit()


def migrate_result_180_to_181(dbpath):
    db = sqlite3.connect(dbpath)
    c = db.cursor()
    try:
        c.execute("alter table variant add column base__cchange text")
    except:
        pass
    c.execute("update variant set base__cchange=null")
    c.execute(
        'insert or replace into variant_header values ("base__cchange", \'{"index": 10, "name": "base__cchange", "title": "cDNA change", "type": "string", "categories": [], "width": 70, "desc": null, "hidden": false, "category": null, "filterable": false, "link_format": null, "genesummary": false}\')'
    )
    c.execute(
        'update variant_header set col_def=\'{"index": 11, "name": "base__achange", "title": "Protein Change", "type": "string", "categories": [], "width": 55, "desc": null, "hidden": false, "category": null, "filterable": false, "link_format": null, "genesummary": false}\' where col_name="base__achange"'
    )
    c.execute(
        'update variant_header set col_def=\'{"index": 12, "name": "base__all_mappings", "title": "All Mappings", "type": "string", "categories": [], "width": 100, "desc": null, "hidden": true, "category": null, "filterable": false, "link_format": null, "genesummary": false}\' where col_name="base__all_mappings"'
    )
    c.execute(
        'update variant_header set col_def=\'{"index": null, "name": "tagsampler__numsample", "title": "Sample Count", "type": "int", "categories": [], "width": 55, "desc": "Number of samples which contain the variant.", "hidden": true, "category": null, "filterable": false, "link_format": null, "genesummary": false}\' where col_name="tagsampler__numsample"'
    )
    c.execute(
        'update variant_header set col_def=\'{"index": null, "name": "tagsampler__samples", "title": "Samples", "type": "string", "categories": ["s0", "s1", "s2", "s3", "s4"], "width": 65, "desc": "Samples which contain the variant.", "hidden": false, "category": "multi", "filterable": true, "link_format": null, "genesummary": false}\' where col_name="tagsampler__samples"'
    )
    c.execute(
        'update variant_header set col_def=\'{"index": null, "name": "tagsampler__tags", "title": "Tags", "type": "string", "categories": [], "width": 65, "desc": "Variant tags from the input file.", "hidden": true, "category": null, "filterable": true, "link_format": null, "genesummary": false}\' where col_name="tagsampler__tags"'
    )
    c.execute(
        (
            "update variant_reportsub set subdict="
            '\'{"so": {"PTR": "processed_transcript", "TU1": "transcribed_unprocessed_pseudogene", "UNP": "unprocessed_pseudogene", '
            '"MIR": "miRNA", "LNC": "lnc_RNA", "PPS": "processed_pseudogene", "SNR": "snRNA", "TPR": "transcribed_processed_pseudogene", '
            '"RTI": "retained_intron", "NMD": "NMD_transcript_variant", "MCR": "misc_RNA", "UNT": "unconfirmed_transcript", '
            '"PSE": "pseudogene", "TU2": "transcribed_unitary_pseudogene", "NSD": "NSD_transcript", "SNO": "snoRNA", "SCA": "scaRNA", '
            '"PRR": "pseudogene_rRNA", "UPG": "unitary_pseudogene", "PPG": "polymorphic_pseudogene", "RRN": "rRNA", "IVP": "IG_V_pseudogene", '
            '"RIB": "ribozyme", "SRN": "sRNA", "TVG": "TR_V_gene", "TVP": "TR_V_pseudogene", "TDG": "TR_D_gene", "TJG": "TR_J_gene", '
            '"TCG": "TR_C_gene", "TJP": "TR_J_pseudogene", "ICG": "IG_C_gene", "ICP": "IG_C_pseudogene", "IJG": "IG_J_gene", '
            '"IJP": "IG_J_pseudogene", "IDG": "IG_D_gene", "IVG": "IG_V_gene", "IGP": "IG_pseudogene", "TPP": "translated_processed_pseudogene", '
            '"SCR": "scRNA", "VLR": "vault_RNA", "TUP": "translated_unprocessed_pseudogene", "MTR": "Mt_tRNA", "MRR": "Mt_rRNA", '
            '"2KD": "2kb_downstream_variant", "2KU": "2kb_upstream_variant", "UT3": "3_prime_UTR_variant", "UT5": "5_prime_UTR_variant", '
            '"INT": "intron_variant", "UNK": "unknown", "SYN": "synonymous_variant", "MRT": "start_retained_variant", "STR": "stop_retained_variant", '
            '"MIS": "missense_variant", "CSS": "complex_substitution", "STL": "stop_lost", "SPL": "splice_site_variant", "STG": "stop_gained", '
            '"FSD": "frameshift_truncation", "FSI": "frameshift_elongation", "INI": "inframe_insertion", "IND": "inframe_deletion", '
            '"MLO": "start_lost", "EXL": "exon_loss_variant", "TAB": "transcript_ablation"}, "all_so": {"PTR": "processed_transcript", '
            '"TU1": "transcribed_unprocessed_pseudogene", "UNP": "unprocessed_pseudogene", "MIR": "miRNA", "LNC": "lnc_RNA", '
            '"PPS": "processed_pseudogene", "SNR": "snRNA", "TPR": "transcribed_processed_pseudogene", "RTI": "retained_intron", '
            '"NMD": "NMD_transcript_variant", "MCR": "misc_RNA", "UNT": "unconfirmed_transcript", "PSE": "pseudogene", '
            '"TU2": "transcribed_unitary_pseudogene", "NSD": "NSD_transcript", "SNO": "snoRNA", "SCA": "scaRNA", "PRR": "pseudogene_rRNA", '
            '"UPG": "unitary_pseudogene", "PPG": "polymorphic_pseudogene", "RRN": "rRNA", "IVP": "IG_V_pseudogene", "RIB": "ribozyme", '
            '"SRN": "sRNA", "TVG": "TR_V_gene", "TVP": "TR_V_pseudogene", "TDG": "TR_D_gene", "TJG": "TR_J_gene", "TCG": "TR_C_gene", '
            '"TJP": "TR_J_pseudogene", "ICG": "IG_C_gene", "ICP": "IG_C_pseudogene", "IJG": "IG_J_gene", "IJP": "IG_J_pseudogene", '
            '"IDG": "IG_D_gene", "IVG": "IG_V_gene", "IGP": "IG_pseudogene", "TPP": "translated_processed_pseudogene", "SCR": "scRNA", '
            '"VLR": "vault_RNA", "TUP": "translated_unprocessed_pseudogene", "MTR": "Mt_tRNA", "MRR": "Mt_rRNA", "2KD": "2kb_downstream_variant", '
            '"2KU": "2kb_upstream_variant", "UT3": "3_prime_UTR_variant", "UT5": "5_prime_UTR_variant", "INT": "intron_variant", '
            '"UNK": "unknown", "SYN": "synonymous_variant", "MRT": "start_retained_variant", "STR": "stop_retained_variant", '
            '"MIS": "missense_variant", "CSS": "complex_substitution", "STL": "stop_lost", "SPL": "splice_site_variant", "STG": "stop_gained", '
            '"FSD": "frameshift_truncation", "FSI": "frameshift_elongation", "INI": "inframe_insertion", "IND": "inframe_deletion", '
            '"MLO": "start_lost", "EXL": "exon_loss_variant", "TAB": "transcript_ablation"}, '
            '"all_mappings": {"PTR": "processed_transcript", "TU1": "transcribed_unprocessed_pseudogene", "UNP": "unprocessed_pseudogene", '
            '"MIR": "miRNA", "LNC": "lnc_RNA", "PPS": "processed_pseudogene", "SNR": "snRNA", "TPR": "transcribed_processed_pseudogene", '
            '"RTI": "retained_intron", "NMD": "NMD_transcript_variant", "MCR": "misc_RNA", "UNT": "unconfirmed_transcript", "PSE": "pseudogene", '
            '"TU2": "transcribed_unitary_pseudogene", "NSD": "NSD_transcript", "SNO": "snoRNA", "SCA": "scaRNA", "PRR": "pseudogene_rRNA", '
            '"UPG": "unitary_pseudogene", "PPG": "polymorphic_pseudogene", "RRN": "rRNA", "IVP": "IG_V_pseudogene", "RIB": "ribozyme", '
            '"SRN": "sRNA", "TVG": "TR_V_gene", "TVP": "TR_V_pseudogene", "TDG": "TR_D_gene", "TJG": "TR_J_gene", "TCG": "TR_C_gene", '
            '"TJP": "TR_J_pseudogene", "ICG": "IG_C_gene", "ICP": "IG_C_pseudogene", "IJG": "IG_J_gene", "IJP": "IG_J_pseudogene", '
            '"IDG": "IG_D_gene", "IVG": "IG_V_gene", "IGP": "IG_pseudogene", "TPP": "translated_processed_pseudogene", "SCR": "scRNA", '
            '"VLR": "vault_RNA", "TUP": "translated_unprocessed_pseudogene", "MTR": "Mt_tRNA", "MRR": "Mt_rRNA", "2KD": "2kb_downstream_variant", '
            '"2KU": "2kb_upstream_variant", "UT3": "3_prime_UTR_variant", "UT5": "5_prime_UTR_variant", "INT": "intron_variant", '
            '"UNK": "unknown", "SYN": "synonymous_variant", "MRT": "start_retained_variant", "STR": "stop_retained_variant", '
            '"MIS": "missense_variant", "CSS": "complex_substitution", "STL": "stop_lost", "SPL": "splice_site_variant", '
            '"STG": "stop_gained", "FSD": "frameshift_truncation", "FSI": "frameshift_elongation", "INI": "inframe_insertion", '
            '"IND": "inframe_deletion", "MLO": "start_lost", "EXL": "exon_loss_variant", "TAB": "transcript_ablation"}, '
            '"coding": {"Y": "Yes"}}\' where module="base"'
        )
    )
    c.execute(
        (
            "update gene_reportsub set subdict="
            '\'{"so": {"PTR": "processed_transcript", "TU1": "transcribed_unprocessed_pseudogene", "UNP": "unprocessed_pseudogene", '
            '"MIR": "miRNA", "LNC": "lnc_RNA", "PPS": "processed_pseudogene", "SNR": "snRNA", "TPR": "transcribed_processed_pseudogene", '
            '"RTI": "retained_intron", "NMD": "NMD_transcript_variant", "MCR": "misc_RNA", "UNT": "unconfirmed_transcript", '
            '"PSE": "pseudogene", "TU2": "transcribed_unitary_pseudogene", "NSD": "NSD_transcript", "SNO": "snoRNA", "SCA": "scaRNA", '
            '"PRR": "pseudogene_rRNA", "UPG": "unitary_pseudogene", "PPG": "polymorphic_pseudogene", "RRN": "rRNA", "IVP": "IG_V_pseudogene", '
            '"RIB": "ribozyme", "SRN": "sRNA", "TVG": "TR_V_gene", "TVP": "TR_V_pseudogene", "TDG": "TR_D_gene", "TJG": "TR_J_gene", '
            '"TCG": "TR_C_gene", "TJP": "TR_J_pseudogene", "ICG": "IG_C_gene", "ICP": "IG_C_pseudogene", "IJG": "IG_J_gene", '
            '"IJP": "IG_J_pseudogene", "IDG": "IG_D_gene", "IVG": "IG_V_gene", "IGP": "IG_pseudogene", "TPP": "translated_processed_pseudogene", '
            '"SCR": "scRNA", "VLR": "vault_RNA", "TUP": "translated_unprocessed_pseudogene", "MTR": "Mt_tRNA", "MRR": "Mt_rRNA", '
            '"2KD": "2kb_downstream_variant", "2KU": "2kb_upstream_variant", "UT3": "3_prime_UTR_variant", "UT5": "5_prime_UTR_variant", '
            '"INT": "intron_variant", "UNK": "unknown", "SYN": "synonymous_variant", "MRT": "start_retained_variant", "STR": "stop_retained_variant", '
            '"MIS": "missense_variant", "CSS": "complex_substitution", "STL": "stop_lost", "SPL": "splice_site_variant", "STG": "stop_gained", '
            '"FSD": "frameshift_truncation", "FSI": "frameshift_elongation", "INI": "inframe_insertion", "IND": "inframe_deletion", '
            '"MLO": "start_lost", "EXL": "exon_loss_variant", "TAB": "transcript_ablation"}, "all_so": {"PTR": "processed_transcript", '
            '"TU1": "transcribed_unprocessed_pseudogene", "UNP": "unprocessed_pseudogene", "MIR": "miRNA", "LNC": "lnc_RNA", '
            '"PPS": "processed_pseudogene", "SNR": "snRNA", "TPR": "transcribed_processed_pseudogene", "RTI": "retained_intron", '
            '"NMD": "NMD_transcript_variant", "MCR": "misc_RNA", "UNT": "unconfirmed_transcript", "PSE": "pseudogene", '
            '"TU2": "transcribed_unitary_pseudogene", "NSD": "NSD_transcript", "SNO": "snoRNA", "SCA": "scaRNA", "PRR": "pseudogene_rRNA", '
            '"UPG": "unitary_pseudogene", "PPG": "polymorphic_pseudogene", "RRN": "rRNA", "IVP": "IG_V_pseudogene", "RIB": "ribozyme", '
            '"SRN": "sRNA", "TVG": "TR_V_gene", "TVP": "TR_V_pseudogene", "TDG": "TR_D_gene", "TJG": "TR_J_gene", "TCG": "TR_C_gene", '
            '"TJP": "TR_J_pseudogene", "ICG": "IG_C_gene", "ICP": "IG_C_pseudogene", "IJG": "IG_J_gene", "IJP": "IG_J_pseudogene", '
            '"IDG": "IG_D_gene", "IVG": "IG_V_gene", "IGP": "IG_pseudogene", "TPP": "translated_processed_pseudogene", "SCR": "scRNA", '
            '"VLR": "vault_RNA", "TUP": "translated_unprocessed_pseudogene", "MTR": "Mt_tRNA", "MRR": "Mt_rRNA", "2KD": "2kb_downstream_variant", '
            '"2KU": "2kb_upstream_variant", "UT3": "3_prime_UTR_variant", "UT5": "5_prime_UTR_variant", "INT": "intron_variant", '
            '"UNK": "unknown", "SYN": "synonymous_variant", "MRT": "start_retained_variant", "STR": "stop_retained_variant", '
            '"MIS": "missense_variant", "CSS": "complex_substitution", "STL": "stop_lost", "SPL": "splice_site_variant", "STG": "stop_gained", '
            '"FSD": "frameshift_truncation", "FSI": "frameshift_elongation", "INI": "inframe_insertion", "IND": "inframe_deletion", '
            '"MLO": "start_lost", "EXL": "exon_loss_variant", "TAB": "transcript_ablation"}, '
            '"all_mappings": {"PTR": "processed_transcript", "TU1": "transcribed_unprocessed_pseudogene", "UNP": "unprocessed_pseudogene", '
            '"MIR": "miRNA", "LNC": "lnc_RNA", "PPS": "processed_pseudogene", "SNR": "snRNA", "TPR": "transcribed_processed_pseudogene", '
            '"RTI": "retained_intron", "NMD": "NMD_transcript_variant", "MCR": "misc_RNA", "UNT": "unconfirmed_transcript", "PSE": "pseudogene", '
            '"TU2": "transcribed_unitary_pseudogene", "NSD": "NSD_transcript", "SNO": "snoRNA", "SCA": "scaRNA", "PRR": "pseudogene_rRNA", '
            '"UPG": "unitary_pseudogene", "PPG": "polymorphic_pseudogene", "RRN": "rRNA", "IVP": "IG_V_pseudogene", "RIB": "ribozyme", '
            '"SRN": "sRNA", "TVG": "TR_V_gene", "TVP": "TR_V_pseudogene", "TDG": "TR_D_gene", "TJG": "TR_J_gene", "TCG": "TR_C_gene", '
            '"TJP": "TR_J_pseudogene", "ICG": "IG_C_gene", "ICP": "IG_C_pseudogene", "IJG": "IG_J_gene", "IJP": "IG_J_pseudogene", '
            '"IDG": "IG_D_gene", "IVG": "IG_V_gene", "IGP": "IG_pseudogene", "TPP": "translated_processed_pseudogene", "SCR": "scRNA", '
            '"VLR": "vault_RNA", "TUP": "translated_unprocessed_pseudogene", "MTR": "Mt_tRNA", "MRR": "Mt_rRNA", "2KD": "2kb_downstream_variant", '
            '"2KU": "2kb_upstream_variant", "UT3": "3_prime_UTR_variant", "UT5": "5_prime_UTR_variant", "INT": "intron_variant", '
            '"UNK": "unknown", "SYN": "synonymous_variant", "MRT": "start_retained_variant", "STR": "stop_retained_variant", '
            '"MIS": "missense_variant", "CSS": "complex_substitution", "STL": "stop_lost", "SPL": "splice_site_variant", '
            '"STG": "stop_gained", "FSD": "frameshift_truncation", "FSI": "frameshift_elongation", "INI": "inframe_insertion", '
            '"IND": "inframe_deletion", "MLO": "start_lost", "EXL": "exon_loss_variant", "TAB": "transcript_ablation"}, '
            '"coding": {"Y": "Yes"}}\' where module="base"'
        )
    )
    c.execute('update info set colval="1.8.1" where colkey="open-cravat"')
    c.execute(
        'SELECT name FROM sqlite_master WHERE type="index" AND name="sample_idx_2"'
    )
    r = c.fetchone()
    if r is None:
        c.execute("create index sample_idx_2 on sample (base__sample_id, base__uid)")
    db.commit()


def migrate_result_201_to_210(dbpath):
    db = sqlite3.connect(dbpath)
    cursor = db.cursor()
    try:
        q = "select * from smartfilters"
        cursor.execute(q)
    except sqlite3.OperationalError:
        return
    sfs = {row[0]: json.loads(row[1]) for row in cursor}
    cols_to_index = set()
    for sf in constants.base_smartfilters:
        cols_to_index |= util.filter_affected_cols(sf["filter"])
    for module_sfs in sfs.values():
        for sf in module_sfs:
            cols_to_index |= util.filter_affected_cols(sf["filter"])
    cursor.execute("pragma table_info(variant)")
    variant_cols = {row[1] for row in cursor}
    cursor.execute("pragma table_info(gene)")
    gene_cols = {row[1] for row in cursor}
    for col in cols_to_index:
        if col in variant_cols:
            q = f'select name from sqlite_master where type="index" and name="sf_variant_{col}"'
            cursor.execute(q)
            r = cursor.fetchone()
            if r is None:
                q = f"create index sf_variant_{col} on variant ({col})"
                cursor.execute(q)
        if col in gene_cols:
            q = f'select name from sqlite_master where type="index" and name="sf_gene_{col}"'
            cursor.execute(q)
            r = cursor.fetchone()
            if r is None:
                q = f"create index sf_gene_{col} on gene ({col})"
                cursor.execute(q)
    db.commit()


migrate_functions = {}
migrate_functions["1.4.5"] = migrate_result_144_to_145
migrate_functions["1.5.0"] = migrate_result_145_to_150
migrate_functions["1.5.1"] = migrate_result_150_to_151
migrate_functions["1.5.2"] = migrate_result_151_to_152
migrate_functions["1.5.3"] = migrate_result_152_to_153
migrate_functions["1.6.0"] = migrate_result_153_to_160
migrate_functions["1.6.1"] = migrate_result_160_to_161
migrate_functions["1.7.0"] = migrate_result_161_to_170
migrate_functions["1.8.0"] = migrate_result_170_to_180
migrate_functions["2.0.1"] = migrate_result_180_to_181
migrate_functions["2.1.0"] = migrate_result_201_to_210
migrate_checkpoints = [LooseVersion(v) for v in list(migrate_functions.keys())]
migrate_checkpoints.sort()
# max_version_supported_for_migration = max(migrate_checkpoints)
max_version_supported_for_migration = LooseVersion("1.7.0")


def can_migrate_result(result_version):
    return LooseVersion(result_version) < max_version_supported_for_migration

def migrate_result(args):
    def get_dbpaths(dbpaths, path):
        for fn in os.listdir(path):
            p = os.path.join(path, fn)
            if os.path.isdir(p) and args.recursive:
                get_dbpaths(dbpaths, p)
            else:
                if fn.endswith(".sqlite"):
                    dbpaths.append(p)

    dbpath = args.dbpath
    if os.path.exists(dbpath) == False:
        print("[{}] does not exist.".format(dbpath))
        return
    if os.path.isdir(dbpath):
        dbpaths = []
        get_dbpaths(dbpaths, dbpath)
    else:
        dbpaths = [dbpath]
    print("Result database files to convert are:")
    for dbpath in dbpaths:
        print("    " + dbpath)
    for dbpath in dbpaths:
        print("converting [{}]...".format(dbpath))
        global migrate_checkpoints
        try:
            db = sqlite3.connect(dbpath)
            cursor = db.cursor()
        except:
            print("  [{}] is not open-cravat result DB.".format(dbpath))
            continue
        try:
            q = 'select colval from info where colkey="open-cravat"'
            cursor.execute(q)
            r = cursor.fetchone()
            if r is None:
                print("  Result DB is too old for migration.")
                continue
            else:
                oc_ver = LooseVersion(r[0])
        except:
            print(
                "  [{}] is not open-cravat result DB or too old for migration.".format(
                    dbpath
                )
            )
            continue
        if oc_ver >= max(migrate_checkpoints):
            print(f"  OpenCRAVAT version of {oc_ver} does not need migration.")
            continue
        elif oc_ver < LooseVersion("1.4.4"):
            print(f"  OpenCRAVAT version of {oc_ver} is not supported for migration.")
            continue
        try:
            if args.backup:
                bak_path = dbpath + ".bak"
                print("  making backup copy [{}]...".format(bak_path))
                shutil.copy(dbpath, bak_path)
            ver_idx = None
            for i, target_ver in enumerate(migrate_checkpoints):
                if oc_ver < target_ver:
                    ver_idx = i
                    break
            if ver_idx is None:
                continue
            for target_ver in migrate_checkpoints[ver_idx:]:
                target_ver = str(target_ver)
                print(f"  converting open-cravat version to {target_ver}...")
                migrate_functions[target_ver](dbpath)
                with sqlite3.connect(dbpath) as db:
                    db.execute(
                        'update info set colval=? where colkey="open-cravat"',
                        (target_ver,),
                    )
        except:
            traceback.print_exc()
            print("  converting [{}] was not successful.".format(dbpath))


def result2gui(args):
    dbpath = args.path
    user = args.user
    jobs_dir = Path(au.get_jobs_dir())
    user_dir = jobs_dir / user
    if not user_dir.is_dir():
        exit(f"User {user} not found")
    attempts = 0
    while (
        True
    ):  # TODO this will currently overwrite if called in parallel. is_dir check and creation is not atomic
        job_id = datetime.datetime.now().strftime(r"%y%m%d-%H%M%S")
        job_dir = user_dir / job_id
        if not job_dir.is_dir():
            break
        else:
            attempts += 1
            time.sleep(1)
        if attempts >= 5:
            exit(
                "Could not acquire a job id. Too many concurrent job submissions. Wait, or reduce submission frequency."
            )
    job_dir.mkdir()
    new_dbpath = job_dir / dbpath.name
    shutil.copyfile(dbpath, new_dbpath)
    log_path = dbpath.with_suffix(".log")
    if log_path.exists():
        shutil.copyfile(log_path, job_dir / log_path.name)
    err_path = dbpath.with_suffix(".err")
    if err_path.exists():
        shutil.copyfile(err_path, job_dir / err_path.name)
    status_path = dbpath.with_suffix(".status.json")
    if status_path.exists():
        shutil.copyfile(status_path, job_dir / status_path.name)
    else:
        statusd = status_from_db(new_dbpath)
        new_status_path = job_dir / status_path.name
        with new_status_path.open("w") as wf:
            json.dump(statusd, wf, indent=2, sort_keys=True)


def variant_id(chrom, pos, ref, alt):
    return chrom + ':' + str(pos) + ':' + ref + ':' + alt

def showsqliteinfo(args):
    dbpaths = args.paths
    info_lines = []
    for dbpath in dbpaths:
        print(f'# SQLite file:\n{dbpath}')
        conn = sqlite3.connect(dbpath)
        c = conn.cursor()
        c.execute('select colval from info where colkey="_input_paths"')
        input_paths = json.loads(c.fetchone()[0].replace("'", '"'))
        print(f'\n# Input files:')
        for p in input_paths.values():
            print(f'{p}')
        max_lens = [len("# Name"), len("Title")]
        c.execute('select col_name, col_def from variant_header')
        rs = c.fetchall()
        for r in rs:
            col_name, col_def = r
            col_def = json.loads(col_def)
            max_lens[0] = max(max_lens[0], len(col_name))
            max_lens[1] = max(max_lens[1], len(col_def["title"]))
            info_lines.append([col_name, col_def["title"], str(col_def["type"])])
        c.execute('select col_name, col_def from gene_header')
        rs = c.fetchall()
        for r in rs:
            col_name, col_def = r
            col_def = json.loads(col_def)
            max_lens[0] = max(max_lens[0], len(col_name))
            max_lens[1] = max(max_lens[1], len(col_def["title"]))
            info_lines.append([col_name, col_def["title"], str(col_def["type"])])
        print(f'\n# Output columns')
        print(f'{"# Name".ljust(max_lens[0])}\t{"Title".ljust(max_lens[1])}\tType')
        for line in info_lines:
            print(f'{line[0].ljust(max_lens[0])}\t{line[1].ljust(max_lens[1])}\t{line[2]}')
        c.close()
        conn.close()

def mergesqlite_readonly_uri(dbpath):
    """Builds a `file:...?mode=ro` URI connection string for a connection
    that will only ever read one of the *original* input dbs - never a
    shard or output file this merge writes to, which are still opened
    with a plain sqlite3.connect(path). mode=ro just enforces (and
    documents) what every one of these call sites already only does;
    it's not immutable=1 - that would additionally skip SQLite's own
    locking, which assumes the file can't change out from under the
    connection for as long as it's open, a promise this merge can't make
    on its own (nothing stops some other process from rewriting an input
    db mid-merge). mode=ro alone still takes the normal SHARED lock,
    which doesn't block other concurrent readers anyway - multiple shard
    workers legitimately do read the same input db at the same time.
    Percent-encodes the absolute path so a real `?`/`#`/space in a
    filename can't be misread as the start of the URI's query string or
    fragment."""
    return f'file:{urllib.parse.quote(os.path.abspath(dbpath))}?mode=ro'


def mergesqlite_check_info(dbpath):
    """Collects the header columns, annotator module versions, and sample
    ids used by a result db, for the pre-merge consistency checks in
    mergesqlite()."""
    conn = sqlite3.connect(mergesqlite_readonly_uri(dbpath), uri=True)
    c = conn.cursor()
    info = {}
    for table in ["variant", "gene", "sample", "mapping"]:
        # Order matters here (no sorted()): the merge loop in mergesqlite()
        # reads and writes rows positionally, in this same rowid order, so
        # two dbs with identical column names but a different physical
        # order must be treated as a mismatch, not silently accepted.
        c.execute(f'select col_name from {table}_header order by rowid')
        info[table] = [r[0] for r in c.fetchall()]
    for annot_table, sql_table in [("variant_annotators", "variant_annotator"),
                                    ("gene_annotators", "gene_annotator")]:
        c.execute(f'select name, version from {sql_table}')
        info[annot_table] = {r[0]: r[1] for r in c.fetchall()}
    c.execute('select distinct base__sample_id from sample')
    # key= tolerates a stray NULL base__sample_id mixed in with strings
    # (plain sorted() raises TypeError comparing None to str) - possible
    # on a db that hasn't been through tagsampler's setup(), which is
    # what normally normalizes nulls to "no-sample".
    info["sample_ids"] = sorted({r[0] for r in c.fetchall()}, key=lambda v: (v is None, v))
    # _converter_format ("vcf" vs. anything else) gates whether vcfinfo or
    # varmeta recomputes on merge (their check()s are each other's
    # opposite on this key), so a mismatch across inputs needs to be
    # caught pre-merge same as the checks above - not left to silently
    # pick db1's format. Absent on pre-migration dbs (see mergesqlite's
    # sibling upgrade-in-place code), so tolerate a missing row.
    c.execute('select colval from info where colkey="_converter_format"')
    r = c.fetchone()
    info["converter_format"] = r[0] if r is not None else ""
    c.close()
    conn.close()
    return info

def mergesqlite_parse_path_arg(raw):
    """Parses a `path` or `path:label` positional arg for mergesqlite.
    A label is only recognized when the part before the last ':' exists
    as a file and the raw string as a whole does not (so plain paths
    with no label, including Windows drive letters, pass through as-is).
    Returns (path, label), label is None when no label was given."""
    raw = str(raw)
    if ':' in raw and not os.path.exists(raw):
        maybe_path, maybe_label = raw.rsplit(':', 1)
        if maybe_label and os.path.exists(maybe_path):
            return maybe_path, maybe_label
    return raw, None

def mergesqlite_drop_columns(conn, table, columns):
    """Drops `columns` from `table`. Uses ALTER TABLE ... DROP COLUMN
    (SQLite >= 3.35.0, released March 2021) when the linked SQLite
    supports it, and otherwise falls back to a temp-table-and-rename:
    recreate the table from a SELECT of the columns being kept (already
    the pattern filtersqlite_async() uses for whole-table copies), then
    replay every index whose columns aren't among those being dropped.
    The stdlib sqlite3 module links the system libsqlite3 on Linux, so
    the DROP COLUMN floor isn't guaranteed merely by open-cravat's own
    Python version requirement.

    Either way, any index covering a column being dropped has to go
    first: SQLite refuses ALTER TABLE ... DROP COLUMN on an indexed
    column, and such an index would reference a nonexistent column
    afterward anyway, so it's simply not recreated in the fallback path
    either."""
    if not columns:
        return
    c = conn.cursor()
    cols_to_drop = set(columns)
    c.execute(
        "select name, sql from sqlite_master where type='index' and tbl_name=?",
        (table,),
    )
    index_defs = [(name, sql) for name, sql in c.fetchall() if sql is not None]
    touching_index_names = set()
    for index_name, sql in index_defs:
        c.execute(f'pragma index_info("{index_name}")')
        idx_cols = {r[2] for r in c.fetchall()}
        if (idx_cols & cols_to_drop) or None in idx_cols:
            touching_index_names.add(index_name)  # touches a dropped column (or is an expression index)
    if sqlite3.sqlite_version_info >= (3, 35, 0):
        for index_name in touching_index_names:
            c.execute(f'drop index "{index_name}"')
        for col in columns:
            c.execute(f'alter table {table} drop column "{col}"')
        return
    c.execute(f"pragma table_info({table})")
    keep_cols = [r[1] for r in c.fetchall() if r[1] not in cols_to_drop]
    keep_index_sqls = [sql for name, sql in index_defs if name not in touching_index_names]
    tmp_table = f"{table}__mergesqlite_drop_tmp"
    c.execute(f'alter table {table} rename to {tmp_table}')
    col_list_sql = ", ".join(f'"{col}"' for col in keep_cols)
    c.execute(f'create table {table} as select {col_list_sql} from {tmp_table}')
    c.execute(f'drop table {tmp_table}')
    for sql in keep_index_sqls:
        c.execute(sql)


def mergesqlite_is_local_postaggregator(module_name):
    info = au.get_local_module_info(module_name)
    return info is not None and info.type == "postaggregator"


def mergesqlite_strip_postaggregator_columns(conn):
    """Removes every postaggregator-authored column, and its header,
    annotator, and reportsub rows, from a merged db - so that postagg
    recompute (or `--skip-postaggregator`) always starts from a clean
    slate. Only modules locally installed with type "postaggregator" are
    touched; "base" and real annotator-authored columns are left alone.

    Strip-after-copy, not never-copy: mergesqlite()'s structural merge
    stays completely unaware that postaggregator recompute exists - it
    copies every column the same generic way regardless of origin, and
    this is a separate, independently testable pass run afterward."""
    c = conn.cursor()
    c.execute("select name from sqlite_master where type='table'")
    existing_tables = {r[0] for r in c.fetchall()}
    for level in ["variant", "gene", "sample", "mapping"]:
        annot_table = f"{level}_annotator"
        header_table = f"{level}_header"
        if annot_table not in existing_tables or header_table not in existing_tables:
            # Postaggregators only ever run at the variant/gene level
            # (constants.LEVELS), so real result dbs always have
            # sample_annotator/mapping_annotator with no postaggregator
            # rows in them; tolerate a db that lacks those tables entirely.
            continue
        c.execute(f"select name from {annot_table}")
        postagg_names = [
            r[0] for r in c.fetchall() if mergesqlite_is_local_postaggregator(r[0])
        ]
        if not postagg_names:
            continue
        c.execute(f"select col_name from {header_table} order by rowid")
        all_cols = [r[0] for r in c.fetchall()]
        cols_to_drop = [
            col for col in all_cols
            if any(col.startswith(name + "__") for name in postagg_names)
        ]
        mergesqlite_drop_columns(conn, level, cols_to_drop)
        for name in postagg_names:
            c.execute(
                f"delete from {header_table} where col_name like ?", (name + "__%",)
            )
            c.execute(f"delete from {annot_table} where name = ?", (name,))
        if level in ("variant", "gene"):
            reportsub_table = f"{level}_reportsub"
            c.executemany(
                f"delete from {reportsub_table} where module = ?",
                [(name,) for name in postagg_names],
            )
    conn.commit()


def mergesqlite_parse_module_options(opt_strs):
    """Parses `--module-option module_name.key=value` strings into
    {module_name: {key: value}}, standing in for the `--confs` a full
    `Cravat` run would build. Reimplements the parsing half of
    cravat_class.py's process_module_options() standalone (same syntax,
    same forgiving "warn and skip" handling of a malformed entry) - this
    tool doesn't drive a full Cravat instance, so there's no ConfigLoader
    for `--module-option` to feed into. `-c`/`--cs` (base conf file /
    inline config-string overrides) are deliberately not supported here:
    this is a narrow, single-purpose recompute tool, not a full pipeline
    run, and `--module-option` covers every case postagg recompute needs."""
    module_options = {}
    for opt_str in opt_strs or []:
        toks = opt_str.split("=")
        if len(toks) != 2:
            print(
                f'Ignoring invalid module option "{opt_str}". '
                "module-option should be module_name.key=value."
            )
            continue
        k, v = toks
        if k.count(".") != 1:
            print(
                f'Ignoring invalid module option "{opt_str}". '
                "module-option should be module_name.key=value."
            )
            continue
        module_name, key = k.split(".")
        module_options.setdefault(module_name, {})[key] = v
    return module_options


def mergesqlite_status_json_path(outpath):
    """The .status.json path StatusWriter writes alongside `outpath` for
    the postaggregators re-run against it - factored out so mergesqlite()
    can find and remove it too if the recompute pass fails partway."""
    output_dir = os.path.dirname(os.path.abspath(outpath))
    run_name = os.path.basename(outpath)
    if run_name.endswith(".sqlite"):
        run_name = run_name[: -len(".sqlite")]
    return os.path.join(output_dir, run_name + ".status.json")


def mergesqlite_run_postaggregators(outpath, module_names, module_options):
    """Re-runs `module_names` against the merged db at `outpath`, using
    the same in-process mechanism the main pipeline already uses
    (cravat_class.py's run_postaggregators): util.load_class(script_path,
    "CravatPostAggregator"), instantiate with -d/-n (+ --confs), a
    StatusWriter, call .run(). No reimplementation of module logic.

    For the --parallel path's vcfinfo shards, the cohort-wide multi_sample
    override (see OC-833 production decision 5) travels through
    `module_options["vcfinfo"]["multi_sample"]` like any other
    --module-option - vcfinfo.py's own setup() reads it from self.confs.
    No special-casing needed here; this function treats every
    postaggregator identically."""
    # Deferred import: cravat_class imports cravat_util at module level
    # ("import cravat.cravat_util as cu"), so importing it back at
    # cravat_util's own module level would be circular.
    from cravat.cravat_class import StatusWriter

    output_dir = os.path.dirname(os.path.abspath(outpath))
    run_name = os.path.basename(outpath)
    if run_name.endswith(".sqlite"):
        run_name = run_name[: -len(".sqlite")]
    status_json_path = mergesqlite_status_json_path(outpath)
    with open(status_json_path, "w") as f:
        json.dump({}, f)
    status_writer = StatusWriter(status_json_path)
    for module_name in module_names:
        module = au.get_local_module_info(module_name)
        cmd = [module.script_path, "-d", output_dir, "-n", run_name]
        conf = module_options.get(module_name)
        if conf:
            confs = json.dumps(conf)
            confs = "'" + confs.replace("'", '"') + "'"
            cmd.extend(["--confs", confs])
        post_agg_cls = util.load_class(module.script_path, "CravatPostAggregator")
        post_agg = post_agg_cls(cmd, status_writer)
        if post_agg.should_run_annotate:
            print(f'Running {module.conf.get("title", module_name)} ({module_name})...')
        post_agg.run()


def mergesqlite_validate_and_prepare(args):
    """Runs mergesqlite()'s pre-merge validation and name resolution -
    column/annotator-version/converter-format consistency checks,
    sample_id collision detection, postaggregator name resolution - shared
    by the serial and parallel merge paths so they can't drift apart on
    what counts as a valid merge. Exits (SystemExit, same as always) on
    any failure, before any output file is written."""
    if args.md is not None:
        constants.custom_modules_dir = args.md
    raw_paths = args.path
    if len(raw_paths) < 2:
        exit("Multiple sqlite file paths should be given")
    dbpaths = []
    # Parallel to dbpaths (not a dict keyed by dbpath) so that passing the
    # same physical file twice with two different :label suffixes keeps
    # both labels instead of the second overwriting the first.
    labels = []
    for raw in raw_paths:
        dbpath, label = mergesqlite_parse_path_arg(raw)
        dbpaths.append(dbpath)
        labels.append(label)
    outpath = args.outpath
    if outpath.endswith('.sqlite') == False:
        outpath = outpath + '.sqlite'
    # Checks columns and annotator modules being the same, and that no
    # sample_id collides across inputs (after any :label rename).
    all_info = {dbpath: mergesqlite_check_info(dbpath) for dbpath in dbpaths}
    base_info = all_info[dbpaths[0]]
    for dbpath in dbpaths[1:]:
        info = all_info[dbpath]
        for table in ["variant", "gene", "sample", "mapping"]:
            if base_info[table] != info[table]:
                exit(
                    f'Annotation columns mismatch ({table} table) between '
                    f'{dbpaths[0]} and {dbpath}'
                )
        for annot_table in ["variant_annotators", "gene_annotators"]:
            base_annots = base_info[annot_table]
            annots = info[annot_table]
            for name in sorted(set(base_annots) | set(annots)):
                base_version = base_annots.get(name)
                version = annots.get(name)
                if base_version != version:
                    exit(
                        f'Annotator module mismatch ({annot_table.replace("_annotators", "")} '
                        f'annotator "{name}"): version {base_version} in {dbpaths[0]} vs '
                        f'version {version} in {dbpath}'
                    )
        if not args.skip_postaggregator:
            # vcfinfo and varmeta's check()s each gate on _converter_format
            # (vcf vs. not) being the opposite of the other, and the merge
            # just carries db1's info table over unchanged - so mixing
            # converter formats would silently pick db1's format for a
            # merged sample set that isn't uniformly that format.
            base_format = base_info["converter_format"]
            fmt = info["converter_format"]
            if base_format != fmt:
                exit(
                    "Converter format mismatch between "
                    f'{dbpaths[0]} ("{base_format}") and {dbpath} ("{fmt}") - '
                    "vcfinfo/varmeta recompute would be ambiguous. Use "
                    "--skip-postaggregator to merge anyway."
                )
    sample_id_sources = {}
    for dbpath, label in zip(dbpaths, labels):
        for sid in all_info[dbpath]["sample_ids"]:
            eff_sid = f'{label}__{sid}' if label else sid
            sample_id_sources.setdefault(eff_sid, []).append(dbpath)
    collisions = {sid: paths for sid, paths in sample_id_sources.items() if len(paths) > 1}
    if collisions:
        lines = [f'  "{sid}": {", ".join(paths)}' for sid, paths in sorted(collisions.items())]
        exit(
            "Sample ID collision(s) across input files. Give the colliding "
            "file(s) a path:label suffix to disambiguate (e.g. "
            "job1.sqlite:cohortA):\n" + "\n".join(lines)
        )
    # Resolves which postaggregators (if any) will be recomputed after
    # merge, and validates -p module names now - before any output file
    # is written - to match the other pre-merge consistency checks above
    # rather than leaving a half-done output file behind on a typo.
    if args.skip_postaggregator:
        postagg_names = []
    else:
        # Defaults that aren't installed locally are silently dropped (the
        # default set can include optional modules, e.g. casecontrol,
        # that not every install has); anything explicitly named via -p
        # must exist, same as any other pre-merge consistency check here,
        # or the merge is aborted before any output file is written.
        for name in args.postaggregators:
            if not au.module_exists_local(name):
                exit(f'Postaggregator module "{name}" does not exist locally.')
        default_names = {
            name for name in constants.default_postaggregator_names
            if au.module_exists_local(name)
        }
        postagg_names = sorted(default_names | set(args.postaggregators))
    module_options = mergesqlite_parse_module_options(args.module_option)
    # casecontrol isn't supported with --parallel at all (OC-833 production
    # decision 7: its Fisher's-exact denominator is a whole-cohort scalar,
    # out of scope for per-shard recompute, and there's no requirement to
    # support it post-parallel-merge). It's only a real problem when
    # casecontrol would actually do something - its own check() gates on a
    # "cohorts" module option being given, same condition checked here - so
    # a bare default install with no cohorts conf still merges fine
    # (casecontrol just no-ops, same as it always has).
    if (
        getattr(args, "parallel", False)
        and "casecontrol" in postagg_names
        and "cohorts" in module_options.get("casecontrol", {})
    ):
        exit(
            "casecontrol is not supported with --parallel. Drop "
            "--module-option casecontrol.cohorts=... (and -p casecontrol, "
            "if given explicitly), or use the default serial merge."
        )
    return {
        "dbpaths": dbpaths,
        "labels": labels,
        "outpath": outpath,
        "all_info": all_info,
        "postagg_names": postagg_names,
        "module_options": module_options,
        "sample_id_sources": sample_id_sources,
    }


# For now, only jobs with same annotators are allowed.
def mergesqlite(args):
    prep = mergesqlite_validate_and_prepare(args)
    if getattr(args, "parallel", False):
        mergesqlite_parallel(args, prep)
    else:
        mergesqlite_serial(args, prep)


def mergesqlite_serial(args, prep):
    dbpaths = prep["dbpaths"]
    labels = prep["labels"]
    outpath = prep["outpath"]
    postagg_names = prep["postagg_names"]
    module_options = prep["module_options"]
    # Copies the first db.
    print(f'Copying {dbpaths[0]} to {outpath}...')
    shutil.copy(dbpaths[0], outpath)
    outconn = sqlite3.connect(outpath)
    outc = outconn.cursor()
    # Gets key column numbers.
    outc.execute('select col_name from variant_header order by rowid')
    cols = [r[0] for r in outc.fetchall()]
    v_chrom_colno = cols.index('base__chrom')
    v_pos_colno = cols.index('base__pos')
    v_ref_colno = cols.index('base__ref_base')
    v_alt_colno = cols.index('base__alt_base')
    outc.execute('select col_name from gene_header order by rowid')
    cols = [r[0] for r in outc.fetchall()]
    g_hugo_colno = cols.index('base__hugo')
    outc.execute('select col_name from sample_header order by rowid')
    cols = [r[0] for r in outc.fetchall()]
    s_uid_colno = cols.index('base__uid')
    s_sampleid_colno = cols.index('base__sample_id')
    outc.execute('select col_name from mapping_header order by rowid')
    cols = [r[0] for r in outc.fetchall()]
    m_uid_colno = cols.index('base__uid')
    m_fileno_colno = cols.index('base__fileno')
    outc.execute('select max(base__uid) from variant')
    new_uid = outc.fetchone()[0] + 1
    # Renames db 1's own sample_ids if it was given a :label.
    if labels[0]:
        outc.execute(
            'update sample set base__sample_id = ? || base__sample_id',
            (f'{labels[0]}__',)
        )
    # Input paths
    outc.execute('select colkey, colval from info where colkey="_input_paths"')
    input_paths = json.loads(outc.fetchone()[1].replace("'", '"'))
    new_fileno = max([int(v) for v in input_paths.keys()]) + 1
    rev_input_paths = {}
    for fileno, filepath in input_paths.items():
        rev_input_paths[filepath] = fileno
    # Makes initial hugo and variant id -> uid lists.
    outc.execute('select base__hugo from gene')
    genes = {r[0] for r in outc.fetchall()}
    outc.execute('select base__uid, base__chrom, base__pos, base__ref_base, base__alt_base from variant')
    vid_to_uid = {variant_id(r[1], r[2], r[3], r[4]): r[0] for r in outc.fetchall()}
    for dbpath, label in zip(dbpaths[1:], labels[1:]):
        print(f'Merging {dbpath}...')
        conn = sqlite3.connect(dbpath)
        c = conn.cursor()
        # Gene
        c.execute('select * from gene order by rowid')
        for r in c.fetchall():
            hugo = r[g_hugo_colno]
            if hugo in genes:
                continue
            q = f'insert into gene values ({",".join(["?" for v in range(len(r))])})'
            outc.execute(q, r)
            genes.add(hugo)
        # Variant
        uid_dic = {}
        c.execute('select * from variant order by rowid')
        for r in c.fetchall():
            vid = variant_id(r[v_chrom_colno], r[v_pos_colno], r[v_ref_colno], r[v_alt_colno])
            old_uid = r[0]
            if vid in vid_to_uid:
                # Variant already present in the merged output (annotation
                # is identical, so the redundant insert is skipped) - but
                # the uid mapping still needs recording so this variant's
                # sample/mapping rows get merged in below.
                uid_dic[old_uid] = vid_to_uid[vid]
                continue
            r = list(r)
            r[0] = new_uid
            uid_dic[old_uid] = new_uid
            vid_to_uid[vid] = new_uid
            new_uid += 1
            q = f'insert into variant values ({",".join(["?" for v in range(len(r))])})'
            outc.execute(q, r)
        # Sample
        c.execute('select * from sample order by rowid')
        for r in c.fetchall():
            uid = r[s_uid_colno]
            if uid in uid_dic:
                mapped_uid = uid_dic[uid]
                r = list(r)
                r[s_uid_colno] = mapped_uid
                if label:
                    r[s_sampleid_colno] = f'{label}__{r[s_sampleid_colno]}'
                q = f'insert into sample values ({",".join(["?" for v in range(len(r))])})'
                outc.execute(q, r)
        # File numbers
        c.execute('select colkey, colval from info where colkey="_input_paths"')
        ips = json.loads(c.fetchone()[1].replace("'", '"'))
        fileno_dic = {}
        for fileno, filepath in ips.items():
            if filepath not in rev_input_paths:
                input_paths[str(new_fileno)] = filepath
                rev_input_paths[filepath] = str(new_fileno)
                fileno_dic[int(fileno)] = new_fileno
                new_fileno += 1
            else:
                # This db's input filepath was already contributed by an
                # earlier db (or is db 1's own) - map its fileno onto the
                # fileno already assigned to that filepath.
                fileno_dic[int(fileno)] = int(rev_input_paths[filepath])
        # Mapping
        c.execute('select * from mapping order by rowid')
        for r in c.fetchall():
            uid = r[m_uid_colno]
            if uid in uid_dic:
                mapped_uid = uid_dic[uid]
                r = list(r)
                r[m_uid_colno] = mapped_uid
                r[m_fileno_colno] = fileno_dic[r[m_fileno_colno]]
                q = f'insert into mapping values ({",".join(["?" for v in range(len(r))])})'
                outc.execute(q, r)
    q = 'update info set colval=? where colkey="_input_paths"'
    outc.execute(q, [json.dumps(input_paths)])
    q = 'update info set colval=? where colkey="Input file name"'
    v = ';'.join([input_paths[str(v)] for v in sorted(input_paths.keys(), key=lambda v: int(v))])
    outc.execute(q, [v])
    outc.execute('select count(*) from variant')
    n_variants = outc.fetchone()[0]
    q = 'update info set colval=? where colkey="Number of unique input variants"'
    outc.execute(q, [str(n_variants)])
    modified = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    q = 'update info set colval=? where colkey="Result modified at"'
    outc.execute(q, [modified])
    outconn.commit()

    # By this point outpath already holds the fully-merged db (committed
    # above), so a failure from here on must not leave it behind looking
    # like a valid result: it would carry stale postaggregator columns
    # (strip failed) or a mix of stripped-but-not-yet-recomputed columns
    # (recompute failed), indistinguishable from a successful run by
    # filename alone. Delete it and the .status.json postaggregators
    # write alongside it, then re-raise so the failure is still visible.
    print('Stripping postaggregator-authored columns for recompute...')
    try:
        mergesqlite_strip_postaggregator_columns(outconn)
        outconn.close()
        if postagg_names:
            mergesqlite_run_postaggregators(outpath, postagg_names, module_options)
    except Exception:
        outconn.close()
        print(
            f'Postaggregator recompute failed; removing incomplete output {outpath}.',
            file=sys.stderr,
        )
        if os.path.exists(outpath):
            os.remove(outpath)
        status_json_path = mergesqlite_status_json_path(outpath)
        if os.path.exists(status_json_path):
            os.remove(status_json_path)
        raise


def mergesqlite_chrom_row_counts(dbpaths):
    """Sums each chromosome's variant row count across all input dbs, for
    load-balanced bucketing (mergesqlite_bucket_chroms). Cheap - one
    `group by` query per db, no row data actually read."""
    weights = {}
    for dbpath in dbpaths:
        conn = sqlite3.connect(mergesqlite_readonly_uri(dbpath), uri=True)
        c = conn.cursor()
        c.execute('select base__chrom, count(*) from variant group by base__chrom')
        for chrom, n in c.fetchall():
            weights[chrom] = weights.get(chrom, 0) + n
        conn.close()
    return weights


def mergesqlite_bucket_chroms(chrom_weights, n_buckets):
    """Greedy longest-processing-time-first bin-packing of chromosomes
    into at most `n_buckets` balanced buckets by summed variant-row
    weight. Returns a list of chrom-name lists, one per non-empty bucket
    (never more buckets than distinct chromosomes, even if `n_buckets` is
    larger - in particular, mergesqlite_parallel() calls this with
    `n_buckets = len(chrom_weights)`, i.e. one chromosome per bucket, so
    ProcessPoolExecutor's own task queue does the load balancing across
    workers dynamically instead of this function pre-committing to a
    fixed assignment - see OC-833 production decision 9).

    No special-casing of chrX/chrY: gene rows aren't bucketed by
    chromosome at all (mergesqlite_merge_genes() merges the gene table
    once, globally, directly from the original input dbs - see OC-833
    production decision 2), so a pseudoautosomal-region gene referenced
    from both X and Y dedupes correctly regardless of which buckets those
    two chromosomes land in."""
    items = [(weight, [chrom]) for chrom, weight in chrom_weights.items()]
    items.sort(key=lambda item: item[0], reverse=True)
    n_buckets = max(1, min(n_buckets, len(items)))
    bucket_weights = [0] * n_buckets
    buckets = [[] for _ in range(n_buckets)]
    for weight, chroms in items:
        i = min(range(n_buckets), key=lambda i: bucket_weights[i])
        buckets[i].extend(chroms)
        bucket_weights[i] += weight
    return [b for b in buckets if b]


def mergesqlite_global_fileno_map(dbpaths, labels):
    """Precomputes, once and serially, the same filepath -> fileno
    numbering the serial merge loop builds incrementally as it goes
    (visiting dbpaths in order, so db1's own filenos stay identity-mapped)
    - not chromosome-dependent, so every contig shard must share this
    exact map rather than each independently renumbering its own subset
    of input files, which could disagree shard-to-shard for the same
    filepath.

    Returns (global_input_paths, fileno_remap): global_input_paths is
    {str(fileno): filepath} for the whole merge; fileno_remap is
    {dbpath: {local_fileno: global_fileno}} for every dbpaths[1:] entry
    (dbpaths[0] is untouched/identity-mapped, matching today's serial
    behavior)."""
    conn0 = sqlite3.connect(mergesqlite_readonly_uri(dbpaths[0]), uri=True)
    c0 = conn0.cursor()
    c0.execute('select colval from info where colkey="_input_paths"')
    input_paths = json.loads(c0.fetchone()[0].replace("'", '"'))
    conn0.close()
    new_fileno = max(int(v) for v in input_paths.keys()) + 1
    rev_input_paths = {filepath: fileno for fileno, filepath in input_paths.items()}
    fileno_remap = {dbpaths[0]: {int(k): int(k) for k in input_paths.keys()}}
    for dbpath in dbpaths[1:]:
        conn = sqlite3.connect(mergesqlite_readonly_uri(dbpath), uri=True)
        c = conn.cursor()
        c.execute('select colval from info where colkey="_input_paths"')
        ips = json.loads(c.fetchone()[0].replace("'", '"'))
        conn.close()
        dic = {}
        for fileno, filepath in ips.items():
            if filepath not in rev_input_paths:
                input_paths[str(new_fileno)] = filepath
                rev_input_paths[filepath] = str(new_fileno)
                dic[int(fileno)] = new_fileno
                new_fileno += 1
            else:
                dic[int(fileno)] = int(rev_input_paths[filepath])
        fileno_remap[dbpath] = dic
    return input_paths, fileno_remap


def mergesqlite_variant_key_colnos(dbpath):
    """Column indices (within a `select *`-shaped row tuple) of the
    variant-identity and uid/fileno key columns, read once from db1's
    header tables - safe to reuse against every input db's own `select *`
    rows since mergesqlite_validate_and_prepare() already requires every
    input db to share db1's exact column order."""
    conn = sqlite3.connect(mergesqlite_readonly_uri(dbpath), uri=True)
    c = conn.cursor()
    c.execute('select col_name from variant_header order by rowid')
    cols = [r[0] for r in c.fetchall()]
    v_chrom, v_pos = cols.index('base__chrom'), cols.index('base__pos')
    v_ref, v_alt = cols.index('base__ref_base'), cols.index('base__alt_base')
    c.execute('select col_name from gene_header order by rowid')
    cols = [r[0] for r in c.fetchall()]
    g_hugo = cols.index('base__hugo')
    c.execute('select col_name from sample_header order by rowid')
    cols = [r[0] for r in c.fetchall()]
    s_uid, s_sampleid = cols.index('base__uid'), cols.index('base__sample_id')
    c.execute('select col_name from mapping_header order by rowid')
    cols = [r[0] for r in c.fetchall()]
    m_uid, m_fileno = cols.index('base__uid'), cols.index('base__fileno')
    conn.close()
    return {
        "v_chrom": v_chrom, "v_pos": v_pos, "v_ref": v_ref, "v_alt": v_alt,
        "g_hugo": g_hugo, "s_uid": s_uid, "s_sampleid": s_sampleid,
        "m_uid": m_uid, "m_fileno": m_fileno,
    }


def mergesqlite_prune_shard_db1(shard_outpath, db1_path, bucket, label0, colnos):
    """Seeds one contig shard's private output file from a full copy of
    db1, then deletes everything outside `bucket`: variant rows by
    base__chrom, sample/mapping rows whose uid no longer has a surviving
    variant, and every gene row. Mirrors the serial loop's db1 label
    rename too.

    Gene is emptied here (not bucketed by chrom, not carried at all): the
    gene table has no chrom column and variant.base__hugo isn't a
    reliable proxy for one (real result dbs were found, during OC-833
    validation against a real 50-batch pilot dataset, to carry gene rows
    for hugos that are never any variant's *primary* base__hugo call), so
    there's no correct way to shard it by chromosome. It's handled by one
    global pass instead - mergesqlite_merge_genes(), run once directly
    against the original input dbs alongside mergesqlite_concatenate_shards()
    rather than replicated into (and deduped out of) every shard - see
    OC-833 production decision 2."""
    shutil.copy(db1_path, shard_outpath)
    conn = sqlite3.connect(shard_outpath)
    c = conn.cursor()
    if label0:
        c.execute('update sample set base__sample_id = ? || base__sample_id', (f'{label0}__',))
    placeholders = ",".join("?" for _ in bucket)
    c.execute(f'delete from variant where base__chrom not in ({placeholders})', bucket)
    c.execute('delete from sample where base__uid not in (select base__uid from variant)')
    c.execute('delete from mapping where base__uid not in (select base__uid from variant)')
    c.execute('delete from gene')
    conn.commit()
    conn.close()


def mergesqlite_shard_merge(
    shard_outpath, dbpaths, labels, bucket, uid_start,
    fileno_remap, global_input_paths, colnos,
):
    """The parallel path's per-shard structural merge: the same dedup
    algorithm as the serial loop in mergesqlite_serial(), restricted to
    `bucket`'s chromosomes and running against `shard_outpath` (already
    seeded by mergesqlite_prune_shard_db1), using the precomputed global
    fileno map instead of deriving it locally.

    uid_start: every shard starts allocating new variant uids from this
    same value (not a private per-shard block) - shards run independently
    and their new-uid ranges *do* overlap each other, which is fine: uids
    only need to be unique within a shard here (so they never collide
    with a db1-preserved uid this same shard also carries), because
    mergesqlite_concatenate_shards() gives every row a fresh, globally-
    unique uid as it copies shards into the final output anyway - see
    OC-833 production decision 1. No overflow-checking or block sizing
    needed as a result."""
    outconn = sqlite3.connect(shard_outpath)
    outc = outconn.cursor()
    v_chrom_colno, v_pos_colno = colnos["v_chrom"], colnos["v_pos"]
    v_ref_colno, v_alt_colno = colnos["v_ref"], colnos["v_alt"]
    s_uid_colno, s_sampleid_colno = colnos["s_uid"], colnos["s_sampleid"]
    m_uid_colno, m_fileno_colno = colnos["m_uid"], colnos["m_fileno"]

    outc.execute(
        'select base__uid, base__chrom, base__pos, base__ref_base, base__alt_base from variant'
    )
    vid_to_uid = {variant_id(r[1], r[2], r[3], r[4]): r[0] for r in outc.fetchall()}
    new_uid = uid_start
    placeholders = ",".join("?" for _ in bucket)

    for dbpath, label in zip(dbpaths[1:], labels[1:]):
        conn = sqlite3.connect(mergesqlite_readonly_uri(dbpath), uri=True)
        c = conn.cursor()
        # Variant, restricted to this shard's chrom bucket. (Gene is
        # handled once, globally, by mergesqlite_merge_genes() - see
        # mergesqlite_prune_shard_db1's docstring.)
        uid_dic = {}
        c.execute(
            f'select * from variant where base__chrom in ({placeholders}) order by rowid',
            bucket,
        )
        for r in c.fetchall():
            vid = variant_id(r[v_chrom_colno], r[v_pos_colno], r[v_ref_colno], r[v_alt_colno])
            old_uid = r[0]
            if vid in vid_to_uid:
                uid_dic[old_uid] = vid_to_uid[vid]
                continue
            r = list(r)
            r[0] = new_uid
            uid_dic[old_uid] = new_uid
            vid_to_uid[vid] = new_uid
            new_uid += 1
            q = f'insert into variant values ({",".join(["?" for v in range(len(r))])})'
            outc.execute(q, r)
        # Sample: uid-gated, same as the serial loop - already
        # bucket-safe since uid_dic only holds this bucket's uids.
        c.execute('select * from sample order by rowid')
        for r in c.fetchall():
            uid = r[s_uid_colno]
            if uid in uid_dic:
                mapped_uid = uid_dic[uid]
                r = list(r)
                r[s_uid_colno] = mapped_uid
                if label:
                    r[s_sampleid_colno] = f'{label}__{r[s_sampleid_colno]}'
                q = f'insert into sample values ({",".join(["?" for v in range(len(r))])})'
                outc.execute(q, r)
        # Mapping: uid-gated, fileno remapped via the precomputed global map.
        c.execute('select * from mapping order by rowid')
        for r in c.fetchall():
            uid = r[m_uid_colno]
            if uid in uid_dic:
                mapped_uid = uid_dic[uid]
                r = list(r)
                r[m_uid_colno] = mapped_uid
                r[m_fileno_colno] = fileno_remap[dbpath][r[m_fileno_colno]]
                q = f'insert into mapping values ({",".join(["?" for v in range(len(r))])})'
                outc.execute(q, r)
        conn.close()

    outc.execute(
        'update info set colval=? where colkey="_input_paths"',
        [json.dumps(global_input_paths)],
    )
    v = ';'.join(
        global_input_paths[str(k)]
        for k in sorted(global_input_paths.keys(), key=lambda v: int(v))
    )
    outc.execute('update info set colval=? where colkey="Input file name"', [v])
    outc.execute('select count(*) from variant')
    n_variants = outc.fetchone()[0]
    outc.execute(
        'update info set colval=? where colkey="Number of unique input variants"',
        [str(n_variants)],
    )
    modified = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    outc.execute('update info set colval=? where colkey="Result modified at"', [modified])
    outconn.commit()
    outconn.close()


def mergesqlite_parallel_shard_worker(spec):
    """Runs in its own process (ProcessPoolExecutor - sqlite3 connections
    aren't picklable/shareable across processes, so this can't be a
    thread pool): builds one contig shard's fully-merged, postagg-
    recomputed output file from scratch. `spec` is a plain dict of
    picklable values (see mergesqlite_parallel) - no shared state with
    the parent process or other shard workers."""
    if spec["md"] is not None:
        constants.custom_modules_dir = spec["md"]
    shard_outpath = spec["shard_outpath"]
    dbpaths = spec["dbpaths"]
    labels = spec["labels"]
    bucket = spec["bucket"]
    colnos = spec["colnos"]
    print(f'[shard {spec["shard_index"]}] chrom(s) {sorted(bucket)}: pruning {dbpaths[0]}...')
    mergesqlite_prune_shard_db1(shard_outpath, dbpaths[0], bucket, labels[0], colnos)
    for dbpath in dbpaths[1:]:
        print(f'[shard {spec["shard_index"]}] merging {dbpath}...')
    mergesqlite_shard_merge(
        shard_outpath, dbpaths, labels, bucket, spec["uid_start"],
        spec["fileno_remap"], spec["global_input_paths"], colnos,
    )
    shard_conn = sqlite3.connect(shard_outpath)
    mergesqlite_strip_postaggregator_columns(shard_conn)
    shard_conn.close()
    if spec["postagg_names"]:
        print(f'[shard {spec["shard_index"]}] recomputing {", ".join(spec["postagg_names"])}...')
        mergesqlite_run_postaggregators(
            shard_outpath, spec["postagg_names"], spec["module_options"],
        )
    return {
        "shard_outpath": shard_outpath, "bucket": bucket,
        "shard_index": spec["shard_index"],
    }


def mergesqlite_merge_genes(dbpaths, outconn, g_hugo_colno):
    """Merges the gene table once, globally, directly from the original
    input dbs - the exact same dedupe-by-first-hugo-seen algorithm
    mergesqlite_serial() always used for its own gene loop (copy db1's
    gene table wholesale, then add each later db's non-duplicate-hugo
    rows), just run once here instead of once per shard.

    The gene table isn't chromosome-partitionable (see
    mergesqlite_prune_shard_db1's docstring), so this deliberately reads
    straight from `dbpaths` - the original inputs, not any shard file -
    and writes into `outconn`, the same connection
    mergesqlite_concatenate_shards() is already using to build the final
    output. See OC-833 production decision 2."""
    outc = outconn.cursor()
    genes = set()
    for dbpath in dbpaths:
        conn = sqlite3.connect(mergesqlite_readonly_uri(dbpath), uri=True)
        c = conn.cursor()
        c.execute('select * from gene order by rowid')
        for r in c.fetchall():
            hugo = r[g_hugo_colno]
            if hugo in genes:
                continue
            q = f'insert into gene values ({",".join(["?" for _ in r])})'
            outc.execute(q, r)
            genes.add(hugo)
        conn.close()


def mergesqlite_checkpoint_shard(shard_path):
    """A shard file inherits its journal_mode (WAL or not) from db1 via
    mergesqlite_prune_shard_db1's shutil.copy - a real oc-run output can
    be WAL-mode, and the many further connections each shard worker opens
    on top of it (prune, merge, strip, one per recomputed postaggregator)
    can leave data sitting in that shard's -wal sidecar rather than
    checkpointed into the main file. A raw byte copy of the file (as
    mergesqlite_concatenate_shard_skeleton does) would silently pick up a
    stale (pre-checkpoint) schema/content if that sidecar isn't flushed
    first - force a full checkpoint before anything touches this file."""
    checkpoint_conn = sqlite3.connect(shard_path)
    checkpoint_conn.execute('pragma wal_checkpoint(truncate)')
    checkpoint_conn.close()


def mergesqlite_concatenate_shard_skeleton(first_shard_path, outpath):
    """Bootstraps `outpath` from whichever shard happens to be handed to
    this function - in practice, whichever shard's worker finishes first
    (OC-833 production decision 10: shards are concatenated as they
    complete, not after all of them finish, so there's no fixed "shard 0"
    to always use here the way a batch-then-concatenate design would
    have). Any shard works equally well as the donor: every shard already
    carries a full, independently-valid schema (header/annotator/
    reportsub/smartfilters/indices, identical across shards since every
    shard ran the same strip+recompute against the same module set),
    including correct, complete _input_paths/"Input file name" info rows
    written by mergesqlite_shard_merge(). Its variant/gene/sample/mapping
    tables are emptied here; mergesqlite_concatenate_one_shard() rebuilds
    them, once per completed shard including this donor.

    Returns (outconn, outc); the caller owns committing/closing outconn
    once every shard has been folded in via mergesqlite_concatenate_one_shard()."""
    mergesqlite_checkpoint_shard(first_shard_path)
    shutil.copy(first_shard_path, outpath)
    outconn = sqlite3.connect(outpath)
    outc = outconn.cursor()
    for table in ["variant", "gene", "sample", "mapping"]:
        outc.execute(f'delete from {table}')
    # keep_rowid: a shard's own variant table is expected to have exactly
    # one row per base__uid, but a handful of real input dbs have been
    # found with one exact-duplicate row (same base__uid, same
    # chrom/pos/ref/alt, at two adjacent rowids - see PLAN_DUPLICATE_UID_INVESTIGATION.md)
    # carried through unchanged from mergesqlite_prune_shard_db1's wholesale
    # copy of db1. GROUP BY base__uid in mergesqlite_concatenate_one_shard()
    # below is a first-uid-wins dedup: it both makes old_uid safe as
    # uid_map's primary key, and (via keep_rowid) picks the single
    # physical row that actually gets copied into the output's variant
    # table, instead of silently reintroducing the same duplicate under a
    # fresh uid.
    outc.execute(
        'create temp table uid_map ('
        'old_uid integer primary key, new_uid integer, keep_rowid integer)'
    )
    outconn.commit()
    return outconn, outc


def mergesqlite_concatenate_one_shard(outc, shard_index, n_shards, n_done, shard_path, uid_offset):
    """Folds one completed shard's rows into the output connection `outc`
    already belongs to (see mergesqlite_concatenate_shard_skeleton) -
    called once per shard, in whatever order shards actually finish (OC-833
    production decision 10). `shard_index` is the shard's own stable
    identity (matches the "[shard N]" labels mergesqlite_parallel_shard_worker
    prints during the merge/postagg phase); `n_done` is how many shards
    have been folded in so far, including this one, purely for progress
    display.

    variant/sample/mapping are bulk-copied via ATTACH DATABASE + INSERT
    INTO ... SELECT - cheap even at scale, unlike the row-by-row Python
    merge loop - with base__uid rewritten through a per-shard old-uid ->
    new-uid temp table as they go. Shards allocate new uids from
    overlapping ranges, not private blocks (see mergesqlite_shard_merge),
    so this is where every row actually gets its final, globally-unique
    uid: `uid_offset` is a plain running count of rows copied so far
    across every shard folded in up to this point (OC-833 production
    decision 1).

    gene is untouched here - not copied from any shard file at all (every
    shard's own gene table is empty, see mergesqlite_prune_shard_db1) -
    it's merged once, after every shard has been folded in, directly from
    the original input dbs, by mergesqlite_merge_genes() (OC-833
    production decision 2).

    Returns the new running uid_offset."""
    mergesqlite_checkpoint_shard(shard_path)
    alias = f'mergesqlite_shard_{shard_index}'
    outc.execute(f'attach database ? as {alias}', (shard_path,))
    outc.execute('delete from temp.uid_map')
    outc.execute(
        f'insert into temp.uid_map (old_uid, new_uid, keep_rowid) '
        f'select base__uid, ? + row_number() over (order by min(rowid)) - 1, min(rowid) '
        f'from {alias}.variant group by base__uid',
        (uid_offset,),
    )
    outc.execute(f'pragma {alias}.table_info(variant)')
    cols = [r[1] for r in outc.fetchall()]
    select_list = ", ".join(
        'um.new_uid' if col == 'base__uid' else f't."{col}"' for col in cols
    )
    outc.execute(
        f'insert into variant select {select_list} from {alias}.variant t '
        f'join temp.uid_map um on t.rowid = um.keep_rowid'
    )
    for table in ["sample", "mapping"]:
        outc.execute(f'pragma {alias}.table_info({table})')
        cols = [r[1] for r in outc.fetchall()]
        select_list = ", ".join(
            'um.new_uid' if col == 'base__uid' else f't."{col}"' for col in cols
        )
        outc.execute(
            f'insert into {table} select {select_list} from {alias}.{table} t '
            f'join temp.uid_map um on t.base__uid = um.old_uid'
        )
    outc.execute('select count(*) from temp.uid_map')
    n_shard_variants = outc.fetchone()[0]
    new_uid_offset = uid_offset + n_shard_variants
    # DETACH is refused while a transaction touching that database is
    # still open - commit first.
    outc.connection.commit()
    outc.execute(f'detach database {alias}')
    print(
        f'Concatenated shard {shard_index} ({n_done}/{n_shards} done): '
        f'{n_shard_variants} variant(s), {new_uid_offset} total so far.'
    )
    return new_uid_offset


def mergesqlite_concatenate_finish(outconn, outc, dbpaths, colnos):
    """Runs once, after every shard has been folded in by
    mergesqlite_concatenate_one_shard(): the one remaining global,
    non-shardable pass (gene - OC-833 production decision 2) plus the
    output db's own bookkeeping columns. Commits and closes outconn."""
    mergesqlite_merge_genes(dbpaths, outconn, colnos["g_hugo"])
    outc.execute('select count(*) from variant')
    n_variants = outc.fetchone()[0]
    outc.execute(
        'update info set colval=? where colkey="Number of unique input variants"',
        [str(n_variants)],
    )
    modified = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    outc.execute('update info set colval=? where colkey="Result modified at"', [modified])
    outconn.commit()
    outconn.close()


def mergesqlite_parallel(args, prep):
    """Contig-parallel merge (OC-833): one task per chromosome (not one
    per worker - OC-833 production decision 9) runs independently in its
    own process (mergesqlite_parallel_shard_worker), and each shard is
    folded into the output as soon as it completes rather than after
    every shard finishes (mergesqlite_concatenate_one_shard - OC-833
    production decision 10), then the gene table is merged globally
    (mergesqlite_concatenate_finish).

    casecontrol is dropped entirely here, not just deferred to a final
    serial pass - mergesqlite_validate_and_prepare() already hard-fails
    before this function is ever called if casecontrol would actually do
    anything (its Fisher's-exact denominator is a whole-cohort scalar,
    out of scope for per-shard parallelization, and there's no
    requirement to recompute it after a parallel merge - see OC-833
    production decision 7). Any leftover "casecontrol" in
    prep["postagg_names"] past that check is guaranteed to be a no-op
    (no cohorts conf given), so it's simply excluded from what shards
    recompute."""
    dbpaths = prep["dbpaths"]
    labels = prep["labels"]
    outpath = prep["outpath"]
    postagg_names = [n for n in prep["postagg_names"] if n != "casecontrol"]
    module_options = prep["module_options"]
    n_workers = max(1, args.workers or os.cpu_count() or 1)
    tmpdir = tempfile.mkdtemp(prefix="mergesqlite_parallel_", dir=args.tmpdir)
    try:
        print(f'Computing per-chromosome load balance across {len(dbpaths)} input db(s)...')
        chrom_weights = mergesqlite_chrom_row_counts(dbpaths)
        # One bucket per chromosome, not one per worker (OC-833 production
        # decision 9): with exactly n_workers buckets, a worker that
        # finishes its (necessarily coarser) bucket early has nothing left
        # to pick up, and sits idle until the slowest bucket finishes -
        # observed directly on the pilot_1000_chip benchmark, where 3 of 4
        # workers sat idle for over an hour waiting on the 4th. Passing
        # every chromosome as its own bucket instead means
        # ProcessPoolExecutor's own task queue (below) does the load
        # balancing dynamically: an idle worker just pulls the next
        # unstarted chromosome.
        buckets = mergesqlite_bucket_chroms(chrom_weights, len(chrom_weights))
        print(f'Bucketed {len(chrom_weights)} chromosome(s) into {len(buckets)} shard(s).')
        global_input_paths, fileno_remap = mergesqlite_global_fileno_map(dbpaths, labels)
        colnos = mergesqlite_variant_key_colnos(dbpaths[0])
        conn0 = sqlite3.connect(mergesqlite_readonly_uri(dbpaths[0]), uri=True)
        c0 = conn0.cursor()
        c0.execute('select max(base__uid) from variant')
        # Every shard starts allocating new variant uids from this same
        # value - not a private per-shard block. See
        # mergesqlite_shard_merge()'s docstring and OC-833 production
        # decision 1: shard-local uid uniqueness is all that's needed,
        # since mergesqlite_concatenate_shards() renumbers every row's
        # uid globally as it copies.
        uid_start = c0.fetchone()[0] + 1
        conn0.close()
        # vcfinfo's multi_sample must reflect the cohort-wide sample
        # count, not any one shard's local subset (a shard's own sample
        # table is restricted to its chrom bucket) - see OC-833
        # production decision 5. Passed through as a plain
        # --module-option-style override on vcfinfo's own confs; vcfinfo
        # itself is responsible for honoring it in setup().
        shard_module_options = module_options
        if "vcfinfo" in postagg_names:
            global_multi_sample = len(prep["sample_id_sources"]) > 1
            shard_module_options = dict(module_options)
            shard_module_options["vcfinfo"] = {
                **module_options.get("vcfinfo", {}),
                "multi_sample": global_multi_sample,
            }
        shard_specs = [
            {
                "shard_index": i,
                "shard_outpath": os.path.join(tmpdir, f"shard_{i}.sqlite"),
                "dbpaths": dbpaths,
                "labels": labels,
                "bucket": bucket,
                "uid_start": uid_start,
                "fileno_remap": fileno_remap,
                "global_input_paths": global_input_paths,
                "colnos": colnos,
                "postagg_names": postagg_names,
                "module_options": shard_module_options,
                "md": args.md,
            }
            for i, bucket in enumerate(buckets)
        ]
        print(
            f'Merging {len(shard_specs)} contig shard(s) in parallel '
            f'(workers={min(n_workers, len(shard_specs))})...'
        )
        # Shards are folded into `outpath` as they complete, not after
        # every one finishes (OC-833 production decision 10): the main
        # process has nothing else to do while waiting on the slowest
        # shard anyway, so there's no reason to leave the (non-trivial)
        # concatenation work stacked up serially at the end when it can
        # overlap the remaining shards' compute time instead. Whichever
        # shard happens to complete first becomes the output skeleton
        # (mergesqlite_concatenate_shard_skeleton) - not necessarily shard
        # 0, since completion order now depends on runtime scheduling, not
        # bucket index. That also means final uid values are no longer
        # reproducible run-to-run for the same input (still guaranteed
        # globally unique and correct, just order-dependent) - nothing
        # today relies on that reproducibility, only on uniqueness.
        outconn = None
        outc = None
        n_shards = len(shard_specs)
        n_done = 0
        uid_offset = 0
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=min(n_workers, n_shards)
        ) as ex:
            futures = [ex.submit(mergesqlite_parallel_shard_worker, spec) for spec in shard_specs]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if outconn is None:
                    print(f'Concatenating shard outputs into {outpath} as they complete...')
                    outconn, outc = mergesqlite_concatenate_shard_skeleton(
                        result["shard_outpath"], outpath,
                    )
                n_done += 1
                uid_offset = mergesqlite_concatenate_one_shard(
                    outc, result["shard_index"], n_shards, n_done,
                    result["shard_outpath"], uid_offset,
                )
        mergesqlite_concatenate_finish(outconn, outc, dbpaths, colnos)
    except Exception:
        print(
            f'Parallel merge failed; removing incomplete output {outpath}.',
            file=sys.stderr,
        )
        for path in (outpath, outpath + '-wal', outpath + '-shm'):
            if os.path.exists(path):
                os.remove(path)
        status_json_path = mergesqlite_status_json_path(outpath)
        if os.path.exists(status_json_path):
            os.remove(status_json_path)
        raise
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def filtersqlite(args):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(filtersqlite_async(args))

def filtersqlite_async_drop_copy_table(c, table_name):
    print(f"- {table_name}")
    c.execute(f"drop table if exists main.{table_name}")
    c.execute(f"create table main.{table_name} as select * from old_db.{table_name}")

async def filtersqlite_async(args):
    dbpaths = args.paths
    for dbpath in dbpaths:
        if not dbpath.endswith(".sqlite"):
            print(f"  Skipping")
            continue
        opath = dbpath[:-7] + "." + args.suffix + ".sqlite"
        print(f"{opath}")
        if os.path.exists(opath):
            os.remove(opath)
        conn = sqlite3.connect(opath)
        c = conn.cursor()
        try:
            c.execute("attach database '" + dbpath + "' as old_db")
            cf = await cravat_filter.CravatFilter.create(
                dbpath=dbpath, 
                filterpath=args.filterpath, 
                filtersql=args.filtersql, 
                includesample=args.includesample, 
                excludesample=args.excludesample)
            await cf.exec_db(cf.loadfilter)
            for table_name in ["info", "smartfilters", "viewersetup", 
                "variant_annotator", "variant_header", "variant_reportsub", 
                "gene_annotator", "gene_header", "gene_reportsub", 
                "sample_annotator", "sample_header", "mapping_annotator", 
                "mapping_header"]:
                filtersqlite_async_drop_copy_table(c, table_name)
            # Variant
            print(f"- variant")
            await cf.exec_db(cf.make_filtered_uid_table)
            c.execute("create table variant as select v.* from old_db.variant as v, old_db.variant_filtered as f where v.base__uid=f.base__uid")
            # Gene
            print(f"- gene")
            await cf.exec_db(cf.make_filtered_hugo_table)
            c.execute("create table gene as select g.* from old_db.gene as g, old_db.gene_filtered as f where g.base__hugo=f.base__hugo")
            # Sample
            print(f"- sample")
            req = []
            rej = []
            if "sample" in cf.filter:
                if "require" in cf.filter["sample"]:
                    req = cf.filter["sample"]["require"]
                if "reject" in cf.filter["sample"]:
                    rej = cf.filter["sample"]["reject"]
            if cf.includesample is not None:
                req = cf.includesample
            if cf.excludesample is not None:
                rej = cf.excludesample
            if len(req) > 0 or len(rej) > 0:
                q = "create table sample as select s.* from old_db.sample as s, old_db.variant_filtered as v where s.base__uid=v.base__uid"
                if req:
                    q += " and s.base__sample_id in ({})".format(
                        ", ".join(['"{}"'.format(sid) for sid in req])
                    )
                for s in rej:
                    q += ' except select * from sample where base__sample_id="{}"'.format(
                        s
                    )
            else:
                q = "create table sample as select s.* from old_db.sample as s, old_db.variant_filtered as v where s.base__uid=v.base__uid"
            c.execute(q)
            # Mapping
            c.execute("create table mapping as select m.* from old_db.mapping as m, old_db.variant_filtered as v where m.base__uid=v.base__uid")
            # Indices
            c.execute("select name, sql from old_db.sqlite_master where type='index'")
            for r in c.fetchall():
                index_name = r[0]
                sql = r[1]
                if sql is not None:
                    print(f"- {index_name}")
                    c.execute(sql)
            # Info
            print("- info")
            c.execute("select count(*) from variant")
            n = c.fetchone()[0]
            c.execute(f"update info set colval={n} where colkey=\"Number of unique input variants\"")
            conn.commit()
            await cf.close_db()
            c.close()
            conn.close()
            print(f"-> {opath}")
        except Exception as e:
            c.close()
            conn.close()
            raise e


def status_from_db(dbpath):
    """
    Generate a status json from a result database.
    Currently only works well if the database is in the gui jobs area.
    """
    if not isinstance(dbpath, Path):
        dbpath = Path(dbpath)
    d = {}
    db = sqlite3.connect(str(dbpath))
    c = db.cursor()
    c.execute("select colkey, colval from info")
    infod = {r[0]: r[1] for r in c}
    try:
        d["annotators"] = []
        d["annotator_version"] = {}
        c.execute("select name, version from gene_annotator")
        skip_names = {"base", "tagsampler", "vcfinfo", ""}
        for r in c:
            if r[0] in skip_names:
                continue
            d["annotators"].append(r[0])
            d["annotator_version"][r[0]] = r[1]
        c.execute("select name, version from variant_annotator")
        for r in c:
            if r[0] in skip_names:
                continue
            d["annotators"].append(r[0])
            d["annotator_version"][r[0]] = r[1]
        d["annotators"] = sorted(list(set(d["annotators"])))
        c.execute('select colval from info where colkey="Input genome"')
        d["assembly"] = c.fetchone()[0]
        d["db_path"] = str(dbpath)
        d["id"] = str(dbpath.parent)
        d["id"] = str(dbpath.parent.name)
        d["job_dir"] = str(dbpath.parent)
        d["note"] = ""
        d["num_error_input"] = 0
        c.execute(
            'select colval from info where colkey="Number of unique input variants"'
        )
        d["num_unique_var"] = c.fetchone()[0]
        d["num_input_var"] = d["num_unique_var"]
        c.execute('select colval from info where colkey="open-cravat"')
        d["open_cravat_version"] = c.fetchone()[0]
        if "Input file name" in infod:
            d["orig_input_path"] = infod["Input file name"].split(";")
            d["orig_input_fname"] = [
                Path(p).name for p in infod["Input file name"].split(";")
            ]
        else:
            d["orig_input_fname"] = [str(dbpath.stem)]
            d["orig_input_path"] = [str(dbpath.with_suffix(""))]
        d["reports"] = []
        d["run_name"] = str(dbpath.stem)
        d["status"] = "Finished"
        d["submission_time"] = datetime.datetime.fromtimestamp(
            dbpath.stat().st_ctime
        ).isoformat()
        d["viewable"] = True
    except:
        raise
    finally:
        c.close()
        db.close()
    return d


#Get metadata about a previously run job from its sqlite DB and use that to create a package
#that can be used as a template to analyze additional data files in the same way.
def jobtopackage(args):

    try:
        # Connect to job database
        db = sqlite3.connect(args.db)
        cursor = db.cursor()
            
        # check for overwrite setting
        overwrite = True
        if args.ov is None or args.ov == False:
            overwrite = False
    
        q = 'select colval from info where colkey = "_annotators"'
        cursor.execute(q)
        r = cursor.fetchone()
        annots = r[0]
            
        annotators = []
        for a in annots.split(','):
            if a.startswith('extra_vcf_info') or a.startswith('original_input'):
                continue
            # Currently throwing away version number - preserve it??
            annotators.append(a.split(':')[0]) 
                
         
        reports = []
        q = 'select colval from info where colkey = "_reports"'
        cursor.execute(q)
        r = cursor.fetchone()
        if r is not None:
            for rep in r[0].split(','):
                reports.append(rep)
            
            
        filter = ""
        q = 'select viewersetup from viewersetup where datatype = "filter" and name = "quicksave-name-internal-use"'
        cursor.execute(q)
        r = cursor.fetchone()
        if r is not None:
            filter = r[0]
    
        viewer = ""
        q = 'select viewersetup from viewersetup where datatype = "layout" and name = "quicksave-name-internal-use"'
        cursor.execute(q)
        r = cursor.fetchone()
        if r is not None:
            viewer = r[0]
               
        name = args.name
        package_conf = {}
        package_conf['type'] = 'package'
        package_conf['description'] = 'Package ' + name + " created from user job with --saveaspackage"
        package_conf['title'] = name
        package_conf['version'] = '1.0'
        package_conf['requires'] = annotators.copy()
            
        run = {}
        run['annotators'] = annotators.copy()
        run['reports'] = reports
        if filter != "":
            run['filter'] = filter 
        if viewer != "":
            run['viewer'] = viewer
            
        package_conf['run'] = run
           
        au.create_package(name, package_conf, overwrite)
            
        print("Successfully created package " + name + ".  Package can now be used to run jobs or published for other users.")        
    
    except ValueError as e: 
        print("Error - " + str(e))    

parser = argparse.ArgumentParser()
# converts db coordinate to hg38
subparsers = parser.add_subparsers(title="Commands")
parser_convert = subparsers.add_parser(
    "converttohg38", help="converts hg19 coordinates in SQLite3 database to hg38 ones."
)
parser_convert.add_argument(
    "--db", nargs="?", required=True, help="path to SQLite3 database file"
)
parser_convert.add_argument(
    "--sourcegenome", required=True, help="genome assembly of source database"
)
parser_convert.add_argument(
    "--cols", nargs="+", required=True, help="names of the columns to convert"
)
parser_convert.add_argument(
    "--tables",
    nargs="*",
    help="table(s) to convert. If omitted, table name will be used as chromosome name.",
)
parser_convert.add_argument(
    "--chromcol",
    required=False,
    help="chromosome column. If omitted, all tables will be tried to be converted.",
)
parser_convert.set_defaults(func=converttohg38)
# migrate old result db
parser_migrate_result = subparsers.add_parser(
    "migrate-result", help="migrates result db made with older versions of open-cravat"
)
parser_migrate_result.add_argument(
    "dbpath", help="path to a result db file or a directory"
)
parser_migrate_result.add_argument(
    "-r",
    dest="recursive",
    action="store_true",
    default=False,
    help="recursive operation",
)
parser_migrate_result.add_argument(
    "-c",
    dest="backup",
    action="store_true",
    default=False,
    help="backup original copy with .bak extension",
)
parser_migrate_result.set_defaults(func=migrate_result)
# Make job accessible through the gui
parser_result2gui = subparsers.add_parser(
    "result2gui", help="Copy a command line job into the GUI submission list"
)
parser_result2gui.add_argument("path", help="Path to result database", type=Path)
parser_result2gui.add_argument(
    "-u",
    "--user",
    help="User who will own the job. Defaults to single user default user.",
    type=str,
    default="default",
)
parser_result2gui.set_defaults(func=result2gui)
# Merge SQLite files
parser_mergesqlite = subparsers.add_parser(
    "mergesqlite", help="Merge SQLite result files"
)
parser_mergesqlite.add_argument("path", nargs='+',
    help="Path to result database. Optionally 'path:label' to rename that "
         "db's sample_ids to 'label__sample_id' on merge, to resolve "
         "sample_id collisions with other input dbs.")
parser_mergesqlite.add_argument("-o", dest="outpath",
    required=True, help="Output SQLite file path")
parser_mergesqlite.add_argument("--skip-postaggregator", dest="skip_postaggregator",
    action="store_true", default=False,
    help="Don't recompute postaggregator columns after merge. Without this "
         "flag, tagsampler, casecontrol, varmeta, and vcfinfo are "
         "recomputed against the merged sample set by default (same as a "
         "fresh 'oc run'); casecontrol still no-ops with no "
         "casecontrol.cohorts module option given.")
parser_mergesqlite.add_argument("-p", nargs="+", dest="postaggregators", default=[],
    help="Additional postaggregator module(s) to recompute after merge, "
         "on top of the defaults (tagsampler, casecontrol, varmeta, "
         "vcfinfo). Ignored with --skip-postaggregator.")
parser_mergesqlite.add_argument("--module-option", dest="module_option", nargs="*",
    default=None,
    help="Module-specific option in module_name.key=value syntax, for "
         "postaggregators recomputed after merge. For example, "
         "--module-option casecontrol.cohorts=/path/to/merged-cohort-file")
parser_mergesqlite.add_argument("--md", dest="md", default=None,
    help="Specify the root directory of OpenCRAVAT modules (annotators, etc)")
parser_mergesqlite.add_argument("--parallel", dest="parallel",
    action="store_true", default=False,
    help="Merge and recompute postaggregators in parallel, sharded by "
         "chromosome. Structural-merge and "
         "postaggregator-recompute output is content-equivalent to the "
         "default serial merge, modulo uid renumbering. casecontrol is "
         "not supported with --parallel: its case/control counts are a "
         "whole-cohort scalar, and using --module-option "
         "casecontrol.cohorts=... (or -p casecontrol) together with "
         "--parallel is a hard error. Use the default serial merge "
         "instead if you need casecontrol.")
parser_mergesqlite.add_argument("--workers", dest="workers", type=int, default=None,
    help="Number of parallel worker processes for --parallel. Default is "
         "os.cpu_count(). Ignored without --parallel.")
parser_mergesqlite.add_argument("--tmpdir", dest="tmpdir", default=None,
    help="Directory to write --parallel's per-shard temp sqlite files "
         "into. Defaults to Python's normal temp-dir resolution "
         "(TMPDIR/TEMP/TMP, else /tmp), which on some machines is a "
         "small RAM-backed tmpfs unsuited to a large merge - pass a "
         "disk-backed directory with enough free space for a full copy "
         "of the merged output. Ignored without --parallel.")
parser_mergesqlite.set_defaults(func=mergesqlite)
parser_showsqliteinfo = subparsers.add_parser('showsqliteinfo', help='Show SQLite result file information')
parser_showsqliteinfo.add_argument('paths', nargs='+', help='SQLite result file paths')
parser_showsqliteinfo.set_defaults(func=showsqliteinfo)
parser_filtersqlite = subparsers.add_parser(
    "filtersqlite", help="Filter SQLite result files to produce filtered SQLite result files"
)
parser_filtersqlite.add_argument("paths", nargs='+', help="Path to result database")
parser_filtersqlite.add_argument("-o", dest="out", default=".", help="Output SQLite file folder")
parser_filtersqlite.add_argument("-s", dest="suffix", default="filtered", help="Suffix for output SQLite files")
parser_filtersqlite.add_argument("-f", dest="filterpath", default=None, help="Path to a filter JSON file")
parser_filtersqlite.add_argument("--filtersql", default=None, help="Filter SQL")
parser_filtersqlite.add_argument(
    '--includesample',
    dest='includesample',
    nargs='+',
    default=None,
    help='Sample IDs to include',
)
parser_filtersqlite.add_argument(
    '--excludesample',
    dest='excludesample',
    nargs='+',
    default=None,
    help='Sample IDs to exclude',
)
parser_filtersqlite.set_defaults(func=filtersqlite)

parser_jobtopackage = subparsers.add_parser("jobtopackage", help="Creates a package from a previously run job.  Packages are a set of annotations, reports, and filters that can be applied to new data.")
parser_jobtopackage.add_argument("--name", required=True, help="name of package to create")
parser_jobtopackage.add_argument("--db", required=True, help="sqlite file of job to turn into a package")
parser_jobtopackage.add_argument("--ov", "--overwrite", action='store_true', help="overwrite existing package")
parser_jobtopackage.set_defaults(func=jobtopackage)

def main():
    args = get_args()
    if "func" not in args:
        parser.print_help(sys.stderr)
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
