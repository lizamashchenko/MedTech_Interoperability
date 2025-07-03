import asyncio
import websockets
import json
import random

SERVER_WS_URL = "ws://127.0.0.1:6789"
DEVICE_ID = "neg-pressure-device-1"
PATIENT_ID = "patient-1"

OPERATION_MODES = ["continuous", "intermittent"]
OPERATION_STATUS = ["running", "paused"]

current_mode = OPERATION_MODES[0]
current_status = OPERATION_STATUS[0]

async def send_data():
    async with websockets.connect(SERVER_WS_URL) as ws:
        while True:
            if random.random() < 0.1:
                payload = {
                    "device_id": DEVICE_ID,
                    "value": 0,
                    "mode": current_mode,
                    "status": current_status,
                    "error": True,
                    "message": "ERROR",
                }

            else:
                val = -random.uniform(50, 100)
                payload = {
                    "device_id": DEVICE_ID,
                    "value": val,
                    "error": False,
                    "message": "",
                    "mode": current_mode,
                    "status": current_status,
                }

            await ws.send(json.dumps(payload))
            print(f"Sent: {payload}")
            await asyncio.sleep(5)

if __name__ == '__main__':
    asyncio.run(send_data())
