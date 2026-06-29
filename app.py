"""
Smart Energy Saver — Phase 1 (Laptop + YOLOv8 + Serial Relay)
NCSC Project · Theme E4 · Energy sub-theme
"""

import cv2
import time
import threading
import serial
import serial.tools.list_ports
from flask import Flask, Response, jsonify, request, render_template
from ultralytics import YOLO
from collections import deque
import numpy as np

# ── App & model ───────────────────────────────────────────────────────────────
app = Flask(__name__)
model = YOLO("yolov8n.pt")           # auto-downloads on first run

# ── Config (edit these) ───────────────────────────────────────────────────────
CAMERA_INDEX      = 0               # 0 = default webcam
CONFIDENCE        = 0.45            # YOLOv8 detection threshold
TIMEOUT_SECONDS   = 300             # 5 min no-person → relay OFF
SERIAL_BAUD       = 9600
SERIAL_PORT       = None            # None = auto-detect ESP32

# ── Shared state ──────────────────────────────────────────────────────────────
state = {
    "person_count":    0,
    "relay_on":        False,
    "last_seen":       None,
    "serial_connected":False,
    "serial_port":     "—",
    "fps":             0.0,
    "total_detections":0,
    "relay_on_time":   0.0,          # seconds relay has been ON
    "session_start":   time.time(),
    "history":         deque(maxlen=60),  # last 60 s person counts
    "alert":           "",
}
state_lock = threading.Lock()
frame_lock  = threading.Lock()
latest_frame = None

# ── Serial / ESP32 ────────────────────────────────────────────────────────────
ser = None

def find_esp32_port():
    """Auto-detect the first USB-serial device (CP210x, CH340, FTDI)."""
    keywords = ["CP210", "CH340", "FTDI", "USB Serial", "USB-SERIAL", "ttyUSB", "ttyACM", "COM"]
    for p in serial.tools.list_ports.comports():
        desc = (p.description or "") + (p.manufacturer or "")
        if any(k.lower() in desc.lower() for k in keywords):
            return p.device
    return None

def connect_serial():
    global ser
    port = SERIAL_PORT or find_esp32_port()
    if not port:
        with state_lock:
            state["serial_connected"] = False
            state["serial_port"] = "Not found"
            state["alert"] = "ESP32 not detected — relay commands disabled"
        return
    try:
        ser = serial.Serial(port, SERIAL_BAUD, timeout=1)
        time.sleep(2)   # wait for ESP32 reset
        with state_lock:
            state["serial_connected"] = True
            state["serial_port"] = port
            state["alert"] = ""
        print(f"[Serial] Connected: {port}")
    except Exception as e:
        with state_lock:
            state["serial_connected"] = False
            state["serial_port"] = f"Error: {e}"
            state["alert"] = f"Serial error: {e}"

def send_relay(on: bool):
    """Send RELAY_ON or RELAY_OFF over serial."""
    global ser
    if ser and ser.is_open:
        cmd = b"RELAY_ON\n" if on else b"RELAY_OFF\n"
        try:
            ser.write(cmd)
        except Exception as e:
            print(f"[Serial] Write error: {e}")

# ── Relay logic ───────────────────────────────────────────────────────────────
relay_on_since = None

def set_relay(on: bool):
    global relay_on_since
    with state_lock:
        if on == state["relay_on"]:
            return
        state["relay_on"] = on
    send_relay(on)
    if on:
        relay_on_since = time.time()
        print("[Relay] ON")
    else:
        if relay_on_since:
            with state_lock:
                state["relay_on_time"] += time.time() - relay_on_since
        relay_on_since = None
        print("[Relay] OFF")

