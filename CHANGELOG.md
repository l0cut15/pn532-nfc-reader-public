# Changelog

All notable changes to this project will be documented in this file.

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
- Comprehensive documentation updates explaining both payload modes
- Configuration reference section in README

### Changed
- Enhanced Home Assistant event structure documentation with payload examples
- Updated integration behavior descriptions for both modes
- Improved troubleshooting section with configuration validation

### Technical Details
- Events are now fired based on `payload_type` configuration
- NDEF mode maintains backward compatibility (existing behavior)
- UUID mode enables detection of blank/unformatted NFC cards
- Migration notes provided for switching between modes

## [2.1] - Previous Release
- Docker deployment support
- Systemd service integration
- NDEF record reading and Home Assistant integration