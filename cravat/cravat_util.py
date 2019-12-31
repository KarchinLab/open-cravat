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

def get_args ():
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

migrate_functions = {}
supported_oc_ver = ['1.4.4', '1.4.5', '1.5.0', '1.5.1', '1.5.2']

def check_result_db_version (dbpath, version):
    try:
        db = sqlite3.connect(dbpath)
        cursor = db.cursor()
        q = 'select colval from info where colkey="open-cravat"'
        cursor.execute(q)
        r = cursor.fetchone()
        if r is None:
            raise
        else:
            oc_ver = r[0]
        if oc_ver != version:
            raise
        checked = True
    except:
        raise
    finally:
        cursor.close()
        db.close()
    return True

def migrate_result_144_to_145 (dbpath):
    check_result_db_version(dbpath, '1.4.4')
    db = sqlite3.connect(dbpath)
    cursor = db.cursor()
    cursor.execute('update info set colval="1.4.5" where colkey="open-cravat"')
    db.commit()
    cursor.close()
    db.close()

def migrate_result_145_to_150 (dbpath):
    check_result_db_version(dbpath, '1.4.5')
    db = sqlite3.connect(dbpath)
    cursor = db.cursor()
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
                if col_def['hidden'] is None:
                    col_def['hidden'] = False
                if col_def['hidden'] == 1:
                    col_def['hidden'] = True
                elif col_def['hidden'] == 0:
                    col_def['hidden'] = False
                if col_def['filterable'] is None:
                    col_def['filterable'] = True
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
    q = 'update info set colval="1.5.0" where colkey="open-cravat"'
    cursor.execute(q)
    db.commit()
    cursor.close()
    db.close()

def migrate_result_150_to_151 (dbpath):
    check_result_db_version(dbpath, '1.5.0')
    db = sqlite3.connect(dbpath)
    cursor = db.cursor()
    cursor.execute('update info set colval="1.5.1" where colkey="open-cravat"')
    db.commit()
    cursor.close()
    db.close()

def migrate_result_151_to_152 (dbpath):
    check_result_db_version(dbpath, '1.5.1')
    db = sqlite3.connect(dbpath)
    cursor = db.cursor()
    cursor.execute('update info set colval="1.5.2" where colkey="open-cravat"')
    db.commit()
    cursor.close()
    db.close()

def migrate_result_152_to_153 (dbpath):
    check_result_db_version(dbpath, '1.5.2')
    db = sqlite3.connect(dbpath)
    cursor = db.cursor()
    q = 'select col_def from variant_header where col_name="base__coding"'
    cursor.execute(q)
    r = cursor.fetchone()
    coldef = json.loads(r[0])
    coldef['categories'] = ['Yes']
    q = 'update variant_header set col_def=? where col_name="base__coding"'
    cursor.execute(q,[json.dumps(coldef)])
    cursor.execute('update info set colval="1.5.3" where colkey="open-cravat"')
    db.commit()
    cursor.close()
    db.close()

def migrate_result_153_to_160():
    db = sqlite3.connect(dbpath)
    c.execute('update info set colval="1.6.0" where colkey="open-cravat"')

def migrate_result_160_to_161():
    db = sqlite3.connect(dbpath)
    c.execute('update info set colval="1.6.1" where colkey="open-cravat"')

def migrate_result_161_to_170 (dbpath):
    db = sqlite3.connect(dbpath)
    c = db.cursor()
    for level in ('gene','mapping','sample','variant'):
        c.execute(f'create unique index unq_{level}_name on {level}_annotator (name)')
        c.execute(f'create unique index unq_{level}_col_name on {level}_header (col_name)')
        if level in ('gene','variant'):
            c.execute(f'create unique index unq_{level}_reportsub_module on {level}_reportsub (module)')
    c.execute('create unique index unq_smartfilters_name on smartfilters (name)')
    c.execute('create unique index unq_info_colkey on info (colkey))')
    c.execute('update info set colval="1.7.0" where colkey="open-cravat"')

