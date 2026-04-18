# Changelog

All notable changes to this project will be documented in this file.

## [3.0.1] - 2026-04-18

### Fixed
- **Serial reconnect**: Service now automatically reconnects to the PN532 when a USB serial disconnect is detected (`[Errno 5] Input/output error`), instead of looping indefinitely on a dead connection
- **Docker health check**: Health check subprocess previously always reported unhealthy because it checked an in-process `running` flag that was never set in the new process. Now uses a heartbeat file written every 30 seconds by the monitor loop — health check verifies the file is fresh

## [3.0.0] - 2026-03-11

### Added
- **WebSocket integration**: Service now registers with Home Assistant as a `mobile_app` device and delivers tag scans via the WebSocket API (`webhook/handle`), matching the official iOS/Android companion app path
- Tags now appear in **Settings → Tags** with last-scanned timestamps and create `tag.<id>` entities automatically
- `ha_websocket.py`: async WebSocket client with auth, heartbeat, and exponential backoff reconnect
- `ha_registration.py`: mobile_app device registration; persists `webhook_id` to disk for restart survival
- `ha_tag_scanner.py`: webhook dispatch with offline queue and stale-entry expiry
- Six new config variables: `HA_WS_ENABLED`, `HA_WS_HEARTBEAT`, `HA_WS_RECONNECT_MAX`, `DEVICE_NAME`, `SCAN_QUEUE_MAX`, `SCAN_STALE_SECONDS`
- `README-Docker.md`: dedicated Docker deployment guide

### Changed
- `nfc_reader_service.py`: full async refactor using `asyncio.run` and `asyncio.to_thread` for non-blocking NFC I/O
- `nfc_reader_ha_events.py`: WebSocket path added to interactive mode; REST mode preserved
- `nfc_config.py`: extended with new env vars; PN532 auto-detection improved
- `docker-compose.yml`: adds `./data` volume to persist registration across container restarts

### Backward Compatible
- Set `HA_WS_ENABLED=false` to keep the legacy REST `POST /api/events/tag_scanned` behaviour

## [2.3.0] - 2026-03-10

### Changed
- **Config migrated from YAML to `.env`**: Removed `config.yaml` / `config.yaml.template` entirely; all settings now read from environment variables via `.env` (works for native, systemd, and Docker without any extra tooling)
- **Simplified payload delivery**: Removed configurable `payload_type` option — service now always uses NDEF record content as `tag_id` (cleaner, more predictable behaviour)
- **Refactored `nfc_config.py`**: Dropped `pyyaml` dependency; config loaded directly from `os.environ` with a built-in `.env` parser

### Removed
- `config.yaml.template` — replaced by `.env.template`
- `docker-env-config.py` — no longer needed
- `pyyaml` dependency from `requirements.txt`

### Security
- Strengthened `.gitignore`: now explicitly protects `.env`, virtual environments (`nfc_env/`), `.DS_Store`, and Claude Code dev files

### Added
- `README-Docker.md`: dedicated Docker deployment guide

## [2.2] - 2024-06-20

### Added
- **Configurable payload types**: Choose between NDEF content or UUID as tag payload
- New `payload_type` configuration option in `config.yaml`:
  - `'ndef'` mode: Uses NDEF record content as tag_id (default, backward compatible)
  - `'uuid'` mode: Uses card UID as tag_id (works with all NFC cards including blank ones)

### Changed
- Enhanced Home Assistant event structure documentation with payload examples
- Updated integration behavior descriptions for both modes

## [2.1] - Previous Release
- Docker deployment support
- Systemd service integration
- NDEF record reading and Home Assistant integration
