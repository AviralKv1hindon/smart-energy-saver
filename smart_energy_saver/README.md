# Smart Energy Saver — Phase 1 (Laptop)
### NCSC Project · Theme E4 · YOLOv8 + ESP32 Serial Relay

---

## Quick Start

### 1. Flash the ESP32
- Open `esp32_relay_serial/esp32_relay_serial.ino` in Arduino IDE 2.x
- Board: **ESP32 Dev Module**
- Upload → keep USB cable connected (this is the serial link)

### 2. Install Python dependencies
```bash
pip install -r requirements.txt
```
YOLOv8 will auto-download `yolov8n.pt` (~6 MB) on first run.

### 3. Run
```bash
python app.py
```
Open **http://localhost:5000** in your browser.

---

## Wiring

| Relay pin | ESP32 pin |
|-----------|-----------|
| IN        | GPIO 26   |
| VCC       | 5V        |
| GND       | GND       |

Connect your classroom devices (fan, projector, lights) to the relay's COM/NO terminals.

---

## Config (top of app.py)

| Variable         | Default | Description                        |
|------------------|---------|------------------------------------|
| CAMERA_INDEX     | 0       | Webcam index (0 = default)         |
| CONFIDENCE       | 0.45    | YOLOv8 detection threshold         |
| TIMEOUT_SECONDS  | 300     | Seconds before relay cuts power    |
| SERIAL_PORT      | None    | None = auto-detect ESP32           |

All config can also be changed **live** from the GUI sliders.

---

## Project phases

| Phase | Hardware         | Detection        | Status |
|-------|------------------|------------------|--------|
| 1     | Laptop + ESP32   | YOLOv8 (webcam)  | ← You are here |
| 2     | ESP32 standalone | PIR / Ultrasonic | Next step |

---

## Folder structure
```
smart_energy_saver/
├── app.py                        # Flask backend + YOLOv8 + Serial
├── requirements.txt
├── templates/
│   └── index.html                # Advanced GUI dashboard
└── esp32_relay_serial/
    └── esp32_relay_serial.ino    # ESP32 sketch (Serial relay receiver)
```