migrate_functions['1.4.4'] = migrate_result_144_to_145
migrate_functions['1.4.5'] = migrate_result_145_to_150
migrate_functions['1.5.0'] = migrate_result_150_to_151
migrate_functions['1.5.1'] = migrate_result_151_to_152
migrate_functions['1.5.2'] = migrate_result_152_to_153
migrate_functions['1.5.3'] = migrate_result_153_to_160
migrate_functions['1.6.0'] = migrate_result_160_to_161
migrate_functions['1.6.1'] = migrate_result_161_to_170

def migrate_result (args):
    def get_dbpaths (dbpaths, path):
        for fn in os.listdir(path):
            p = os.path.join(path, fn)
            if os.path.isdir(p) and args.recursive:
                get_dbpaths(dbpaths, p)
            else:
                if fn.endswith('.sqlite'):
                    dbpaths.append(p)
    dbpath = args.dbpath
    if os.path.exists(dbpath) == False:
        print('[{}] does not exist.'.format(dbpath))
        return
    if os.path.isdir(dbpath):
        dbpaths = []
        get_dbpaths(dbpaths, dbpath)
    else:
        dbpaths = [dbpath]
    print('Result database files to convert are:')
    for dbpath in dbpaths:
        print('    ' + dbpath)
    for dbpath in dbpaths:
        print('converting [{}]...'.format(dbpath))
        global supported_oc_ver
        try:
            db = sqlite3.connect(dbpath)
            cursor = db.cursor()
        except:
            print('  [{}] is not open-cravat result DB.'.format(dbpath))
            continue
        try:
            q = 'select colval from info where colkey="open-cravat"'
            cursor.execute(q)
            r = cursor.fetchone()
            if r is None:
                print('  Result DB is too old for migration.')
                continue
            else:
                oc_ver = r[0]
        except:
            print('  [{}] is not open-cravat result DB or too old for migration.'.format(dbpath))
            continue
        if oc_ver not in supported_oc_ver:
            print('  OpenCRAVAT version of {} is not supported for migration. Supported versions are {}.'.format(oc_ver, str(supported_oc_ver)))
            continue
        try:
            if args.backup:
                bak_path = dbpath + '.bak'
                print('  making backup copy [{}]...'.format(bak_path))
                shutil.copy(dbpath, bak_path)
            ver_idx = supported_oc_ver.index(oc_ver)
            for mig_ver in supported_oc_ver[ver_idx:]:
                print('  converting from open-cravat version {}...'.format(mig_ver))
                migrate_functions[mig_ver](dbpath)
        except:
            traceback.print_exc()
            print('  converting [{}] was not successful.'.format(dbpath))

