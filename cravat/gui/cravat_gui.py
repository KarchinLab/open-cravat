from http.server import HTTPServer, CGIHTTPRequestHandler
from socketserver import TCPServer
import os
import webbrowser
import multiprocessing
import sqlite3
import urllib.parse
import re
import json
import sys
import argparse
import imp
import yaml
import requests
from cravat import ConfigLoader
import cravat.admin_util as au

basedir = os.path.dirname(__file__)

class MyHandler (CGIHTTPRequestHandler):
    def do_POST (self):
        print('POST path=', self.path)
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        print(post_data)
        urltoks = urllib.parse.urlparse(self.path)
        path = urltoks.path
        params = urllib.parse.parse_qs(urltoks.query)
        self.send_response(200)
        self.send_header('Content-type','application/json')
        self.end_headers()
        if path.startswith('/rest/install'):
            d = json.loads(post_data)
            for module in d['modules']:
                module_name = module['name']
                version = module['version']
                print(module_name, version)
                au.install_module(module_name,version=version)
            r = {'success':d['modules'],
                 'failure':[]}
            rs = json.dumps(r)
            print(rs)
            self.wfile.write(bytes(rs,'utf-8'))
        elif path.startswith('/rest/remove'):
            d = json.loads(post_data)
            for module in d['modules']:
                print(module)
                module_name = module['name']
                au.remove_module(module_name)
            r = {'success':d['modules'],
                 'failure':[]}
            rs = json.dumps(r)
            print(rs)
            self.wfile.write(bytes(rs,'utf-8'))
            
    def do_GET(self):
        print('start do_GET')
        urltoks = urllib.parse.urlparse(self.path)
        request_path = urltoks.path
        request_query = urllib.parse.parse_qs(urltoks.query)
        if self.path.startswith('/rest/'):
            trimmed_path = re.sub('^/rest/','', request_path)
            self.serve_rest(trimmed_path, request_query)
        elif self.path.startswith('/modules/'):
            trimmed_path = re.sub('^/modules/','', request_path)
            self.serve_module(trimmed_path, request_query)
        elif self.path.startswith('/'):
            if self.path == '/':
                filepath = self.get_filepath('index.html')
            else:
                filepath = self.get_filepath(request_path)
            self.serve_view(filepath, request_query)
        print('return from do_GET')
        return

    def serve_module(self,path,query):
        path_toks = path.split('/')
        try:
            module_name = path_toks[0]
        except IndexError:
            self.send_response(404)
            return
        try:
            local_info = au.get_local_module_info(module_name)
            local_yml = yaml.dump(local_info, default_flow_style=False)
            local_html = local_yml.replace('\n','<br>')
        except KeyError:
            local_html = 'NOT INSTALLED'
        try:
            remote_info = au.get_remote_module_info(module_name)
        except KeyError:
            self.send_response(404)
            return
        remote_yml = yaml.dump(remote_info, default_flow_style=False)
        remote_html = remote_yml.replace('\n','<br>')
        all_html = local_html + '<hr>' + remote_html
        response = bytes(all_html,'utf-8')
        print(response)
        self.send_header('Content-type','text/html')
        self.end_headers
        print(self.headers)
        response = bytes('<h4>Kyle Moad</h4>','utf-8')
        self.wfile.write(response)
        self.send_response(200)
    
    def serve_rest (self, path, params):
        path_toks = path.split('/')
        content = None
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        if path_toks[0] == 'local':
            if len(path_toks) > 1:
                module_name = path_toks[1]
                local = self.get_local_detailed(module_name)
                content = json.dumps(local)
            else:
                local = self.get_local()
                if local is None:
                    self.send_response(400)
                else:
                    content = json.dumps(local)
        elif path_toks[0] == 'remote':
            if len(path_toks) > 1:
                module_name = path_toks[1]
                version = path_toks[2] if len(path_toks) > 2 else None
                remote = self.get_remote_detailed(module_name,version=version)
                if remote is None:
                    self.send_response(400)
                else:
                    content = json.dumps(remote)
            else:
                remote = self.get_remote()
                content = json.dumps(remote)
        else:
            self.send_response(404)
        if content is not None:
            response = bytes(content, 'UTF-8')
            self.wfile.write(response)
        return
    
    def do_install_module (self, path, params):
        pass
    
    def do_remove_module (self, path, params):
        pass
    
    def get_local(self):
        local = au.list_local()
        out = {}
        for module_name in local:
            local_info = au.get_local_module_info(module_name)
            out[module_name] = {'version':local_info.conf['version']}
        return out
    
    def get_remote(self):
        remote = au.list_remote()
        out = {}
        for module_name in remote:
            remote_info = au.get_remote_module_info(module_name)
            out[remote_info.name] = {
                                     'versions':remote_info.versions,
                                     'latestVersion':remote_info.latest_version,
                                     'type':remote_info.type,
                                     'title':remote_info.title
                                     }
        return out
    
    def get_remote_detailed(self, module_name, version=None):
        remote_info = au.get_remote_module_info(module_name)
        if remote_info is None:
            return
        out = {
               'versions':remote_info.versions,
               'latestVersion':remote_info.latest_version,
               'type':remote_info.type,
               'title':remote_info.title,
               'description':remote_info.description,
               'developer':remote_info.developer
              }
        return out
    
    def get_local_detailed(self, module_name):
        local_info = au.get_local_module_info(module_name)
        if local_info is None:
            return
        else:
            out = {
                   'version':local_info.version,
                   'type':local_info.type,
                   'title':local_info.title,
                   'description':local_info.description,
                   'readme':local_info.readme,
                   'developer':local_info.developer
                  }
            return out
        
    def get_filepath (self, path):
        filepath = os.sep.join(re.sub('^/', '', path).split('/'))
        filepath = os.path.join(basedir, filepath)
        return filepath
                
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
    def __init__(self, port):
        super().__init__()
        self.port = port
        
    def run(self):
        print('HTTP server starting...')
        httpd = HTTPServer(('localhost', self.port), MyHandler)
        # SSL
        '''httpd = TCPServer(('localhost', 8443), handler)
        httpd.socket = ssl.wrap_socket(
            httpd.socket, 
            certfile='./newkey.pem',
            server_side=True
        )'''
        try:
            httpd.serve_forever()
        except:
            print('Stopped')
            exit()

def main():
    conf_loader = ConfigLoader()
    conf = conf_loader.get_cravat_conf()
    port = conf['gui_port']
    server = Server(port)
    server.start()
#     url = 'http://localhost:%d/' %port
#     webbrowser.open(url)

if __name__ == '__main__':
    main()