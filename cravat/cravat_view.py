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

class MyHandler (CGIHTTPRequestHandler):
    def do_POST (self):
        if hasattr(self, 'conf') == False:
            self.conf = ConfigLoader()
        #print('POST path=', self.path)
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        urltoks = urllib.parse.urlparse(self.path)
        path = urltoks.path
        if path.startswith('/rest/widgetservice/'):
            self.serve_widgetservice(
                re.sub('^/rest/widgetservice/', '', path),
                None,
                post_data)

    def do_GET (self):
        if hasattr(self, 'conf') == False:
            self.conf = ConfigLoader()
        #print('path=', self.path)
        urltoks = urllib.parse.urlparse(self.path)
        self.request_path = urltoks.path
        self.request_query = urltoks.query
        if self.path.startswith('/rest/service/'):
            self.serve_rest(
                re.sub('^/rest/service/', '', self.request_path), 
                self.request_query)
        elif self.path.startswith('/rest/widgetservice/'):
            self.serve_widgetservice(
                re.sub('^/rest/widgetservice/', '', self.request_path),
                self.request_query,
                None)
        elif self.path.startswith('/widgets/'):
            self.serve_widgets(
                re.sub('^/widgets/', '', self.request_path))
        elif self.path.startswith('/widget_support/'):
            self.serve_widget_support(
                re.sub('^/widget_support/', '', self.request_path))
        elif self.path.startswith('/'):
            filepath = self.get_filepath(self.request_path)
            self.serve_view(filepath, self.request_query)
    
    def get_filepath (self, path):
        filepath = \
            os.sep.join(re.sub('^/', '', path).split('/'))
        filepath = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 
            'webviewer',
            filepath
            )
        
        return filepath
    
    def serve_widgets (self, module_name):
        module_name, ext = os.path.splitext(module_name)
        module_name = 'wg' + module_name
        filepath = os.path.join(
            au.get_modules_dir(),
            'webviewerwidgets',
            module_name,
            module_name + ext)
        if os.path.exists(filepath):
            self.serve_view(filepath, None)
        elif ext == '.js':
            self.send_response(200)
            self.send_header('Content-type', 'application/javascript')
            self.end_headers()
            self.wfile.write(bytes('', 'UTF-8'))
        elif ext == '.yml':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(bytes('', 'UTF-8'))
    
    def serve_widget_support (self, path):
        module_name, script_name = path.split('/')
        module_name = 'wg' + module_name
        dummy, ext = os.path.splitext(script_name)
        filepath = os.path.join(
            au.get_modules_dir(),
            'webviewerwidgets',
            module_name,
            script_name)
        if os.path.exists(filepath):
            self.serve_view(filepath, None)
        elif ext == '.js':
            self.send_response(200)
            self.send_header('Content-type', 'application/javascript')
            self.end_headers()
            self.wfile.write(bytes('', 'UTF-8'))
        elif ext == '.yml':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(bytes('', 'UTF-8'))
        elif ext == '.css':
            self.send_response(200)
            self.send_header('Content-type', 'text/css')
            self.end_headers()
            self.wfile.write(bytes('', 'UTF-8'))
    
    def serve_widgetservice (self, path, query, post_data):
        path = 'wg' + path
        queries = urllib.parse.parse_qs(query)
        f, fn, d = imp.find_module(path, 
            [os.path.join(au.get_modules_dir(), 
                          'webviewerwidgets', path)])
        m = imp.load_module(path, f, fn, d)
        ret = m.get_data(queries)
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        content = json.dumps(ret)
        response = bytes(content, 'UTF-8')
        self.wfile.write(response)
    
    def get_sosamples (self, dbpath):
        ret = {}
        conn = sqlite3.connect(dbpath)
        cursor = conn.cursor()
        q = 'select distinct base__sample_id from variant'
        cursor.execute(q)
        samples = [v[0] for v in cursor.fetchall()]
        samples.sort()
        for sample in samples:
            ret[sample] = {}
            q = 'select base__so, count(*) from variant where ' +\
                'base__sample_id="' + sample + '" group by base__so ' +\
                'order by base__so'
            cursor.execute(q)
            for row in cursor.fetchall():
                (base_so, count) = row
                ret[sample][base_so] = str(count)
        return ret
    
    def get_topgenessamples (self):
        ret = []
        ret.append("PIWIL3:33")
        ret.append("MKL1:33")
        ret.append("MTMR3:33")
        ret.append("AAMP:33")
        return ret
    
    def get_go (self, dbpath, numcat):
        f, fn, d = imp.find_module('go', 
            [os.path.join(self.conf.get_system_conf()['home'], 
                          'viewers', 'webviewer', 'widgets', 'go')])
        m = imp.load_module('go', f, fn, d)
        ret = m.run(dbpath, numcat)
        return ret
    
    def get_sojob (self, dbpath):
        ret = {}
        conn = sqlite3.connect(dbpath)
        cursor = conn.cursor()
        query = 'select distinct base__so from variant'
        cursor.execute(query)
        sos = [v[0] for v in cursor.fetchall() if v[0] != '']
        for so in sos:
            query = 'select count(*) from variant where base__so="' + so + '"'
            cursor.execute(query)
            no = cursor.fetchone()[0]
            ret[so] = str(no)
        return ret
    
    def get_datamodel (self, data):
        ret = []
        for row in data:
            ret.append(list(row))
        return ret

    def get_colmodel (self, tab, colinfo):
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
    
    def get_summary_widget_names (self, queries):
        runid = queries['jobid'][0]
    
    def get_webviewerconf (self):
        conf_path = os.path.join(
                self.conf.get_system_conf()['home'], 
                'viewers',
                'webviewer',
                'webviewer.yml')
        with open(conf_path) as f:
            conf = yaml.load(f)
        return conf
    
    def get_colinfo (self, dbpath, confpath, filterstring):
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
    
    def serve_rest (self, path, query):
        queries = urllib.parse.parse_qs(query)
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        #print('queries=', queries)
        if path == 'variantcols':
            content = self.get_variant_cols(queries)
        if path == 'conf':
            content = self.get_webviewerconf()
        elif path == 'getsummarywidgetnames':
            content = self.get_summary_widget_names(queries)
        elif path == 'getresulttablelevels':
            content = self.get_result_levels(queries)
        elif path == 'result':
            content = self.get_result(queries)
        elif path == 'count':
            content = self.get_count(queries)
        elif path == 'widgetlist':
            content = self.get_widgetlist()
        elif path == 'status':
            content = self.get_status(queries)
        elif path == 'savefiltersetting':
            content = self.save_filter_setting(queries)
        elif path == 'savelayoutsetting':
            content = self.save_layout_setting(queries)
        elif path == 'loadfiltersetting':
            content = self.load_filtersetting(queries)
        elif path == 'loadlayoutsetting':
            content = self.load_layout_setting(queries)
        elif path == 'deletelayoutsetting':
            content = self.delete_layout_setting(queries)
        elif path == 'renamelayoutsetting':
            content = self.rename_layout_setting(queries)
        elif path == 'getlayoutsavenames':
            content = self.get_layoutsavenames(queries)
        elif path == 'getfiltersavenames':
            content = self.get_filter_save_names(queries)
        elif path == 'getnowgannotmodules':
            content = self.get_nowg_annot_modules(queries)
        response = bytes(json.dumps(content), 'UTF-8')
        self.wfile.write(response)
    
    def get_nowg_annot_modules (self, queries):
        dbpath = urllib.parse.unquote(queries['dbpath'][0])
        conn = sqlite3.connect(dbpath)
        cursor = conn.cursor()
        wgmodules = au.get_local_module_infos_of_type('webviewerwidget')
        nowg_annot_modules = []
        if self.table_exists(cursor, 'variant'):
            q = 'select name from variant_annotator'
            cursor.execute(q)
            for r in cursor.fetchall():
                module = r[0]
                if module not in wgmodules and module not in nowg_annot_modules:
                    nowg_annot_modules.append(module)
        print('@@@ nowg_annot_modules:', nowg_annot_modules)
        content = nowg_annot_modules
        return content
        
    def get_layoutsavenames (self, queries):
        dbpath = urllib.parse.unquote(queries['dbpath'][0])
        conn = sqlite3.connect(dbpath)
        cursor = conn.cursor()
        table = 'viewersetup'
        content = []
        if self.table_exists(cursor, table):
            q = 'select distinct name from ' + table + ' where datatype="layout"'
            cursor.execute(q)
            r = cursor.fetchall()
            content = [v[0] for v in r]
        cursor.close()
        conn.close()
        return content
    
    def load_filtersetting (self, queries):
        dbpath = urllib.parse.unquote(queries['dbpath'][0])
        name = urllib.parse.unquote(queries['name'][0])
        conn = sqlite3.connect(dbpath)
        cursor = conn.cursor()
        table = 'viewersetup'
        if self.table_exists(cursor, table) == False:
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
    
    def get_status (self, queries):
        dbpath = urllib.parse.unquote(queries['dbpath'][0])
        conn = sqlite3.connect(dbpath)
        cursor = conn.cursor()
        q = 'select * from info'
        cursor.execute(q)
        content = {}
        for row in cursor.fetchall():
            content[row[0]] = row[1]
        return content
    
    def get_widgetlist (self):
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
    
    def get_count (self, queries):
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
        
    def get_filter_save_names (self, queries):
        dbpath = urllib.parse.unquote(queries['dbpath'][0])
        conn = sqlite3.connect(dbpath)
        cursor = conn.cursor()
        table = 'viewersetup'
        if self.table_exists(cursor, table) == False:
            content = []
        else:
            q = 'select distinct name from ' + table + ' where datatype="filter"'
            cursor.execute(q)
            r = cursor.fetchall()
            content = str([v[0] for v in r])
        cursor.close()
        conn.close()
        return content
        
    def get_result (self, queries):
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
        content['columns'] = self.get_colmodel(tab, data['colinfo'])
        content["data"] = self.get_datamodel(data[tab])
        content["status"] = "normal"
        return content
            
    def get_variant_cols (self, queries):
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
        colinfo = self.get_colinfo(dbpath, confpath, filterstring)
        data['columns'] = {}
        if 'variant' in colinfo:
            data['columns']['variant'] = self.get_colmodel('variant', colinfo)
        if 'gene' in colinfo:
            data['columns']['gene'] = self.get_colmodel('gene', colinfo)
        content = data
        return content
        
    def get_result_levels (self, queries):
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
    
    def load_layout_setting (self, queries):
        dbpath = urllib.parse.unquote(queries['dbpath'][0])
        name = urllib.parse.unquote(queries['name'][0])
        conn = sqlite3.connect(dbpath)
        cursor = conn.cursor()
        table = 'viewersetup'
        if self.table_exists(cursor, table) == False:
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
    
    def delete_layout_setting (self, queries):
        dbpath = urllib.parse.unquote(queries['dbpath'][0])
        name = urllib.parse.unquote(queries['name'][0])
        conn = sqlite3.connect(dbpath)
        cursor = conn.cursor()
        table = 'viewersetup'
        if self.table_exists(cursor, table) == True:
            q = 'DELETE FROM ' + table + ' WHERE datatype="layout" and name="' + name + '"'
            cursor.execute(q)
        conn.commit()
        cursor.close()
        conn.close()
        content = {}
        return content
    
    def rename_layout_setting (self, queries):
        dbpath = urllib.parse.unquote(queries['dbpath'][0])
        name = urllib.parse.unquote(queries['name'][0])
        new_name = urllib.parse.unquote(queries['newname'][0])
        conn = sqlite3.connect(dbpath)
        cursor = conn.cursor()
        table = 'viewersetup'
        if self.table_exists(cursor, table) == True:
            q = 'update ' + table + ' set name="' + new_name + '" where datatype="layout" and name="' + name + '"'
            cursor.execute(q)
        conn.commit()
        cursor.close()
        conn.close()
        content = {}
        return content
    
    def save_filter_setting (self, queries):
        dbpath = urllib.parse.unquote(queries['dbpath'][0])
        name = urllib.parse.unquote(queries['name'][0])
        savedata = urllib.parse.unquote(queries['savedata'][0])
        conn = sqlite3.connect(dbpath)
        cursor = conn.cursor()
        table = 'viewersetup'
        if self.table_exists(cursor, table) == False:
            q = 'create table ' + table + ' (datatype text, name text, viewersetup text, unique (datatype, name))'
            cursor.execute(q)
        q = 'replace into ' + table + ' values ("filter", "' + name + '", \'' + savedata + '\')'
        cursor.execute(q)
        conn.commit()
        cursor.close()
        conn.close()
        content = 'saved'
        return content
    
    def save_layout_setting (self, queries):
        dbpath = urllib.parse.unquote(queries['dbpath'][0])
        name = urllib.parse.unquote(queries['name'][0])
        savedata = urllib.parse.unquote(queries['savedata'][0])
        conn = sqlite3.connect(dbpath)
        cursor = conn.cursor()
        table = 'viewersetup'
        if self.table_exists(cursor, table) == False:
            q = 'create table ' + table + ' (datatype text, name text, viewersetup text, unique (datatype, name))'
            cursor.execute(q)
        q = 'replace into ' + table + ' values ("layout", "' + name + '", \'' + savedata + '\')'
        cursor.execute(q)
        conn.commit()
        cursor.close()
        conn.close()
        content = 'saved'
        return content
    
    def table_exists (self, cursor, table):
        sql = 'select name from sqlite_master where type="table" and ' +\
            'name="' + table + '"'
        cursor.execute(sql)
        if cursor.fetchone() == None:
            return False
        else:
            return True
        
    def serve_view (self, filepath, params):
        self.send_response(200)
        if filepath[-4:] == '.css':
            self.send_header('Content-type', 'text/css')
        elif filepath[-3:] == '.js':
            self.send_header('Content-type', 'application/javascript')
        elif filepath[-4:] == '.png':
            self.send_header('Content-type', 'image/png')
        elif filepath[-4:] == '.jpg':
            self.send_header('Content-type', 'image/jpg')
        elif filepath[-4:] == '.gif':
            self.send_header('Content-type', 'image/gif')
        else:
            self.send_header('Content-type', 'text/html')
        self.end_headers()
        with open(filepath, 'rb') as f:
            response = f.read()
            self.wfile.write(response)
            
