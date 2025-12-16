import socketio
import time

sio = socketio.Client()

@sio.event
def connect():
    print("Connected!")
    sio.emit('request_history')

@sio.event
def chart_history_response(data):
    print(f"Received Chart History: {len(data)} points")
    if len(data) > 0:
        print("Sample Point:", data[-1])
    else:
        print("Chart History is EMPTY.")
    sio.disconnect()

@sio.event
def tick_bundle(data):
    # print("Tick received")
    pass

sio.connect('http://localhost:5000')
sio.wait()
