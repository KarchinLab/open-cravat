import os
import webbrowser
import multiprocessing
import aiosqlite3
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
from aiohttp import web
import time

def get_filepath (path):
    filepath = os.sep.join(path.split('/'))
    filepath = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 
        filepath
        )
    return filepath

async def get_nowg_annot_modules (request):
    # disabling this until required_annotator is included in the remote manifest.
    return web.json_response({})
    # Below is not run. Delete the above and change the below so that remote manifest's required_annotator is used.
    queries = request.rel_url.query
    dbpath = queries['dbpath']
    conn = await aiosqlite3.connect(dbpath)
    cursor = await conn.cursor()
    remote_widget_modules = au.get_remote_module_infos_of_type('webviewerwidget')
    remote_widget_names = remote_widget_modules.keys()
    remote_annot_to_widgets = {}
    for remote_widget_name in remote_widget_names:
        conf = au.get_remote_module_config(remote_widget_name)
        if 'required_annotator' in conf:
            req_annot = conf['required_annotator']
            if req_annot not in remote_annot_to_widgets:
                remote_annot_to_widgets[req_annot] = []
            remote_annot_to_widgets[req_annot].append(remote_widget_name)
    wgmodules = au.get_local_module_infos_of_type('webviewerwidget')
    annot_modules_with_wg = []
    for wgmodule in wgmodules:
        conf = wgmodules[wgmodule].conf
        if 'required_annotator' in conf:
            annot_module = conf['required_annotator']
            if annot_module not in annot_modules_with_wg:
                annot_modules_with_wg.append(annot_module)
    nowg_annot_modules = {}
    r = await table_exists(cursor, 'variant')
    if r:
        q = 'select name, displayname from variant_annotator'
        await cursor.execute(q)
        for r in await cursor.fetchall():
            m = r[0]
            if m in ['example_annotator', 'testannot', 'tagsampler']:
                continue
            annot_module = r[0]
            displayname = r[1]
            if annot_module not in annot_modules_with_wg and annot_module not in nowg_annot_modules and annot_module in remote_annot_to_widgets:
                nowg_annot_modules[annot_module] = displayname
    content = nowg_annot_modules
    await cursor.close()
    await conn.close()
    return web.json_response(content)

async def get_filter_save_names (request):
    queries = request.rel_url.query
    dbpath = queries['dbpath']
    conn = await aiosqlite3.connect(dbpath)
    cursor = await conn.cursor()
    table = 'viewersetup'
    content = []
    r = await table_exists(cursor, table)
    if r == False:
        pass
    else:
        q = 'select distinct name from ' + table + ' where datatype="filter"'
        await cursor.execute(q)
        rs = await cursor.fetchall()
        for r in rs:
            content.append(r[0])
    await cursor.close()
    await conn.close()
    return web.json_response(content)

async def get_layout_save_names (request):
    queries = request.rel_url.query
    dbpath = queries['dbpath']
    conn = await aiosqlite3.connect(dbpath)
    cursor = await conn.cursor()
    table = 'viewersetup'
    content = []
    r = await table_exists(cursor, table)
    if r:
        q = 'select distinct name from ' + table + ' where datatype="layout"'
        await cursor.execute(q)
        rs = await cursor.fetchall()
        for r in rs:
            content.append(r[0])
    await cursor.close()
    await conn.close()
    return web.json_response(content)

async def rename_layout_setting (request):
    queries = request.rel_url.query
    dbpath = queries['dbpath']
    name = queries['name']
    new_name = queries['newname']
    conn = await aiosqlite3.connect(dbpath)
    cursor = await conn.cursor()
    table = 'viewersetup'
    r = await table_exists(cursor, table)
    if r == True:
        q = 'update ' + table + ' set name="' + new_name + '" where datatype="layout" and name="' + name + '"'
        await cursor.execute(q)
    await conn.commit()
    await cursor.close()
    await conn.close()
    content = {}
    return web.json_response(content)

