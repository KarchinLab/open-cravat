from http.server import HTTPServer, CGIHTTPRequestHandler
from socketserver import TCPServer
import os
import webbrowser
import multiprocessing
import sqlite3
import urllib.parse
import json
import sys
import argparse
import imp
import yaml
import re
from cravat import ConfigLoader
from cravat import admin_util as au
from cravat import CravatFilter

def get (handler):
    head = handler.trim_path_head()
    if head == 'service':
        serve_service(handler)
    elif head == 'widgetfile':
        serve_widgetfile(handler)
    elif head == 'runwidget':
        serve_runwidget(handler)
    else:
        handler.request_path = head + '/' + handler.request_path
        handler.request_path = handler.request_path.rstrip('/')
        filepath = get_filepath(handler.request_path)
        serve_view(handler, filepath)

### files ###

def get_filepath (path):
    filepath = os.sep.join(path.split('/'))
    filepath = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 
        'webviewer',
        filepath
        )
    return filepath

def serve_view (handler, filepath):
    handler.send_response(200)
    if filepath[-4:] == '.css':
        handler.send_header('Content-type', 'text/css')
    elif filepath[-3:] == '.js':
        handler.send_header('Content-type', 'application/javascript')
    elif filepath[-4:] == '.png':
        handler.send_header('Content-type', 'image/png')
    elif filepath[-4:] == '.jpg':
        handler.send_header('Content-type', 'image/jpg')
    elif filepath[-4:] == '.gif':
        handler.send_header('Content-type', 'image/gif')
    else:
        handler.send_header('Content-type', 'text/html')
    handler.end_headers()
    with open(filepath, 'rb') as f:
        response = f.read()
        handler.wfile.write(response)

### service ###

def serve_service (handler):
    head = handler.trim_path_head()
    queries = handler.request_queries
    handler.send_response(200)
    handler.send_header('Content-type', 'application/json')
    handler.end_headers()
    if head == 'variantcols':
        content = get_variant_cols(queries)
    #if head == 'conf':
    #    content = get_webviewerconf()
    elif head == 'getsummarywidgetnames':
        content = get_summary_widget_names(queries)
    elif head == 'getresulttablelevels':
        content = get_result_levels(queries)
    elif head == 'result':
        content = get_result(queries)
    elif head == 'count':
        content = get_count(queries)
    elif head == 'widgetlist':
        content = get_widgetlist()
    elif head == 'status':
        content = get_status(queries)
    elif head == 'savefiltersetting':
        content = save_filter_setting(queries)
    elif head == 'savelayoutsetting':
        content = save_layout_setting(queries)
    elif head == 'loadfiltersetting':
        content = load_filtersetting(queries)
    elif head == 'loadlayoutsetting':
        content = load_layout_setting(queries)
    elif head == 'deletelayoutsetting':
        content = delete_layout_setting(queries)
    elif head == 'renamelayoutsetting':
        content = rename_layout_setting(queries)
    elif head == 'getlayoutsavenames':
        content = get_layout_save_names(queries)
    elif head == 'getfiltersavenames':
        content = get_filter_save_names(queries)
    elif head == 'getnowgannotmodules':
        content = get_nowg_annot_modules(queries)
    handler.response = bytes(json.dumps(content), 'UTF-8')
    handler.wfile.write(handler.response)

def get_nowg_annot_modules (queries):
    dbpath = urllib.parse.unquote(queries['dbpath'][0])
    conn = sqlite3.connect(dbpath)
    cursor = conn.cursor()
    wgmodules = au.get_local_module_infos_of_type('webviewerwidget')
    annot_modules_with_wg = []
    for wgmodule in wgmodules:
        conf = wgmodules[wgmodule].conf
        if 'required_annotator' in conf:
            if wgmodule not in annot_modules_with_wg:
                annot_modules_with_wg.append(wgmodule)
    nowg_annot_modules = {}
    if table_exists(cursor, 'variant'):
        q = 'select name, displayname from variant_annotator'
        cursor.execute(q)
        for r in cursor.fetchall():
            m = r[0]
            if m in ['example_annotator', 'testannot', 'tagsampler']:
                continue
            annot_module = 'wg' + r[0]
            displayname = r[1]
            if annot_module not in annot_modules_with_wg and annot_module not in nowg_annot_modules:
                nowg_annot_modules[annot_module] = displayname
    content = nowg_annot_modules
    return content

