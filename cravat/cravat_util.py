import subprocess
import sqlite3
import cravat.constants as constants
import pyliftover
import argparse
import os
import sys

def get_args ():
    if len(sys.argv) == 1:
        sys.argv.append('-h')
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(title='Commands')
    subparser = subparsers.add_parser('hg19tohg38',
        help='converts hg19 coordinates in sqlite3 database to hg38 ones.')
    subparser.add_argument('--db',
        nargs='?',
        required=True,
        help='path to sqlite3 database file')
    subparser.add_argument('--cols',
        nargs='+',
        required=True,
        help='names of the columns to convert')
    subparser.add_argument('--tables',
        help='table(s) to convert. If omitted, table name will be used as chromosome name.')
    subparser.add_argument('--chromcol',
        required=False,
        help='chromosome column. If omitted, all tables will be tried to be converted.')
    subparser.set_defaults(func=hg19tohg38)
    args = parser.parse_args()
    return args

def hg19tohg38 (args):
    if os.path.exists(args.db) == False:
        print(args.db, 'does not exist.')
        exit()
    liftover = pyliftover.LiftOver(constants.liftover_chain_paths['hg19'])
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
                pos = row[colno]
                liftover_out = liftover.convert_coordinate(chrom, pos)
                if liftover_out == None:
                    print('None:', row)
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

def main ():
    args = get_args()
    args.func(args)

if __name__ == '__main__':
    main()