def result2gui(args):
    dbpath = args.path
    user = args.user
    jobs_dir = Path(au.get_jobs_dir())
    user_dir = jobs_dir/user
    if not user_dir.is_dir():
        exit(f'User {user} not found')
    attempts = 0
    while True: #TODO this will currently overwrite if called in parallel. is_dir check and creation is not atomic
        job_id = datetime.datetime.now().strftime(r'%y%m%d-%H%M%S')
        job_dir = user_dir/job_id
        if not job_dir.is_dir():
            break
        else:
            attempts += 1
            time.sleep(1)
        if attempts >= 5:
            exit('Could not acquire a job id. Too many concurrent job submissions. Wait, or reduce submission frequency.')
    job_dir.mkdir()
    new_dbpath = job_dir/dbpath.name
    shutil.copyfile(dbpath, new_dbpath)
    log_path = dbpath.with_suffix('.log')
    if log_path.exists():
        shutil.copyfile(log_path, job_dir/log_path.name)
    err_path = dbpath.with_suffix('.err')
    if err_path.exists():
        shutil.copyfile(err_path, job_dir/err_path.name)
    status_path = dbpath.with_suffix('.status.json')
    if status_path.exists():
        shutil.copyfile(status_path, job_dir/status_path.name)
    else:
        statusd = status_from_db(new_dbpath)
        new_status_path = job_dir/status_path.name
        with new_status_path.open('w') as wf:
            json.dump(statusd, wf, indent=2, sort_keys=True)

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
    try:
        d['annotators'] = []
        d['annotator_version'] = {}
        c.execute('select name, version from gene_annotator')
        skip_names = {'base','tagsampler','vcfinfo',''}
        for r in c:
            if r[0] in skip_names: continue
            d['annotators'].append(r[0])
            d['annotator_version'][r[0]] = r[1]
        c.execute('select name, version from variant_annotator')
        for r in c:
            if r[0] in skip_names: continue
            d['annotators'].append(r[0])
            d['annotator_version'][r[0]] = r[1]
        d['annotators'] = sorted(list(set(d['annotators'])))
        c.execute('select colval from info where colkey="Input genome"')
        d['assembly'] = c.fetchone()[0]
        d['db_path'] = str(dbpath)
        d['id'] = str(dbpath.parent)
        d['id'] = str(dbpath.parent.name)
        d['job_dir'] = str(dbpath.parent)
        d['note'] = ''
        d['num_error_input'] = 0
        c.execute('select colval from info where colkey="Number of unique input variants"')
        d['num_unique_var'] = c.fetchone()[0]
        d['num_input_var'] = d['num_unique_var']
        c.execute('select colval from info where colkey="open-cravat"')
        d['open_cravat_version'] = c.fetchone()[0]
        d['orig_input_fname'] = [str(dbpath.stem)]
        d['orig_input_path'] = [str(dbpath.with_suffix(''))]
        d['reports'] = []
        d['run_name'] = str(dbpath.stem)
        d['status'] = 'Finished'
        d['submission_time'] = datetime.datetime.fromtimestamp(dbpath.stat().st_ctime).isoformat()
        d['viewable'] = True
    except:
        raise
    finally:
        c.close()
        db.close()
    return d

parser = argparse.ArgumentParser()
# converts db coordinate to hg38
subparsers = parser.add_subparsers(title='Commands')
parser_convert = subparsers.add_parser('converttohg38',
    help='converts hg19 coordinates in sqlite3 database to hg38 ones.')
parser_convert.add_argument('--db',
    nargs='?',
    required=True,
    help='path to sqlite3 database file')
parser_convert.add_argument('--sourcegenome',
    required=True,
    help='genome assembly of source database')
parser_convert.add_argument('--cols',
    nargs='+',
    required=True,
    help='names of the columns to convert')
parser_convert.add_argument('--tables',
    nargs='*',
    help='table(s) to convert. If omitted, table name will be used as chromosome name.')
parser_convert.add_argument('--chromcol',
    required=False,
    help='chromosome column. If omitted, all tables will be tried to be converted.')
parser_convert.set_defaults(func=converttohg38)
# migrate old result db
parser_migrate_result = subparsers.add_parser('migrate-result',
    help='migrates result db made with older versions of open-cravat')
parser_migrate_result.add_argument('dbpath', help='path to a result db file or a directory')
parser_migrate_result.add_argument('-r', dest='recursive',
    action='store_true', default=False, help='recursive operation')
parser_migrate_result.add_argument('-c', dest='backup',
    action='store_true', default=False, help='backup original copy with .bak extension')
parser_migrate_result.set_defaults(func=migrate_result)
# Make job accessible through the gui
parser_result2gui = subparsers.add_parser('result2gui', 
    help='Copy a command line job into the GUI submission list')
parser_result2gui.add_argument('path', 
    help='Path to result database', 
    type=Path)
parser_result2gui.add_argument('-u','--user', 
    help='User who will own the job. Defaults to single user default user.', 
    type=str, default='default')
parser_result2gui.set_defaults(func=result2gui)

def main ():
    args = get_args()
    args.func(args)

if __name__ == '__main__':
    main()
