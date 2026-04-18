# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python service that reads NFC cards via a USB-connected PN532 module (CH340 USB-to-serial adapter) and delivers `tag_scanned` events to Home Assistant. The service runs on a Raspberry Pi 4. As of v3.0.0 it uses the HA WebSocket API + `mobile_app` webhook registration (the same path as the official iOS/Android companion apps), which causes tags to appear in Settings → Tags and `tag.<id>` entities to be created.

## Setup

```bash
# Python 3.10+ required
python3 -m venv nfc_env
source nfc_env/bin/activate
pip install -r requirements.txt

# Configure
cp .env.template .env
# Edit .env: set HA_HOST and HA_TOKEN (minimum required)
```

## Running

```bash
# Interactive (foreground) — primary entry point for manual testing
source nfc_env/bin/activate
python nfc_reader_ha_events.py

# As systemd service
sudo ./install-service.sh install
sudo systemctl start nfc-reader
journalctl -u nfc-reader -f

# Docker
cp .env.template .env  # edit .env with HA_TOKEN, HA_HOST
docker compose up -d
docker compose logs -f nfc-reader
```

## Architecture

```
nfc_config.py           — Config loader (reads env vars) + PN532 auto-detection
nfc_reader_ha_events.py — NFCReaderHA class: serial comms, NDEF parsing; interactive runner
nfc_reader_service.py   — Async systemd daemon; signal handling + rotating logs
ha_websocket.py         — HAWebSocketClient: auth, heartbeat, exponential backoff reconnect
ha_registration.py      — DeviceRegistrar: mobile_app registration, persists webhook_id to disk
ha_tag_scanner.py       — TagScanner: webhook/handle dispatch, offline queue, stale expiry
tests/                  — Pytest unit + integration tests (pytest-asyncio, mock WS server)
```

**Data flow (WS mode, default):**
`NFCConfig` reads env vars → `NFCReaderHA` opens serial port → polls PN532 via raw HSU commands → parses ISO14443A card data → reads NDEF from MIFARE blocks → extracts tag ID → `TagScanner.scan_tag()` → `webhook/handle` message over WebSocket → HA `tag.async_scan_tag()` → Settings → Tags updated.

**Data flow (REST mode, `HA_WS_ENABLED=false`):**
Same NFC path → `NFCReaderHA.fire_tag_scanned_event()` → `POST /api/events/tag_scanned`.

**Key design decisions:**
- Events only fire when NDEF content is found — blank/unformatted tags are detected but silently dropped
- The `tag_id` sent to HA is the NDEF record 1 content (not the hardware UID); for HA-format tags, the UUID is extracted from the `home-assistant.io/tag/` URL
- All PN532 communication is raw serial bytes (no libnfc/nfcpy); HSU wakeup, GetFirmwareVersion, and InDataExchange frames are hand-crafted
- Auto-detection tests each `/dev/ttyUSB*` / `/dev/cu.usbserial*` device for the PN532 firmware response pattern (`\xd5\x03`)
- Blocking serial I/O runs in `asyncio.to_thread()` so it doesn't block the async event loop
- Registration file `.nfc_reader_registration.json` is stored alongside the service; on HTTP 410 from HA, it is deleted and re-registration happens automatically
- `.env` values must not have inline comments — the parser splits on `=` only

## Configuration

All deployments (native, systemd, Docker) use `.env`. Do not put inline comments on value lines.

```bash
HA_HOST=192.168.1.100
HA_PORT=8123
HA_TOKEN=<long-lived-access-token>
NFC_AUTO_DETECT=true
NFC_PORT=/dev/ttyUSB0
NFC_BAUDRATE=115200
HA_WS_ENABLED=true
HA_WS_HEARTBEAT=30
HA_WS_RECONNECT_MAX=60
DEVICE_NAME=PN532 NFC Reader
SCAN_QUEUE_MAX=50
SCAN_STALE_SECONDS=300
```

Systemd loads `.env` via `EnvironmentFile=`. Docker Compose loads it via `env_file:`.

## Device Paths

| Platform | Pattern |
|----------|---------|
| Linux    | `/dev/ttyUSB0`, `/dev/ttyACM0` |
| macOS    | `/dev/cu.usbserial-*` |

Add user to `dialout` group for non-root serial access: `sudo usermod -a -G dialout $USER` (requires re-login).

## PN532 Protocol Notes

Communication is 115200 baud UART (HSU mode). Frames follow the pattern `00 00 FF <LEN> <LCS> <TFI> <CMD> ... <DCS> 00`. NDEF reading uses MIFARE Ultralight `READ` (0x30) command wrapped in `InDataExchange` (D4 40), reading 4 blocks at a time starting at block 4 (capability container at block 3). Bulk reads cover blocks 4–47 (176 bytes) with 2-retry logic per 4-block chunk.