def get_filter_save_names (queries):
    dbpath = urllib.parse.unquote(queries['dbpath'][0])
    conn = sqlite3.connect(dbpath)
    cursor = conn.cursor()
    table = 'viewersetup'
    if table_exists(cursor, table) == False:
        content = []
    else:
        q = 'select distinct name from ' + table + ' where datatype="filter"'
        cursor.execute(q)
        r = cursor.fetchall()
        content = str([v[0] for v in r])
    cursor.close()
    conn.close()
    return content

def get_layout_save_names (queries):
    dbpath = urllib.parse.unquote(queries['dbpath'][0])
    conn = sqlite3.connect(dbpath)
    cursor = conn.cursor()
    table = 'viewersetup'
    content = []
    if table_exists(cursor, table):
        q = 'select distinct name from ' + table + ' where datatype="layout"'
        cursor.execute(q)
        r = cursor.fetchall()
        content = [v[0] for v in r]
    cursor.close()
    conn.close()
    return content

def rename_layout_setting (queries):
    dbpath = urllib.parse.unquote(queries['dbpath'][0])
    name = urllib.parse.unquote(queries['name'][0])
    new_name = urllib.parse.unquote(queries['newname'][0])
    conn = sqlite3.connect(dbpath)
    cursor = conn.cursor()
    table = 'viewersetup'
    if table_exists(cursor, table) == True:
        q = 'update ' + table + ' set name="' + new_name + '" where datatype="layout" and name="' + name + '"'
        cursor.execute(q)
    conn.commit()
    cursor.close()
    conn.close()
    content = {}
    return content

def delete_layout_setting (queries):
    dbpath = urllib.parse.unquote(queries['dbpath'][0])
    name = urllib.parse.unquote(queries['name'][0])
    conn = sqlite3.connect(dbpath)
    cursor = conn.cursor()
    table = 'viewersetup'
    if table_exists(cursor, table) == True:
        q = 'DELETE FROM ' + table + ' WHERE datatype="layout" and name="' + name + '"'
        cursor.execute(q)
    conn.commit()
    cursor.close()
    conn.close()
    content = {}
    return content

def load_layout_setting (queries):
    dbpath = urllib.parse.unquote(queries['dbpath'][0])
    name = urllib.parse.unquote(queries['name'][0])
    conn = sqlite3.connect(dbpath)
    cursor = conn.cursor()
    table = 'viewersetup'
    if table_exists(cursor, table) == False:
        content = {"widgetSettings": []}
    else:
        q = 'select viewersetup from ' + table + ' where datatype="layout" and name="' + name + '"'
        cursor.execute(q)
        r = cursor.fetchone()
        if r != None:
            data = r[0]
            content = json.loads(data)
        else:
            content = {"widgetSettings": []}
    cursor.close()
    conn.close()
    return content

def load_filtersetting (queries):
    dbpath = urllib.parse.unquote(queries['dbpath'][0])
    name = urllib.parse.unquote(queries['name'][0])
    conn = sqlite3.connect(dbpath)
    cursor = conn.cursor()
    table = 'viewersetup'
    if table_exists(cursor, table) == False:
        content = {"filterSet": []}
    else:
        q = 'select viewersetup from ' + table + ' where datatype="filter" and name="' + name + '"'
        cursor.execute(q)
        r = cursor.fetchone()
        if r != None:
            data = r[0]
            content = json.loads(data)
        else:
            content = {"filterSet": []}
    cursor.close()
    conn.close()
    return content

def save_layout_setting (queries):
    dbpath = urllib.parse.unquote(queries['dbpath'][0])
    name = urllib.parse.unquote(queries['name'][0])
    savedata = urllib.parse.unquote(queries['savedata'][0])
    conn = sqlite3.connect(dbpath)
    cursor = conn.cursor()
    table = 'viewersetup'
    if table_exists(cursor, table) == False:
        q = 'create table ' + table + ' (datatype text, name text, viewersetup text, unique (datatype, name))'
        cursor.execute(q)
    q = 'replace into ' + table + ' values ("layout", "' + name + '", \'' + savedata + '\')'
    cursor.execute(q)
    conn.commit()
    cursor.close()
    conn.close()
    content = 'saved'
    return content

