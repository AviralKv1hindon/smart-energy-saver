/*
  Smart Energy Saver — ESP32 Serial Relay Receiver
  ─────────────────────────────────────────────────
  NCSC Project · Theme E4 · Phase 1

  Wiring:
    Relay IN  → GPIO 26
    Relay VCC → 5V (or 3.3V depending on relay module)
    Relay GND → GND

  Commands received over Serial (USB from laptop):
    RELAY_ON\n   → turns relay ON  (power to devices)
    RELAY_OFF\n  → turns relay OFF (cut power)
    STATUS\n     → replies with current state

  Baud rate: 9600
*/

#define RELAY_PIN     26
#define LED_PIN        2     // onboard LED mirrors relay state
#define RELAY_ACTIVE  LOW    // LOW = active LOW relay (most common modules)
                             // change to HIGH if your relay is active HIGH

bool relayState = false;
String inputBuffer = "";

void setup() {
  Serial.begin(9600);
  while (!Serial) {}          // wait for serial port

  pinMode(RELAY_PIN, OUTPUT);
  pinMode(LED_PIN,   OUTPUT);

  setRelay(false);             // start with relay OFF

  Serial.println("ESP32 Relay Receiver ready");
  Serial.println("Commands: RELAY_ON | RELAY_OFF | STATUS");
}

void loop() {
  // Read serial command
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      inputBuffer.trim();
      if (inputBuffer.length() > 0) {
        handleCommand(inputBuffer);
        inputBuffer = "";
      }
    } else {
      inputBuffer += c;
    }
  }
}

void handleCommand(String cmd) {
  cmd.toUpperCase();

  if (cmd == "RELAY_ON") {
    setRelay(true);
    Serial.println("ACK:RELAY_ON");

  } else if (cmd == "RELAY_OFF") {
    setRelay(false);
    Serial.println("ACK:RELAY_OFF");

  } else if (cmd == "STATUS") {
    Serial.print("STATUS:");
    Serial.println(relayState ? "ON" : "OFF");

  } else {
    Serial.print("UNKNOWN_CMD:");
    Serial.println(cmd);
  }
}

void setRelay(bool on) {
  relayState = on;
  digitalWrite(RELAY_PIN, on ? RELAY_ACTIVE : !RELAY_ACTIVE);
  digitalWrite(LED_PIN,   on ? HIGH : LOW);
}
