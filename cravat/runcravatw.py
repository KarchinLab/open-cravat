from aiohttp import web
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

async def index (request):
    name = request.match_info.get('name', "Anonymous")
    text = "Hello, " + name
    return web.Response(text=text)

def setup_routes(app):
    app.router.add_get('/index.html', index)
    app.router.add_get('/', index)

def setup_static_routes(app):
    app.router.add_static('/static/',
                          path=os.path.join(PROJECT_ROOT, 
                                            'runcravatw', 
                                            'static'),
                          name='static')
    
def main ():
    app = web.Application()
    setup_routes(app)
    setup_static_routes(app)
    web.run_app(app, host='127.0.0.1', port=8080)
    
if __name__ ==  '__main__':
    main()