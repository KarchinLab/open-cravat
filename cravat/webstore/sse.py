import asyncio
from aiohttp import web
from aiohttp.web import Application, Response
from aiohttp_sse import sse_response
from multiprocessing import Process, Pipe, Value, Manager
import time

listner_conn, ticker_conn = Pipe(False)
cur_tick = Value('i',0)


# async def hello(request):
#     loop = request.app.loop
#     async with sse_response(request) as resp:
#         for i in range(0, 100):
#             await asyncio.sleep(1, loop=loop)
#             await resp.send('foo {}'.format(i))
#     return resp

async def update_sse_with_tick(sse, value):
    await sse.send(str(value.value))

async def hello(request):
    async with sse_response(request) as resp:
        await update_sse_with_tick(resp, managed_tick_value)
        last_value = managed_tick_value.value
        while True:
            await asyncio.sleep(1)
            if managed_tick_value.value != last_value:
                await update_sse_with_tick(resp, managed_tick_value)
                last_value = managed_tick_value.value
            
        managed_sse_list.append(resp)
#     return resp

def tick(value, sse_list):
    while True:
        value.value += 5
        for sse in sse_list:
            update_sse_with_tick(sse, value)
        time.sleep(5)

async def index(request):
    d = """
        <html>
        <head>
            <script type="text/javascript"
                src="http://code.jquery.com/jquery.min.js"></script>
            <script type="text/javascript">
            var evtSource = new EventSource("/hello");
            evtSource.onmessage = function(e) {
             $('#response').html(e.data);
            }

            </script>
        </head>
        <body>
            <h1>Response from server:</h1>
            <div id="response"></div>
        </body>
    </html>
    """
    return Response(text=d, content_type='text/html')



if __name__ == '__main__':
    manager = Manager()
    managed_tick_value = manager.Value('i',0)
    managed_sse_list = manager.list()
    p = Process(target=tick, args=(managed_tick_value,managed_sse_list))
    p.start()
    
    app = web.Application()
    app.router.add_route('GET', '/hello', hello)
    app.router.add_route('GET', '/index', index)
    
    web.run_app(app, host='localhost', port=8080)
