# PN532 NFC Reader — Home Assistant Integration

A Python service that reads NFC cards via a USB-connected PN532 module and delivers `tag_scanned` events to Home Assistant. Runs as a Docker container or native systemd service on Raspberry Pi / Linux.

## What's new in v3.0.0

Version 3 replaces the legacy REST event API with the same WebSocket + mobile_app webhook path used by the official iOS and Android companion apps. This means:

- Tags scanned by this reader now appear in **Settings → Tags** with a last-scanned timestamp
- The reader shows up as a device in **Settings → Devices & Services**
- `tag.<id>` entities are created and updated automatically
- Automations triggered by **Tag** work out of the box — no additional HA configuration needed

The legacy REST path (`POST /api/events/tag_scanned`) is still available via `HA_WS_ENABLED=false` for backward compatibility.

---

## Quick Start — Docker (Recommended)

No local build required. The image is published automatically to GHCR on every push to `main`.

### Prerequisites

- Docker + Docker Compose installed (**rootful/system Docker required** — see note below)
- PN532 NFC module connected via USB
- Home Assistant 2023.4 or later

> **Rootful Docker required for device access**
>
> The container needs direct access to the USB serial device (`/dev/ttyUSB0`). This only works when Docker runs as root (the default on most Linux server installs). Rootless Docker installations cannot pass USB devices through to containers.
>
> Check which mode you have:
> ```bash
> docker info | grep rootless
> ```
> If that returns `rootless`, either run all Docker commands with `sudo`, or switch to system Docker:
> ```bash
> sudo systemctl enable --now docker
> sudo usermod -aG docker $USER   # log out and back in after this
> ```

### Steps

1. **Download the two required files** from the releases page:
   - `docker-compose.yml`
   - `.env.template`

2. **Configure:**
   ```bash
   cp .env.template .env
   nano .env
   ```
   Required settings in `.env`:
   ```bash
   HA_HOST=192.168.1.100           # Your Home Assistant IP
   HA_TOKEN=<long-lived-token>     # See: Getting a Long-Lived Token below
   ```

3. **Find your NFC device path:**
   ```bash
   ls /dev/ttyUSB*    # most common (CH340 adapter)
   ls /dev/ttyACM*    # alternative
   ```
   If your device is not `/dev/ttyUSB0`, update the `devices:` section in `docker-compose.yml`.

4. **Start:**
   ```bash
   docker compose up -d
   docker compose logs -f nfc-reader
   ```

   On first run you will see:
   ```
   ✅ PN532 found on /dev/ttyUSB0
   ✅ Device registered with Home Assistant
   ✅ WebSocket connected
   📡 Monitoring for NFC cards...
   ```

### Docker Commands

```bash
docker compose logs -f nfc-reader     # Live logs
docker compose down                   # Stop
docker compose pull && docker compose up -d   # Update to latest
docker compose restart nfc-reader    # Restart
```

---

## Standalone Installation — Native Python + systemd

For running directly on a Raspberry Pi or Linux machine without Docker.

### Prerequisites