async def delete_layout_setting (request):
    queries = request.rel_url.query
    dbpath = queries['dbpath']
    name = queries['name']
    conn = await aiosqlite3.connect(dbpath)
    cursor = await conn.cursor()
    table = 'viewersetup'
    r = await table_exists(cursor, table)
    if r == True:
        q = 'DELETE FROM ' + table + ' WHERE datatype="layout" and name="' + name + '"'
        await cursor.execute(q)
    await conn.commit()
    await cursor.close()
    await conn.close()
    content = {}
    return web.json_response(content)

async def load_layout_setting (request):
    queries = request.rel_url.query
    dbpath = queries['dbpath']
    name = queries['name']
    conn = await aiosqlite3.connect(dbpath)
    cursor = await conn.cursor()
    table = 'viewersetup'
    r = await table_exists(cursor, table)
    if r == False:
        content = {"widgetSettings": {}}
    else:
        q = 'select viewersetup from ' + table + ' where datatype="layout" and name="' + name + '"'
        await cursor.execute(q)
        r = await cursor.fetchone()
        if r != None:
            data = r[0]
            content = json.loads(data)
        else:
            content = {"widgetSettings": {}}
    await cursor.close()
    await conn.close()
    print('@@ widgetSettings=', content)
    return web.json_response(content)

async def load_filter_setting (request):
    queries = request.rel_url.query
    dbpath = queries['dbpath']
    name = queries['name']
    conn = await aiosqlite3.connect(dbpath)
    cursor = await conn.cursor()
    table = 'viewersetup'
    r = await table_exists(cursor, table)
    if r == False:
        content = {"filterSet": []}
    else:
        q = 'select viewersetup from ' + table + ' where datatype="filter" and name="' + name + '"'
        await cursor.execute(q)
        r = await cursor.fetchone()
        if r != None:
            data = r[0]
            content = json.loads(data)
        else:
            content = {"filterSet": []}
    await cursor.close()
    await conn.close()
    return web.json_response(content)

async def save_layout_setting (request):
    #queries = request.rel_url.query
    queries = await request.post()
    dbpath = queries['dbpath']
    name = queries['name']
    savedata = queries['savedata']
    conn = await aiosqlite3.connect(dbpath)
    cursor = await conn.cursor()
    table = 'viewersetup'
    r = await table_exists(cursor, table)
    if r == False:
        q = 'create table ' + table + ' (datatype text, name text, viewersetup text, unique (datatype, name))'
        await cursor.execute(q)
    q = 'replace into ' + table + ' values ("layout", "' + name + '", \'' + savedata + '\')'
    await cursor.execute(q)
    await conn.commit()
    await cursor.close()
    conn.close()
    content = 'saved'
    return web.json_response(content)

async def save_filter_setting (request):
    queries = request.rel_url.query
    dbpath = queries['dbpath']
    name = queries['name']
    savedata = queries['savedata']
    conn = await aiosqlite3.connect(dbpath)
    cursor = await conn.cursor()
    table = 'viewersetup'
    r = await table_exists(cursor, table)
    if r == False:
        q = 'create table ' + table + ' (datatype text, name text, viewersetup text, unique (datatype, name))'
        await cursor.execute(q)
    q = 'select * from {} where datatype="filter" and name="{}"'.format(table, name)
    await cursor.execute(q)
    r = await cursor.fetchone()
    if r is not None:
        q = 'delete from {} where datatype="filter" and name="{}"'.format(table, name)
        await cursor.execute(q)
        conn.commit()
    q = 'replace into ' + table + ' values ("filter", "' + name + '", \'' + savedata + '\')'
    await cursor.execute(q)
    await conn.commit()
    await cursor.close()
    await conn.close()
    content = 'saved'
    return web.json_response(content)

async def delete_filter_setting (request):
    queries = request.rel_url.query
    dbpath = queries['dbpath']
    name = queries['name']
    conn = await aiosqlite3.connect(dbpath)
    cursor = await conn.cursor()
    table = 'viewersetup'
    r = await table_exists(cursor, table)
    if r:
        q = 'delete from ' + table + ' where name="' + name + '" and datatype="filter"'
        await cursor.execute(q)
        conn.commit()
        content = 'deleted'
    else:
        content = 'no such table'
    await cursor.close()
    await conn.close()
    return web.json_response(content)

