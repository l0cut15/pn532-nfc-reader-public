# Changelog

All notable changes to this project will be documented in this file.

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