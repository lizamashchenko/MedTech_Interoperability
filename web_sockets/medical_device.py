import tkinter as tk
import asyncio
import threading
import json
import random
import websockets

SERVER_WS_URL = "ws://127.0.0.1:6789"
DEVICE_ID = "neg-pressure-device-2"
PATIENT_ID = "patient-2"

OPERATION_MODES = {
    "continuous": "continuous",
     "intermittent": "intermittent",
}
OPERATION_STATUS = {
    "running": "running",
    "paused": "paused",
    "ended": "ended"
}

CRITICAL_ERRORS = {'System is open', 'System is not tight', 'System is blocked', 'Pouch is full'}
NON_CRITICAL_ERRORS = {'Battery low', 'Battery empty', 'No therapy', 'Internal error'}
ALL_ERRORS = list(CRITICAL_ERRORS | NON_CRITICAL_ERRORS)

current_mode = OPERATION_MODES['continuous']
current_status = OPERATION_STATUS['running']

is_running = False
last_value = -80

async def send_data():
    async with websockets.connect(SERVER_WS_URL) as ws:
        while True:
            if is_running:
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
                    global last_value
                    last_value = val
                    payload = {
                        "device_id": DEVICE_ID,
                        "value": val,
                        "mode": current_mode,
                        "status": current_status,
                        "error": False,
                        "message": "",
                    }
                await ws.send(json.dumps(payload))
            await asyncio.sleep(5)

def end_therapy():
    global is_running, current_status
    is_running = False
    current_status = OPERATION_STATUS["ended"]

    async def send_end():
        try:
            async with websockets.connect(SERVER_WS_URL) as ws:
                payload = {
                    "device_id": DEVICE_ID,
                    "value": 0,
                    "mode": current_mode,
                    "status": current_status,
                    "error": False,
                    "message": "Therapy ended by user"
                }
                await ws.send(json.dumps(payload))
                print("Sent: Therapy ended")
        except Exception as e:
            print(f"Failed to send end payload: {e}")

    threading.Thread(target=lambda: asyncio.run(send_end()), daemon=True).start()

    # GUI update
    for w in [main_frame, header_label, mode_label, pressure_frame, pressure_value, pressure_unit,
              intensity_label, button_frame, footer_frame]:
        w.config(bg="#888888")
    header_label.config(text="Therapy ended")
    start_pause_button.config(state="disabled")
    end_button.config(state="disabled")

def send_manual_error(message):
    async def send_error():
        try:
            async with websockets.connect(SERVER_WS_URL) as ws:
                payload = {
                    "device_id": DEVICE_ID,
                    "value": 0,
                    "mode": current_mode,
                    "status": current_status,
                    "error": True,
                    "message": message
                }
                await ws.send(json.dumps(payload))
                print(f"Sent manual error: {message}")
        except Exception as e:
            print(f"Failed to send manual error: {e}")

    threading.Thread(target=lambda: asyncio.run(send_error()), daemon=True).start()

def trigger_critical_error():
    global is_running, current_status

    message = random.choice(list(CRITICAL_ERRORS))
    is_running = False
    current_status = OPERATION_STATUS["paused"]
    send_manual_error(f"CRITICAL: {message}")

    bg = "#f4931b"
    btn = "#8fda9c"
    header_label.config(text="Therapy paused due to critical error")
    start_pause_button.config(text="▶", bg=btn)

    for w in [main_frame, header_label, mode_label, pressure_frame, pressure_value, pressure_unit,
              intensity_label, button_frame, footer_frame]:
        w.config(bg=bg)

    pressure_value.config(text=str(int(last_value)))

def trigger_non_critical_error():
    message = random.choice(list(NON_CRITICAL_ERRORS))
    send_manual_error(f"NON-CRITICAL: {message}")


def start_loop():
    asyncio.run(send_data())

