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
from cravat.webresult import webresult as wr
from cravat.webstore import webstore as ws
import websockets

class CravatWebHandler (CGIHTTPRequestHandler):
    def do_POST (self):
        pass

    def do_GET (self):
        urltoks = urllib.parse.urlparse(self.path)
        self.request_path = urltoks.path
        self.request_queries = urllib.parse.parse_qs(urltoks.query)
        print('doget path=', self.request_path)
        head = self.trim_path_head()
        if head == 'result':
            wr.get(self)
        elif head == 'store':
            ws.get(self)

    def trim_path_head (self):
        if self.request_path[0] == '/':
            self.request_path = self.request_path[1:]
        toks = self.request_path.split('/')
        head = toks[0]
        if len(toks) == 1:
            path = ''
        else:
            path = '/'.join(toks[1:])
        self.request_path = path
        return head

    def serve_view (self, filepath):
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
        httpd = HTTPServer(('localhost', 8060), CravatWebHandler)
        try:
            httpd.serve_forever()
            print('HTTP Server started.')
        except:
            print('Stopped')
            exit()


def result ():
    server = Server()
    server.start()
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
    runid = os.path.basename(dbpath).replace('.sqlite', '')
    webbrowser.open('http://localhost:8060/result/index.html?job_id=' + runid + '&dbpath=' + dbpath)

def store ():
    server = Server()
    server.start()
    '''
    manager = Manager()
    install_state = manager.dict()
    sse_update_condition = manager.Condition()
    sse_update_event = manager.Event()
    install_state['stage'] = ''
    install_state['message'] = ''
    install_state['module_name'] = ''
    install_state['module_version'] = ''
    install_state['cur_chunk'] = 0
    install_state['total_chunks'] = 0
    install_state['cur_size'] = 0
    install_state['total_size'] = 0
    install_state['update_time'] = time.time()
    install_worker = Process(target=install_from_queue, args=(install_queue, install_state, sse_update_event))
    install_worker.start()
    app = web.Application()
    add_routes(app)
    conf_loader = ConfigLoader()
    conf = conf_loader.get_cravat_conf()
    port = conf['gui_port']
    web.run_app(app, host='localhost', port=port)
    '''
    webbrowser.open('http://localhost:8060/store/index.html')

if __name__ == '__main__':
    main()