- Python **3.10** or later
- PN532 NFC module connected via USB
- Home Assistant 2023.4 or later with a Long-Lived Access Token

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/l0cut15/pn532-nfc-reader-public
   cd pn532-nfc-reader-public
   ```

2. **Add your user to the `dialout` group** (required for serial port access):
   ```bash
   sudo usermod -a -G dialout $USER
   ```
   Log out and back in for this to take effect.

3. **Create virtual environment and install dependencies:**
   ```bash
   python3 -m venv nfc_env
   source nfc_env/bin/activate
   pip install -r requirements.txt
   ```

4. **Configure:**
   ```bash
   cp .env.template .env
   nano .env
   ```
   Required settings:
   ```bash
   HA_HOST=192.168.1.100           # Your Home Assistant IP
   HA_TOKEN=<long-lived-token>     # See: Getting a Long-Lived Token below
   ```

5. **Test interactively:**
   ```bash
   source nfc_env/bin/activate
   python nfc_reader_ha_events.py
   ```
   Scan a tag — you should see:
   ```
   🏷️  [12:34:56] NFC Card Detected!
      📋 UID: 04A16D40240289 (logged only)
      🎴 Type: MIFARE Ultralight
      🏷️  NDEF Tag Value: abc123...
      🏠 Delivered via WebSocket
   ```

### systemd Service

Install as a service for automatic startup on boot:

```bash
sudo ./install-service.sh install
sudo systemctl start nfc-reader
sudo systemctl enable nfc-reader
```

**Service management:**
```bash
sudo systemctl status nfc-reader
sudo systemctl restart nfc-reader
journalctl -u nfc-reader -f       # Live logs
journalctl -u nfc-reader -n 50   # Last 50 lines
```

**Uninstall:**
```bash
sudo ./install-service.sh uninstall
```

---

## Getting a Long-Lived Access Token

1. In Home Assistant, go to your **Profile** (click your name in the bottom-left)
2. Scroll to **Long-Lived Access Tokens**
3. Click **Create Token**, give it a name (e.g. `NFC Reader`), copy the token
4. Paste it as `HA_TOKEN=` in your `.env` file

---

## Configuration Reference

All settings live in `.env`. Copy `.env.template` to get started.

### Required

| Variable | Example | Description |
|----------|---------|-------------|
| `HA_HOST` | `192.168.1.100` | Home Assistant IP or hostname |
| `HA_TOKEN` | `eyJ...` | Long-Lived Access Token |

### NFC Reader

| Variable | Default | Description |
|----------|---------|-------------|
| `NFC_AUTO_DETECT` | `true` | Probe all `/dev/ttyUSB*` ports at startup to find the PN532 |
| `NFC_PORT` | *(empty)* | Pin to a specific port (e.g. `/dev/ttyUSB0`); only used when `NFC_AUTO_DETECT=false` |
| `NFC_BAUDRATE` | `115200` | Serial baud rate — do not change |
| `HA_PORT` | `8123` | Home Assistant port |

### WebSocket Mode (v3.0.0)

| Variable | Default | Description |
|----------|---------|-------------|
| `HA_WS_ENABLED` | `true` | Enable WebSocket delivery (recommended). Set `false` to fall back to legacy REST |
| `HA_WS_HEARTBEAT` | `30` | Seconds between keep-alive pings |
| `HA_WS_RECONNECT_MAX` | `60` | Maximum backoff delay (seconds) between reconnect attempts |
| `DEVICE_NAME` | `PN532 NFC Reader` | Name shown in HA Settings → Devices & Services |

### Offline Queue

When the WebSocket connection drops, scans are queued locally and replayed automatically when the connection restores.

| Variable | Default | Description |
|----------|---------|-------------|
| `SCAN_QUEUE_MAX` | `50` | Maximum queued scans (oldest are dropped when full) |
| `SCAN_STALE_SECONDS` | `300` | Scans older than this (seconds) are discarded on replay |

---

## Home Assistant Integration

### How It Works (v3.0.0)

On first run, the service registers itself with HA as a `mobile_app` device — the same registration type used by the iOS and Android companion apps. The registration is saved to `.nfc_reader_registration.json` and reused on subsequent runs.

Each tag scan is delivered as a `webhook/handle` message over the WebSocket, which routes through `tag.async_scan_tag()` internally. This is what causes tags to appear in **Settings → Tags** and `tag.<id>` entities to be created.

### Verifying It Works

After scanning a tag:

1. **Settings → Tags** — your tag appears with a last-scanned timestamp
2. **Settings → Devices & Services → Mobile App** — "PN532 NFC Reader" (or your `DEVICE_NAME`) appears as a device
3. **Developer Tools → Events** — listen for `tag_scanned` events while scanning

### Setting Up Automations

1. Go to **Settings → Automations → Create Automation**
2. Add a trigger: **Tag** → select your tag
3. Add your actions (toggle a light, run a script, etc.)
4. Save — the automation fires the next time you scan the tag

### Preparing Tags

| Tag type | How to write | What the reader sends as `tag_id` |
|----------|-------------|-----------------------------------|
| HA mobile app tag | Settings → Tags → Add Tag, then write with HA app or NFC Tools | UUID extracted from `home-assistant.io/tag/<uuid>` URL |
| Custom NDEF text | Any NFC writer app | The text content of NDEF record 1 |
| Custom NDEF URI | Any NFC writer app | The full URI |
| Blank / unformatted | — | **Ignored** — no event fired |

---

## Troubleshooting

### Service won't start / no PN532 found

```bash
ls /dev/ttyUSB*     # Check the device is present
dmesg | tail -20    # Look for USB serial messages after plugging in
```

Make sure your user is in the `dialout` group:
```bash
groups              # dialout should appear in the list
sudo usermod -a -G dialout $USER   # add if missing, then log out/in
```

### "Permission denied" on serial port (Docker)

Docker is running in rootless mode. Device passthrough requires rootful Docker:
```bash
sudo docker compose up -d    # quick fix: run with sudo
# or switch to system Docker permanently:
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