def toggle_state():
    global is_running, current_status 

    is_running = not is_running

    if is_running:
        bg = "#1b8d33"
        btn = "#f4a83d"
        header_label.config(text="Therapy in progress")
        start_pause_button.config(text="⏸", bg=btn)
        current_status = OPERATION_STATUS['running']
    else:
        bg = "#f4931b"
        btn = "#8fda9c"
        header_label.config(text="Therapy paused")
        start_pause_button.config(text="▶", bg=btn)
        current_status = OPERATION_STATUS['paused']

    for w in [main_frame, header_label, mode_label, pressure_frame, pressure_value, pressure_unit,
              intensity_label, button_frame, footer_frame]:
        w.config(bg=bg)

    pressure_value.config(text=str(int(last_value)))

root = tk.Tk()
root.title("Therapy Control")
root.geometry("300x500")
root.resizable(False, False)

main_frame = tk.Frame(root, bg="#f4931b")
main_frame.pack(fill="both", expand=True)

header_label = tk.Label(main_frame, text="Therapy paused", bg="#f4931b", fg="white", font=("Helvetica", 14, "bold"))
header_label.pack(pady=10)

mode_label = tk.Label(main_frame, text="⎍ Continuous", bg="#f4931b", fg="white", font=("Helvetica", 11))
mode_label.pack(pady=2)

tk.Frame(main_frame, height=1, bg="white").pack(fill="x", padx=30, pady=5)

pressure_frame = tk.Frame(main_frame, bg="#f4931b")
pressure_frame.pack()

pressure_value = tk.Label(pressure_frame, text="-80", bg="#f4931b", fg="white", font=("Helvetica", 36, "bold"))
pressure_value.pack(side="left")

pressure_unit = tk.Label(pressure_frame, text="mmHg", bg="#f4931b", fg="white", font=("Helvetica", 14))
pressure_unit.pack(side="left", anchor="s", padx=(5, 0))

tk.Frame(main_frame, height=1, bg="white").pack(fill="x", padx=30, pady=5)

intensity_label = tk.Label(main_frame, text="📊 Medium", bg="#f4931b", fg="white", font=("Helvetica", 11))
intensity_label.pack(pady=5)

button_frame = tk.Frame(main_frame, bg="#f4931b")
button_frame.pack(pady=15)

start_pause_button = tk.Button(button_frame, text="▶", font=("Helvetica", 20), width=4, height=2,
                               bg="#8fda9c", relief="flat", command=toggle_state)
start_pause_button.grid(row=0, column=0, padx=10)

end_button = tk.Button(button_frame, text="■", font=("Helvetica", 20), width=4, height=2,
                       bg="#ff4d4d", relief="flat", command=end_therapy)
end_button.grid(row=0, column=2, padx=10)

settings_button = tk.Button(button_frame, text="⚙️", font=("Helvetica", 20), width=4, height=2,
                            bg="lightgray", relief="flat")
settings_button.grid(row=0, column=1, padx=10)

error_frame = tk.Frame(main_frame, bg="#f4931b")
error_frame.pack(pady=5)

critical_button = tk.Button(error_frame, text="❗ Critical", font=("Helvetica", 10),
                            bg="#ff5e57", fg="white", relief="flat",
                            command=trigger_critical_error)
critical_button.pack(side="left", padx=10)

non_critical_button = tk.Button(error_frame, text="⚠️ Non-Critical", font=("Helvetica", 10),
                                bg="#ffc048", fg="black", relief="flat",
                                command=trigger_non_critical_error)

non_critical_button.pack(side="left", padx=10)


footer_frame = tk.Frame(main_frame, bg="#dcdcdc")
footer_frame.pack(side="bottom", fill="x", pady=10)

tk.Button(footer_frame, text="🔒", font=("Helvetica", 12), bg="#dcdcdc", relief="flat").pack(side="left", padx=30)
tk.Button(footer_frame, text="🛠", font=("Helvetica", 12), bg="#dcdcdc", relief="flat").pack(side="right", padx=30)

threading.Thread(target=start_loop, daemon=True).start()
root.mainloop()
