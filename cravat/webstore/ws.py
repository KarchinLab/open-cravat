from aiohttp import web, WSMsgType
import os
import asyncio
import time
from multiprocessing import Process, Pipe, Value
listener_conn, ticker_conn = Pipe(False)

v = Value('i',0)

async def websocket_handler(request):
    print('Get WebSocket Connection')
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    print('Prepared')
    await ws.send_str('Hello from the server!')
    task = request.app.loop.create_task(send_ticks(ws))
    try:
        async for msg in ws:
            print(msg.data)
    finally:
        task.cancel()
    print('websocket connection closed')

    return ws

async def send_ticks(ws):
    while True:
        await ws.send_str(str(v.value))
        await asyncio.sleep(1)
        
def tick(v):
    for i in range(100):
        v.value = i
        time.sleep(2)
    
if __name__ == '__main__':
    p = Process(target=tick, args=(v,))
    p.start()
    
    app = web.Application()
    app.router.add_routes([web.static('/static',os.getcwd())])
    app.router.add_get('/ws', websocket_handler)
    web.run_app(app, host='localhost', port=8080)