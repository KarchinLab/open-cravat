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
import time
from pathlib import Path
import datetime
from . import admin_util as au
from . import cravat_filter
from distutils.version import LooseVersion
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
    return chrom + str(pos) + ref + alt

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

# For now, only jobs with same annotators are allowed.
def mergesqlite(args):
    dbpaths = args.path
    if len(dbpaths) < 2:
        exit("Multiple sqlite file paths should be given")
    outpath = args.outpath
    if outpath.endswith('.sqlite') == False:
        outpath = outpath + '.sqlite'
    # Checks columns being the same.
    conn = sqlite3.connect(dbpaths[0])
    c = conn.cursor()
    c.execute('select col_name from variant_header')
    v_cols = sorted([r[0] for r in c.fetchall()])
    c.execute('select col_name from gene_header')
    g_cols = sorted([r[0] for r in c.fetchall()])
    c.close()
    conn.close()
    for dbpath in dbpaths[1:]:
        conn = sqlite3.connect(dbpath)
        c = conn.cursor()
        c.execute('select col_name from variant_header')
        if v_cols != sorted([r[0] for r in c.fetchall()]):
            exit("Annotation columns mismatch (variant table)")
        c.execute('select col_name from gene_header')
        if g_cols != sorted([r[0] for r in c.fetchall()]):
            exit("Annotation columns mismatch (gene table)")
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
    outc.execute('select col_name from mapping_header order by rowid')
    cols = [r[0] for r in outc.fetchall()]
    m_uid_colno = cols.index('base__uid')
    m_fileno_colno = cols.index('base__fileno')
    outc.execute('select max(base__uid) from variant')
    new_uid = outc.fetchone()[0] + 1
    # Input paths
    outc.execute('select colkey, colval from info where colkey="_input_paths"')
    input_paths = json.loads(outc.fetchone()[1].replace("'", '"'))
    new_fileno = max([int(v) for v in input_paths.keys()]) + 1
    rev_input_paths = {}
    for fileno, filepath in input_paths.items():
        rev_input_paths[filepath] = fileno
    # Makes initial hugo and variant id lists.
    outc.execute('select base__hugo from gene')
    genes = {r[0] for r in outc.fetchall()}
    outc.execute('select base__chrom, base__pos, base__ref_base, base__alt_base from variant')
    variants = {variant_id(r[0], r[1], r[2] ,r[3]) for r in outc.fetchall()}
    for dbpath in dbpaths[1:]:
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
            if vid in variants:
                continue
            old_uid = r[0]
            r = list(r)
            r[0] = new_uid
            uid_dic[old_uid] = new_uid
            new_uid += 1
            q = f'insert into variant values ({",".join(["?" for v in range(len(r))])})'
            outc.execute(q, r)
            variants.add(vid)
        # Sample
        c.execute('select * from sample order by rowid')
        for r in c.fetchall():
            uid = r[s_uid_colno]
            if uid in uid_dic:
                new_uid = uid_dic[uid]
                r = list(r)
                r[s_uid_colno] = new_uid
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
        # Mapping
        c.execute('select * from mapping order by rowid')
        for r in c.fetchall():
            uid = r[m_uid_colno]
            if uid in uid_dic:
                new_uid = uid_dic[uid]
                r = list(r)
                r[m_uid_colno] = new_uid
                r[m_fileno_colno] = fileno_dic[r[m_fileno_colno]]
                q = f'insert into mapping values ({",".join(["?" for v in range(len(r))])})'
                outc.execute(q, r)
    q = 'update info set colval=? where colkey="_input_paths"'
    outc.execute(q, [json.dumps(input_paths)])
    q = 'update info set colval=? where colkey="Input file name"'
    v = ';'.join([input_paths[str(v)] for v in sorted(input_paths.keys(), key=lambda v: int(v))])
    outc.execute(q, [v])
    outconn.commit()


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
parser_mergesqlite.add_argument("path", nargs='+', help="Path to result database", type=Path)
parser_mergesqlite.add_argument("-o", dest="outpath", 
    required=True, help="Output SQLite file path")
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

def main():
    args = get_args()
    if "func" not in args:
        parser.print_help(sys.stderr)
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
