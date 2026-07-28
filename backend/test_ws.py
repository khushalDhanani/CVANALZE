import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8000/api/batch/ws/progress"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected! Waiting for CV processing events...")
            while True:
                message = await websocket.recv()
                data = json.loads(message)
                print(f"--> Received Event: {data['filename']} - {data['status']}")
    except websockets.exceptions.ConnectionClosed:
        print("Connection closed.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())
