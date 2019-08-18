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

def get_args ():
    if len(sys.argv) == 1:
        sys.argv.append('-h')
    parser = argparse.ArgumentParser()
    # converts db coordinate to hg38
    subparsers = parser.add_subparsers(title='Commands')
    subparser = subparsers.add_parser('converttohg38',
        help='converts hg19 coordinates in sqlite3 database to hg38 ones.')
    subparser.add_argument('--db',
        nargs='?',
        required=True,
        help='path to sqlite3 database file')
    subparser.add_argument('--sourcegenome',
        required=True,
        help='genome assembly of source database')
    subparser.add_argument('--cols',
        nargs='+',
        required=True,
        help='names of the columns to convert')
    subparser.add_argument('--tables',
        nargs='*',
        help='table(s) to convert. If omitted, table name will be used as chromosome name.')
    subparser.add_argument('--chromcol',
        required=False,
        help='chromosome column. If omitted, all tables will be tried to be converted.')
    subparser.set_defaults(func=converttohg38)
    # migrate old result db
    parser_migrate_result = subparsers.add_parser('migrate-result',
                                               help='migrates result db made with older versions of open-cravat')
    parser_migrate_result.add_argument('dbpath', help='path to result db')
    parser_migrate_result.set_defaults(func=migrate_result)
    args = parser.parse_args()
    return args

def converttohg38 (args):
    if args.sourcegenome not in ['hg18', 'hg19']:
        print('Source genome should be either hg18 or hg19.')
        exit()
    if os.path.exists(args.db) == False:
        print(args.db, 'does not exist.')
        exit()
    liftover = pyliftover.LiftOver(constants.get_liftover_chain_path_for_src_genome(args.sourcegenome))
    print('Extracting table schema from DB...')
    cmd = ['sqlite3', args.db, '.schema']
    output = subprocess.check_output(cmd)
    sqlpath = args.db + '.newdb.sql'
    wf = open(sqlpath, 'w')
    wf.write(output.decode())
    wf.close()
    newdbpath = '.'.join(args.db.split('.')[:-1]) + '.hg38.sqlite'
    if os.path.exists(newdbpath):
        print('Deleting existing hg38 DB...')
        os.remove(newdbpath)
    print('Creating ' + newdbpath + '...')
    newdb = sqlite3.connect(newdbpath)
    newc = newdb.cursor()
    print('Creating same table(s) in ' + newdbpath + '...')
    cmd = ['sqlite3', newdbpath, '.read ' + sqlpath]
    output = subprocess.check_output(cmd)
    db = sqlite3.connect(args.db)
    c = db.cursor()
    if args.tables == None:
        print('tables not given. All tables will be tried.')
        output = subprocess.check_output(['sqlite3', args.db, '.table'])
        args.tables = output.decode().split()
        args.tables.sort()
        print('The following tables will be examined:', ', '.join(args.tables))
    tables_toconvert = []
    tables_tocopy = []
    for table in args.tables:
        c.execute('select * from ' + table + ' limit 1')
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
    print('Tables to convert:', ', '.join(tables_toconvert) if len(tables_toconvert) > 0 else 'none')
    print('Tables to copy:', ', '.join(tables_tocopy) if len(tables_tocopy) > 0 else 'none')
    wf = open(newdbpath + '.noconversion', 'w')
    count_interval = 10000
    for table in tables_toconvert:
        print('Converting ' + table + '...')
        c.execute('select * from ' + table)
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
            if chrom.startswith('chr') == False:
                chrom = 'chr' + chrom
            for colno in colnos:
                pos = int(row[colno])
                liftover_out = liftover.convert_coordinate(chrom, pos)
                if liftover_out == None:
                    print('- no liftover mapping:', chrom + ':' + str(pos))
                    continue
                if liftover_out == []:
                    wf.write(table + ':' + ','.join([str(v) for v in row]) + '\n')
                    continue
                newpos = liftover_out[0][1]
                row[colno] = newpos
            q = 'insert into ' + table + ' values(' + ','.join(['"' + v + '"' if type(v) == type('a') else str(v) for v in row]) + ')'
            newc.execute(q)
            count += 1
            if count % count_interval == 0:
                print('  ' + str(count) + '...')
        print('  ' + table + ': done.', count, 'rows converted')
    wf.close()
    for table in tables_tocopy:
        count = 0
        print('Copying ' + table + '...')
        c.execute('select * from ' + table)
        for row in c.fetchall():
            row = list(row)
            q = 'insert into ' + table + ' values(' + ','.join(['"' + v + '"' if type(v) == type('a') else str(v) for v in row]) + ')'
            newc.execute(q)
            count += 1
            if count % count_interval == 0:
                print('  ' + str(count) + '...')
        print('  ' + table + ': done.', count, 'rows converted')
    newdb.commit()