async def get_status (request):
    queries = request.rel_url.query
    dbpath = queries['dbpath']
    conn = await aiosqlite3.connect(dbpath)
    cursor = await conn.cursor()
    q = 'select * from info'
    await cursor.execute(q)
    content = {}
    for row in await cursor.fetchall():
        content[row[0]] = row[1]
    await cursor.close()
    await conn.close()
    return web.json_response(content)

def get_widgetlist (request):
    queries = request.rel_url.query
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
                        'required_annotator': req,
                        'helphtml_exists': module.helphtml_exists})
    return web.json_response(content)

async def get_count (request):
    queries = request.rel_url.query
    dbpath = queries['dbpath']
    tab = queries['tab']
    if 'filter' in queries:
        filterstring = queries['filter']
    else:
        filterstring = None
    cf = await CravatFilter.create(dbpath=dbpath, 
                      mode='sub', 
                      filterstring=filterstring)
    dbbasename = os.path.basename(dbpath)
    print('calling count for {}'.format(dbbasename))
    t = time.time()
    n = await cf.getcount(level=tab)
    t = round(time.time() - t, 3)
    print('count obtained from {} in {}s'.format(dbbasename, t))
    content = {'n': n}        
    return web.json_response(content)

async def get_result (request):
    queries = request.rel_url.query
    dbpath = queries['dbpath']
    tab = queries['tab']
    if 'filter' in queries:
        filterstring = queries['filter']
    else:
        filterstring = None
    if 'confpath' in queries:
        confpath = queries['confpath']
    else:
        confpath = None
    reporter_name = 'jsonreporter'
    f, fn, d = imp.find_module(
        reporter_name, 
        [os.path.join(os.path.dirname(__file__),)])
    m = imp.load_module(reporter_name, f, fn, d)
    args = ['', dbpath, '--module-name', reporter_name]
    if confpath != None:
        args.extend(['-c', confpath])
    if filterstring != None:
        args.extend(['--filterstring', filterstring])
    reporter = m.Reporter(args, None)
    await reporter.prep()
    dbbasename = os.path.basename(dbpath)
    print('getting result [{}] from {} for viewer...'.format(tab, dbbasename))
    t = time.time()
    data = await reporter.run(tab=tab)
    t = round(time.time() - t, 3)
    print('result [{}] obtained from {} in {}s. packing...'.format(tab, dbbasename, t))
    t = time.time()
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
    t = round(time.time() - t, 3)
    print('done in {}s. sending result of {}...'.format(t, dbbasename))
    return web.json_response(content)

async def get_result_levels (request):
    queries = request.rel_url.query
    conn = await aiosqlite3.connect(queries['dbpath'])
    cursor = await conn.cursor()
    sql = 'select name from sqlite_master where type="table" and ' +\
        'name like "%_header"'
    await cursor.execute(sql)
    ret = await cursor.fetchall()
    if len(ret) > 0:
        content = [v[0].split('_')[0] for v in ret]
        content.insert(0, 'info')
    else:
        content = []
    content.remove('sample')
    content.remove('mapping')
    await cursor.close()
    await conn.close()
    return web.json_response(content)

async def get_variant_cols (request):
    queries = request.rel_url.query
    dbpath = queries['dbpath']
    if 'confpath' in queries:
        confpath = queries['confpath']
    else:
        confpath = None
    if 'filter' in queries:
        filterstring = queries['filter']
    else:
        filterstring = None
    data = {}
    data['data'] = {}
    data['stat'] = {}
    data['status'] = {}
    colinfo = await get_colinfo(dbpath, confpath, filterstring)
    data['columns'] = {}
    if 'variant' in colinfo:
        data['columns']['variant'] = get_colmodel('variant', colinfo)
    if 'gene' in colinfo:
        data['columns']['gene'] = get_colmodel('gene', colinfo)
    content = data
    return web.json_response(content)

