# Docker Deployment

For full Docker setup instructions, see the **Quick Start — Docker** section in [README.md](README.md).

## Quick reference

```bash
# 1. Configure
cp .env.template .env
nano .env   # set HA_HOST and HA_TOKEN (minimum required)

# 2. Start
docker compose up -d
docker compose logs -f nfc-reader
```

The image is pulled automatically from `ghcr.io/l0cut15/pn532-nfc-reader:latest` — no local build needed.

## First-run output

```
✅ PN532 found on /dev/ttyUSB0
✅ Device registered with Home Assistant
✅ WebSocket connected
📡 Monitoring for NFC cards...
```

After the first run, a `data/` directory is created containing `.nfc_reader_registration.json`. This persists the HA device registration across container restarts — do not delete it unless you want to re-register.