def save_filter_setting (queries):
    dbpath = urllib.parse.unquote(queries['dbpath'][0])
    name = urllib.parse.unquote(queries['name'][0])
    savedata = urllib.parse.unquote(queries['savedata'][0])
    conn = sqlite3.connect(dbpath)
    cursor = conn.cursor()
    table = 'viewersetup'
    if table_exists(cursor, table) == False:
        q = 'create table ' + table + ' (datatype text, name text, viewersetup text, unique (datatype, name))'
        cursor.execute(q)
    q = 'replace into ' + table + ' values ("filter", "' + name + '", \'' + savedata + '\')'
    cursor.execute(q)
    conn.commit()
    cursor.close()
    conn.close()
    content = 'saved'
    return content

def get_status (queries):
    dbpath = urllib.parse.unquote(queries['dbpath'][0])
    conn = sqlite3.connect(dbpath)
    cursor = conn.cursor()
    q = 'select * from info'
    cursor.execute(q)
    content = {}
    for row in cursor.fetchall():
        content[row[0]] = row[1]
    return content

def get_widgetlist ():
    content = []
    modules = au.get_local_module_infos_of_type('webviewerwidget')
    for module_name in modules:
        module = modules[module_name]
        conf = module.conf
        if 'required_annotator' in conf:
            req = conf['required_annotator']
        else: 
            # Removes wg.
            req = module_name[2:]
        content.append({'name': module_name, 
                        'title': module.title, 
                        'required_annotator': req})
    return content

def get_count (queries):
    dbpath = urllib.parse.unquote(queries['dbpath'][0])
    tab = queries['tab'][0]
    if 'filter' in queries:
        filterstring = queries['filter'][0]
    else:
        filterstring = None
    cf = CravatFilter(dbpath=dbpath, 
                      mode='sub', 
                      filterstring=filterstring)
    n = cf.getcount(level=tab)
    content = {'n': n}        
    return content   

def get_result (queries):
    dbpath = urllib.parse.unquote(queries['dbpath'][0])
    tab = queries['tab'][0]
    if 'filter' in queries:
        filterstring = queries['filter'][0]
    else:
        filterstring = None
    if 'confpath' in queries:
        confpath = queries['confpath'][0]
    else:
        confpath = None
    reporter_name = 'jsonreporter'
    f, fn, d = imp.find_module(
        reporter_name, 
        [os.path.join(os.path.dirname(__file__), 'webviewer')])
    m = imp.load_module(reporter_name, f, fn, d)
    args = ['', dbpath]
    if confpath != None:
        args.extend(['-c', confpath])
    if filterstring != None:
        args.extend(['--filterstring', filterstring])
    reporter = m.Reporter(args)
    data = reporter.run(tab=tab)
    content = {}
    content['stat'] = {'rowsreturned': True, 
                   'wherestr':'', 
                   'filtered': True,
                   'filteredresultmessage': '',
                   'maxnorows': 100000,
                   'norows': data['info']['norows']}
    content['columns'] = get_colmodel(tab, data['colinfo'])
    content["data"] = get_datamodel(data[tab])
    content["status"] = "normal"
    return content

def get_result_levels (queries):
    conn = sqlite3.connect(queries['dbpath'][0])
    cursor = conn.cursor()
    sql = 'select name from sqlite_master where type="table" and ' +\
        'name like "%_header"'
    cursor.execute(sql)
    ret = cursor.fetchall()
    if len(ret) > 0:
        content = [v[0].split('_')[0] for v in ret]
        content.insert(0, 'info')
    else:
        content = []
    return content