# ── Detection thread ──────────────────────────────────────────────────────────
def detection_loop():
    global latest_frame
    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    prev_time = time.time()
    tick = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.05)
            continue

        # YOLOv8 inference (only class 0 = person)
        results = model(frame, classes=[0], conf=CONFIDENCE, verbose=False)[0]
        boxes   = results.boxes

        person_count = len(boxes)
        now = time.time()

        # FPS
        fps = 1.0 / max(now - prev_time, 1e-6)
        prev_time = now
        tick += 1

        # Draw bounding boxes
        annotated = frame.copy()
        for i, box in enumerate(boxes):
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = float(box.conf[0])
            # Gradient-ish colour by index
            colour = [(0,230,118),(0,188,212),(156,39,176),(255,152,0)][i % 4]
            cv2.rectangle(annotated, (x1, y1), (x2, y2), colour, 2)
            label = f"Person {i+1}  {conf:.0%}"
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
            cv2.rectangle(annotated, (x1, y1 - lh - 8), (x1 + lw + 6, y1), colour, -1)
            cv2.putText(annotated, label, (x1 + 3, y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (10,10,10), 1, cv2.LINE_AA)

        # Overlay HUD
        _draw_hud(annotated, person_count, fps)

        # Update state
        with state_lock:
            state["person_count"]     = person_count
            state["fps"]              = round(fps, 1)
            if tick % 60 == 0:
                state["history"].append(person_count)
            if person_count > 0:
                state["last_seen"]        = now
                state["total_detections"] += person_count

        # Relay logic
        if person_count > 0:
            set_relay(True)
            with state_lock:
                state["last_seen"] = now
        else:
            with state_lock:
                last = state["last_seen"]
            if last and (now - last > TIMEOUT_SECONDS):
                set_relay(False)

        # Encode frame
        _, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
        with frame_lock:
            latest_frame = buf.tobytes()

def _draw_hud(frame, count, fps):
    h, w = frame.shape[:2]
    # semi-transparent top bar
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 52), (15, 15, 20), -1)
    cv2.addWeighted(overlay, 0.72, frame, 0.28, 0, frame)
    cv2.putText(frame, f"Persons: {count}", (12, 34),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,230,118), 2, cv2.LINE_AA)
    cv2.putText(frame, f"FPS {fps:.1f}", (w - 120, 34),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (180,180,180), 1, cv2.LINE_AA)
    # bottom tag
    cv2.putText(frame, "NCSC Smart Energy Saver  |  YOLOv8n", (10, h - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100,100,100), 1, cv2.LINE_AA)

# ── Flask routes ──────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/video_feed")
def video_feed():
    def gen():
        while True:
            with frame_lock:
                f = latest_frame
            if f:
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + f + b"\r\n")
            time.sleep(0.03)
    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/api/status")
def api_status():
    with state_lock:
        s = dict(state)
        s["history"] = list(s["history"])
        last = s.get("last_seen")
        s["seconds_since_seen"] = round(time.time() - last) if last else None
        s["uptime"] = round(time.time() - s["session_start"])
        s["relay_on_pct"] = round(
            (s["relay_on_time"] + (time.time()-relay_on_since if relay_on_since else 0))
            / max(s["uptime"], 1) * 100, 1)
    return jsonify(s)

@app.route("/api/relay", methods=["POST"])
def api_relay():
    """Manual override from GUI."""
    data = request.get_json()
    set_relay(bool(data.get("on", False)))
    return jsonify({"ok": True})

@app.route("/api/config", methods=["POST"])
def api_config():
    global CONFIDENCE, TIMEOUT_SECONDS
    data = request.get_json()
    if "confidence" in data:
        CONFIDENCE = float(data["confidence"])
    if "timeout" in data:
        TIMEOUT_SECONDS = int(data["timeout"])
    return jsonify({"confidence": CONFIDENCE, "timeout": TIMEOUT_SECONDS})

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    connect_serial()
    t = threading.Thread(target=detection_loop, daemon=True)
    t.start()
    print("\n  Open → http://localhost:5000\n")
    app.run(host="0.0.0.0", port=5000, threaded=True)