def get_summary_widget_names (request):
    queries = request.rel_url.query
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
            cats = d['col_cats']
            column = {
                "col": d['col_name'],
                'colgroupkey': groupkey, 
                'colgroup': grouptitle,
                "title": d['col_title'], 
                "align":"center",
                "dataIndx": dataindx,
                "retfilt":False,
                "retfilttype":"None",
                "multiseloptions":[],
                'reportsub': d['reportsub'] if 'reportsub' in d else {},
                'categories': cats,
                'width': d['col_width'],
                'desc': d['col_desc'],
                'type': d['col_type'],
                'hidden': d['col_hidden'],
                'ctg': d['col_ctg'],
                'filterable': d['col_filterable'],
                'link_format': d.get('link_format'),
                }
            if d['col_type'] == 'string':
                if d['col_ctg'] == 'single':
                    column['filter'] = {
                        'type': 'select',
                        'attr': 'multiple',
                        'condition': 'equal',
                        'options': cats,
                        'listeners': ['change']}
                    column['retfilt'] = True
                    column['retfilttype'] = 'select'
                    column['multiseloptions'] = cats
                elif d['col_ctg'] == 'multi':
                    column['filter'] = {
                        'type': 'select',
                        'attr': 'multiple',
                        'condition': 'contain',
                        'options': cats,
                        'listeners': ['change']}
                    column['retfilt'] = True
                    column['retfilttype'] = 'select'
                    column['multiseloptions'] = cats
                else:
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

async def get_colinfo (dbpath, confpath, filterstring):
    reporter_name = 'jsonreporter'
    f, fn, d = imp.find_module(
        reporter_name, 
        [os.path.join(os.path.dirname(__file__),)])
    m = imp.load_module(reporter_name, f, fn, d)
    args = ['', dbpath, '--module-name', reporter_name]
    if confpath != None:
        args.extend(['-c', confpath])
    if filterstring != None:
        args.extend(['--filterstring', filterstring])
    reporter = m.Reporter(args, None)
    await reporter.prep()
    colinfo = await reporter.get_variant_colinfo()
    return colinfo

async def table_exists (cursor, table):
    q = 'select name from sqlite_master where type="table" and ' +\
        'name="' + table + '"'
    await cursor.execute(q)
    r = await cursor.fetchone()
    if r == None:
        return False
    else:
        return True

def serve_widgetfile (request):
    filepath = os.path.join(
        au.get_modules_dir(),
        'webviewerwidgets',
        request.match_info['module_dir'],
        request.match_info['filename']
        )
    if os.path.exists(filepath):
        return web.FileResponse(filepath)

async def serve_runwidget (request):
    path = 'wg' + request.match_info['module']
    queries = request.rel_url.query
    f, fn, d = imp.find_module(path, 
        [os.path.join(au.get_modules_dir(), 
                      'webviewerwidgets', path)])
    m = imp.load_module(path, f, fn, d)
    content = await m.get_data(queries)
    return web.json_response(content)

routes = []
routes.append(['GET', '/result/service/variantcols', get_variant_cols])
routes.append(['GET', '/result/service/getsummarywidgetnames', get_summary_widget_names])
routes.append(['GET', '/result/service/getresulttablelevels', get_result_levels])
routes.append(['GET', '/result/service/result', get_result])
routes.append(['GET', '/result/service/count', get_count])
routes.append(['GET', '/result/service/widgetlist', get_widgetlist])
routes.append(['GET', '/result/service/status', get_status])
routes.append(['GET', '/result/service/savefiltersetting', save_filter_setting])
routes.append(['POST', '/result/service/savelayoutsetting', save_layout_setting])
routes.append(['GET', '/result/service/loadfiltersetting', load_filter_setting])
routes.append(['GET', '/result/service/loadlayoutsetting', load_layout_setting])
routes.append(['GET', '/result/service/deletelayoutsetting', delete_layout_setting])
routes.append(['GET', '/result/service/renamelayoutsetting', rename_layout_setting])
routes.append(['GET', '/result/service/getlayoutsavenames', get_layout_save_names])
routes.append(['GET', '/result/service/getfiltersavenames', get_filter_save_names])
routes.append(['GET', '/result/service/getnowgannotmodules', get_nowg_annot_modules])
routes.append(['GET', '/result/widgetfile/{module_dir}/{filename}', serve_widgetfile])
routes.append(['GET', '/result/runwidget/{module}', serve_runwidget])
routes.append(['GET', '/result/service/deletefiltersetting', delete_filter_setting])