def get_variant_cols (queries):
    dbpath = urllib.parse.unquote(queries['dbpath'][0])
    if 'confpath' in queries:
        confpath = queries['confpath'][0]
    else:
        confpath = None
    if 'filter' in queries:
        filterstring = queries['filter'][0]
    else:
        filterstring = None
    data = {}
    data['data'] = {}
    data['stat'] = {}
    data['status'] = {}
    colinfo = get_colinfo(dbpath, confpath, filterstring)
    data['columns'] = {}
    if 'variant' in colinfo:
        data['columns']['variant'] = get_colmodel('variant', colinfo)
    if 'gene' in colinfo:
        data['columns']['gene'] = get_colmodel('gene', colinfo)
    content = data
    return content

def get_webviewerconf ():
    conf_path = os.path.join(
            au.get_system_conf()['home'], 
            'viewers',
            'webviewer',
            'webviewer.yml')
    with open(conf_path) as f:
        conf = yaml.load(f)
    return conf

def get_summary_widget_names (queries):
    runid = queries['jobid'][0]

def get_datamodel (data):
    ret = []
    for row in data:
        ret.append(list(row))
    return ret

def get_colmodel (tab, colinfo):
    colModel = []
    groupkeys_ordered = []
    groupnames = {}
    for d in colinfo[tab]['colgroups']:
        groupnames[d['name']] = [d['displayname'], d['count']]
        groupkeys_ordered.append(d['name'])
    dataindx = 0
    for groupkey in groupkeys_ordered:
        [grouptitle, col_count] = groupnames[groupkey]
        columngroupdef = {'title': grouptitle, 'colModel': []}
        startidx = dataindx
        endidx = startidx + col_count
        for d in colinfo[tab]['columns'][startidx:endidx]:
            column = {
                "col": d['col_name'],
                'colgroupkey': groupkey, 
                'colgroup': grouptitle,
                "title": d['col_title'], 
                "align":"center",
                "hidden":False,
                "dataIndx": dataindx,
                "retfilt":False,
                "retfilttype":"None",
                "multiseloptions":[]
                }
            if d['col_type'] == 'string':
                column['filter'] = {
                    "type":"textbox",
                    "condition":"contain",
                    "listeners":["keyup"]}
                column['retfilt'] = True
                column['retfilttype'] = 'regexp'
                column['multiseloptions'] = []
            elif d['col_type'] == 'float' or d['col_type'] == 'int':
                column['filter'] = {
                    "type":"textbox",
                    "condition":"between",
                    "listeners":["keyup"]}
                column['retfilt'] = True
                column['retfilttype'] = 'between'
                column['multiseloptions'] = []
            columngroupdef['colModel'].append(column)
            dataindx += 1
        colModel.append(columngroupdef)
    return colModel

def get_colinfo (dbpath, confpath, filterstring):
    reporter_name = 'jsonreporter'
    f, fn, d = imp.find_module(
        reporter_name, 
        [os.path.join(os.path.dirname(__file__), 'webviewer')])
    m = imp.load_module(reporter_name, f, fn, d)
    args = ['', dbpath]
    if confpath != None:
        args.extend(['-c', confpath])
    if filterstring != None:
        args.extend(['--filterstring', filterstring])
    reporter = m.Reporter(args)
    colinfo = reporter.get_variant_colinfo()
    return colinfo

def table_exists (cursor, table):
    sql = 'select name from sqlite_master where type="table" and ' +\
        'name="' + table + '"'
    cursor.execute(sql)
    if cursor.fetchone() == None:
        return False
    else:
        return True

### widgetfiles ###

def serve_widgetfile (handler):
    module_name, ext = os.path.splitext(handler.request_path)
    filepath = os.path.join(
        au.get_modules_dir(),
        'webviewerwidgets',
        handler.request_path)
        #module_name,
        #module_name + ext)
    if os.path.exists(filepath):
        serve_view(handler, filepath)

### runwidget ###

def serve_runwidget (handler):
    path = 'wg' + handler.request_path
    queries = handler.request_queries
    f, fn, d = imp.find_module(path, 
        [os.path.join(au.get_modules_dir(), 
                      'webviewerwidgets', path)])
    m = imp.load_module(path, f, fn, d)
    ret = m.get_data(queries)
    handler.send_response(200)
    handler.send_header('Content-type', 'application/json')
    handler.end_headers()
    content = json.dumps(ret)
    response = bytes(content, 'UTF-8')
    handler.wfile.write(response)