class Server(multiprocessing.Process):
    def run(self):
        print('HTTP server starting...')
        httpd = HTTPServer(('localhost', 8060), MyHandler)
        # SSL
        '''httpd = TCPServer(('localhost', 8443), handler)
        httpd.socket = ssl.wrap_socket(
            httpd.socket, 
            certfile='./newkey.pem',
            server_side=True
        )'''
        try:
            httpd.serve_forever()
            print('HTTP Server started.')
        except:
            print('Stopped')
            exit()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('dbpath',
                        help='path to a CRAVAT result SQLite file')
    parser.add_argument('-c',
                        dest='confpath',
                        default=None,
                        help='path to a CRAVAT configuration file')
    parsed_args = parser.parse_args(sys.argv[1:])
    dbpath = os.path.abspath(parsed_args.dbpath)
    if os.path.exists(dbpath) == False:
        sys.stderr.write(dbpath + ' does not exist.\n')
        exit(-1)
    confpath = parsed_args.confpath
    server = Server()
    server.start()
    
    runid = os.path.basename(dbpath).replace('.sqlite', '')
    webbrowser.open('http://localhost:8060/view.html?job_id=' + runid + '&dbpath=' + dbpath)

def test ():
    server = Server()
    server.start()
    parser = argparse.ArgumentParser()
    parser.add_argument('dbpath',
                        help='Path to a CRAVAT-result sqlite file')
    parsed_args = parser.parse_args([
        'd:\\git\\cravat-newarch\\tmp\\job\\in10.sqlite'])
    dbpath = os.path.abspath(parsed_args.dbpath)
    if os.path.exists(dbpath) == False:
        sys.stderr.write(dbpath + ' does not exist.\n')
        exit(-1)
    runid = os.path.basename(dbpath).replace('.sqlite', '')
    webbrowser.open('http://localhost:8060/view.html?job_id=' + runid + '&dbpath=' + dbpath)
    
if __name__ == '__main__':
    main()
    #test()