### WebSocket connection fails

```bash
# Test HA is reachable and the token is valid
curl -H "Authorization: Bearer <your_token>" http://<HA_HOST>:8123/api/
# Should return: {"message": "API running."}
```

The service retries with exponential backoff (1 s → 2 s → 4 s … up to `HA_WS_RECONNECT_MAX`). Check logs for `WebSocket connection failed:` messages.

### Tags not appearing in Settings → Tags

This happens when the NDEF content is not recognised as a HA-format tag. Tags written by the HA mobile app use a `home-assistant.io/tag/<uuid>` URI which the reader extracts automatically. Tags written with a custom text or URI will still deliver a scan event, but won't create a named entry in the Tags panel unless you add them manually.

### Registration issues

The registration file `.nfc_reader_registration.json` stores the `webhook_id` assigned by HA. If HA returns a 410 (webhook expired), the service automatically deletes the file and re-registers. To force re-registration manually:

```bash
rm .nfc_reader_registration.json
# Then restart the service
```

### Fall back to legacy REST mode

Set `HA_WS_ENABLED=false` in `.env` and restart. The service will use `POST /api/events/tag_scanned` instead of the WebSocket webhook. Tags will fire automations but will **not** appear in Settings → Tags.

### No card detection

- Cards must be within ~3 cm of the antenna
- Only ISO14443A cards are supported (MIFARE Ultralight, Classic, DESFire)
- Check the PN532 antenna is connected properly

---

## Project Structure

```
pn532-nfc-reader/
├── nfc_config.py              # Config loader (env vars + PN532 auto-detect)
├── nfc_reader_ha_events.py    # NFCReaderHA class + interactive runner
├── nfc_reader_service.py      # Async systemd daemon wrapper
├── ha_websocket.py            # WebSocket connection manager (auth, heartbeat, backoff)
├── ha_registration.py         # mobile_app device registration
├── ha_tag_scanner.py          # Webhook tag scan dispatch + offline queue
├── tests/                     # Pytest unit + integration tests
├── install-service.sh         # systemd service installer
├── nfc-reader.service         # systemd unit file
├── Dockerfile                 # Container image definition
├── docker-compose.yml         # Docker Compose service definition
├── .env.template              # Configuration template
└── requirements.txt           # Python dependencies
```

---

## Technical Details

- **Python:** 3.10 or later required
- **Communication:** UART at 115200 baud (PN532 HSU mode)
- **NFC standard:** ISO14443A
- **NDEF reading:** MIFARE Ultralight `READ` (0x30) via `InDataExchange` (D4 40), blocks 4–47
- **All PN532 communication** is raw serial bytes — no libnfc or nfcpy dependency
- **HA integration (v3):** WebSocket `webhook/handle` → `tag.async_scan_tag()` via `mobile_app` registration
- **HA integration (legacy):** REST `POST /api/events/tag_scanned`

### Dependencies

| Package | Purpose |
|---------|---------|
| `pyserial` | Serial communication with PN532 |
| `websockets` | Home Assistant WebSocket API (v3 mode) |
| `aiohttp` | Device registration HTTP call |
| `requests` | HA connection test + legacy REST fallback |

---

## License

MIT License — feel free to modify and distribute.