def migrate_result (args):
    dbpath = args.dbpath
    if os.path.exists(dbpath) == False:
        print('Result DB file [{}] does not exist.'.format(dbpath))
    db = sqlite3.connect(dbpath)
    cursor = db.cursor()
    try:
        q = 'select colval from info where colkey="open-cravat"'
        cursor.execute(q)
        r = cursor.fetchone()
        if r is None:
            print('Result DB is too old for migration.')
            return
        else:
            oc_ver = r[0]
    except:
        print('Result DB is not open-cravat result DB or too old for migration')
        return
    if oc_ver not in ['1.4.4', '1.4.5', '1.5.0', '1.5.1']:
        print('Result DB is too old for migration. OpenCRAVAT 1.4.4 and up are supported.')
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
        hg38ver = r[0].split('(')[1].strip(')')
        q = 'insert into info values ("_mapper", "hg38:{}")'.format(hg38ver)
        cursor.execute(q)
    q = 'select colval from info where colkey="_input_paths"'
    cursor.execute(q)
    r = cursor.fetchone()
    if r is None:
        q = 'select colval from info where colkey="Input file name"'
        cursor.execute(q)
        r = cursor.fetchone()
        ips = r[0].split(';')
        input_paths_str = '{'
        for i in range(len(ips)):
            input_paths_str += "'" + str(i) + "': '" + ips[i] + "', "
        input_paths_str += '}'
        q = 'insert into info values ("_input_paths", "{}")'.format(input_paths_str)
        cursor.execute(q)
    q = 'select colval from info where colkey="_annotator_desc"'
    cursor.execute(q)
    r = cursor.fetchone()
    if r is None:
        q = 'insert into info values ("_annotator_desc", "{}")'
        cursor.execute(q)
    q = 'update info set colval="1.5.1" where colkey="open-cravat"'
    cursor.execute(q)
    db.commit()
    # gene
    q = 'select * from gene limit 1'
    cursor.execute(q)
    cols = [v[0] for v in cursor.description]
    gene_cols_to_retrieve = []
    note_to_add = True
    for col in cols:
        module = col.split('__')[0]
        if module == 'base':
            if col == 'base__hugo':
                gene_cols_to_retrieve.append(col)
            elif col == 'base__note':
                gene_cols_to_retrieve.append(col)
                note_to_add = False
        else:
            gene_cols_to_retrieve.append(col)
    cursor.execute('alter table gene rename to gene_old')
    cursor.execute('create table gene as select {} from gene_old'.format(','.join(gene_cols_to_retrieve)))
    if note_to_add:
        cursor.execute('alter table gene add column base__note text')
    cursor.execute('drop table gene_old')
    cursor.execute('create index gene_idx_0 on gene (base__hugo)')
    # variant_header, gene_header, mapping_header, sample_header
    for table in ['variant', 'gene', 'mapping', 'sample']:
        q = 'select * from {}_header'.format(table)
        cursor.execute(q)
        rs = cursor.fetchall()
        cols = [v[0] for v in cursor.description]
        if len(cols) == 2 and 'col_name' in cols and 'col_def' in cols:
            pass
        else:
            q = 'alter table {}_header rename to {}_header_old'.format(table, table)
            cursor.execute(q)
            q = 'create table {}_header (col_name text, col_def text)'.format(table)
            cursor.execute(q)
            old_colkeys = ['col_name', 'col_title', 'col_type', 'col_cats', 'col_width', 'col_desc', 'col_hidden', 'col_ctg', 'col_filterable', 'col_link_format']
            old_to_new_colkey = {'col_name': 'name', 'col_title': 'title', 'col_type': 'type', 'col_cats': 'categories', 'col_width': 'width', 'col_desc': 'desc', 'col_hidden': 'hidden', 'col_ctg': 'category', 'col_filterable': 'filterable', 'col_link_format': 'link_format'}
            colnos = {}
            for c in old_colkeys:
                try:
                    colnos[c] = cols.index(c)
                except:
                    colnos[c] = None
            colidx = {}
            for r in rs:
                col_name = r[colnos['col_name']]
                if table == 'gene' and col_name not in gene_cols_to_retrieve:
                    continue
                module = col_name.split('__')[0]
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
                col_def['index'] = colidx[module]
                col_def['genesummary'] = False
                if col_def['categories'] is None:
                    col_def['categories'] = []
                else:
                    col_def['categories'] = json.loads(col_def['categories'])
                if col_def['width'] is None:
                    col_def['width'] = 100
                if col_def['hidden'] is None:
                    col_def['hidden'] = False
                if col_def['filterable'] is None:
                    col_def['filterable'] = True
                if col_def['desc'] is None:
                    col_def['desc'] = ''
                q = 'insert into {}_header values (\'{}\', \'{}\')'.format(table, col_name, json.dumps(col_def))
                cursor.execute(q)
            if table == 'gene' and note_to_add:
                q = 'insert into gene_header (\'base__note\', \'{"name": "base__note", "index": 1, "title": "Note", "type": "string", "categories": [], "width": 50, "desc": null, "hidden": false, "category": null, "filterable": true, "link_format": null, "genesummary": false}\')'
                cursor.execute(q)
        q = 'drop table {}_header_old'.format(table)
        cursor.execute(q)
        db.commit()
    # mapping
    # base__fileno cannot be determined. set to 0.
    q = 'select * from mapping limit 1'
    cursor.execute(q)
    cols = [v[0] for v in cursor.description]
    if 'base__fileno' not in cols:
        q = 'alter table mapping add column base__fileno integer'
        cursor.execute(q)
        q = 'update mapping set base__fileno=0'
        cursor.execute(q)
    db.commit()
    # smartfilters
    try:
        cursor.execute('select * from smartfilters')
    except:
        q = 'create table smartfilters (name text, definition text)'
        cursor.execute(q)
        db.commit()

def main ():
    args = get_args()
    args.func(args)

if __name__ == '__main__':
    main()
