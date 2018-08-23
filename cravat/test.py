import asyncio
import websockets
import time

async def gettime (websocket, path):
    while True:
        now = time.time()
        await websocket.send(str(now))
        await asyncio.sleep(1)

server = websockets.serve(gettime, 'localhost', 8500)
asyncio.get_event_loop().run_until_complete(server)
asyncio.get_event_loop().run_forever()
