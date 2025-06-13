# PN532 NFC Card Reader with Home Assistant Integration

A robust Python service for reading NFC cards using a USB-connected PN532 reader, designed for seamless Home Assistant integration with systemd service support.

## Features

- 🏷️ Real-time NFC card detection with NDEF record reading
- 📋 Card UID extraction and logging (for debugging)
- 🏷️ **NDEF tag content extraction** - reads tag values from record 1
- 🎴 Card type identification (MIFARE Classic, Ultralight, etc.)
- 📡 ISO14443A protocol support
- 🔄 Continuous monitoring with timestamps
- 📤 Card removal detection
- 🏠 **Smart Home Assistant integration** - fires events only with NDEF content
- 🎯 **Tag ID as token** - uses NDEF record content instead of UID for events
- 🔧 Systemd service for automatic startup
- 📊 Comprehensive logging and monitoring

## Hardware Requirements

- PN532 NFC module connected via USB-to-serial adapter (like CH340)
- Compatible with any PN532 breakout board

## Installation Options

Choose your preferred installation method:

### 🐳 Docker (Recommended)

**Quick Start:**
```bash
# 1. Copy environment template
cp .env.template .env
# Edit .env with your Home Assistant token and settings

# 2. Find your NFC device
ls /dev/cu.*        # macOS
ls /dev/tty*        # Linux

# 3. Update device path in docker-compose.yml, then run
docker-compose up -d
```

**Pull from Registry:**
```bash
# GitHub Container Registry
docker pull ghcr.io/l0cut15/pn532-nfc-reader-public:latest

# Docker Hub  
docker pull l0cut15/nfc-reader:latest
```

📖 **[Complete Docker Setup Guide](#docker-deployment)**

### 🐍 Native Python Installation

### Prerequisites
- Python 3.7+
- PN532 NFC module connected via USB-to-serial adapter
- Home Assistant instance with API access

### Automated Setup

1. **Clone the repository:**
```bash
git clone <repository-url>
cd pn532-nfc-reader
```

2. **Create virtual environment and install dependencies:**
```bash
python3 -m venv nfc_env
source nfc_env/bin/activate
pip install -r requirements.txt
```

3. **Configure the application:**
```bash
# Copy the template config file
cp config.yaml.template config.yaml

# Edit config.yaml with your settings
nano config.yaml
```

**Required configuration:**
- **Home Assistant host**: Your HA server IP address (e.g., `192.168.1.100:8123`)
- **HA Token**: Create a Long-Lived Access Token in HA Profile settings
- **Device path**: Auto-detected, or specify manually (e.g., `/dev/ttyUSB0`)

4. **Connect your PN532:**
   - Connect PN532 to USB-to-serial adapter
   - Device will be auto-detected, or find manually with `ls /dev/ttyUSB*` (Linux) or `ls /dev/cu.usbserial*` (macOS)

### Service Installation (Recommended)

Install as a systemd service for automatic startup:

```bash
# Install the service
sudo ./install-service.sh install

# Start the service
sudo systemctl start nfc-reader

# Check service status
sudo systemctl status nfc-reader

# View logs
journalctl -u nfc-reader -f
```

### Test Installation

Test the application before installing as a service:
```bash
source nfc_env/bin/activate
python nfc_reader_ha_events.py
```

## Usage

### As a Service (Recommended)
Once installed as a service, the NFC reader runs automatically:
- Starts on boot
- Runs continuously in the background
- Logs to systemd journal
- Auto-restarts on failures

### Manual Operation
For testing:
```bash
source nfc_env/bin/activate
python nfc_reader_ha_events.py
```

### Service Management
```bash
# Control the service
sudo systemctl start nfc-reader     # Start service
sudo systemctl stop nfc-reader      # Stop service  
sudo systemctl restart nfc-reader   # Restart service
sudo systemctl enable nfc-reader    # Enable auto-start on boot
sudo systemctl disable nfc-reader   # Disable auto-start

# Monitor the service
sudo systemctl status nfc-reader    # Check status
journalctl -u nfc-reader -f         # Follow logs
journalctl -u nfc-reader -n 50      # Show last 50 log entries

# Install script commands
sudo ./install-service.sh install   # Install service
sudo ./install-service.sh uninstall # Remove service
sudo ./install-service.sh status    # Show detailed status
```

**What it does:**
- Detects NFC cards and reads NDEF content from record 1
- **Only fires `tag_scanned` events when NDEF data is available**
- Uses NDEF tag content as the token (not UID) for Home Assistant
- Automatically registers new tags in HA (just like the mobile app)
- Creates automations in HA using the actual tag content for actions
- Provides continuous monitoring with automatic reconnection

Place NFC cards near the reader to detect them. The application will:
- Read and extract NDEF record 1 content (tag value)
- Log card UID (for debugging only)
- Identify card type (MIFARE Classic, Ultralight, etc.)
- Record detection timestamps
- Detect card removal events
- **Send events to Home Assistant only when NDEF content is found**

## Example Output

### Service Logs (via journalctl)
```
Jun 12 12:38:29 rpi4 nfc-reader[13581]: 🔧 Testing /dev/ttyUSB0...
Jun 12 12:38:29 rpi4 nfc-reader[13581]: ✅ PN532 found on /dev/ttyUSB0
Jun 12 12:38:29 rpi4 nfc-reader[13581]: ✅ Home Assistant API connection successful
Jun 12 12:38:29 rpi4 nfc-reader[13581]: 🔌 Connecting to PN532 on /dev/ttyUSB0...
Jun 12 12:38:29 rpi4 nfc-reader[13581]: ✅ PN532 ready for NFC detection
Jun 12 12:38:29 rpi4 nfc-reader[13581]: 2025-06-12 12:38:29 - NFC Reader Service started successfully
Jun 12 12:38:29 rpi4 nfc-reader[13581]: 2025-06-12 12:38:29 - Starting NFC card monitoring...
```

### Manual Operation Output
```
🎯 PN532 NFC Card Reader Service
==============================
🔧 Testing /dev/ttyUSB0...
✅ PN532 found on /dev/ttyUSB0
✅ Home Assistant API connection successful
🔌 Connecting to PN532 on /dev/ttyUSB0...
✅ PN532 ready for NFC detection

📡 Monitoring for NFC cards...
🏷️  [14:23:45] NFC Card Detected!
   📋 UID: 0447DF7ADF6180 (logged only)
   🎴 Type: MIFARE Ultralight
   📡 Protocol: ISO14443A
   🏷️  NDEF Tag Value: df72ea0e-c986-42a1-adcf-4313201c63c8
🏠 Fired tag_scanned event with tag_id: df72ea0e-c986-42a1-adcf-4313201c63c8
   ────────────────────────────────────────
📤 [14:23:50] Card removed
```

### Tags Without NDEF Content
```
🏷️  [14:25:12] NFC Card Detected!
   📋 UID: 0411436E240289 (logged only)
   🎴 Type: MIFARE Classic 1K
   📡 Protocol: ISO14443A
   ⚠️  No NDEF data found
📋 No NDEF data found for UID 0411436E240289 - no event fired
   ────────────────────────────────────────
```

## Supported Card Types

**For NDEF Record Reading (Full Functionality):**
- MIFARE Ultralight (with NDEF content)
- MIFARE Classic 1K/4K (with NDEF formatting)
- MIFARE DESFire (with NDEF application)
- Other ISO14443A cards with NDEF records

**For UID Detection Only:**
- Any ISO14443A compatible card
- MIFARE Plus
- Blank or unformatted tags

**Note:** Only cards with programmed NDEF content will fire Home Assistant events. Cards without NDEF data will be detected and logged but no events will be sent.

## Home Assistant Integration

### Event Structure

The NFC reader fires `tag_scanned` events with this structure:
```json
{
  "event_type": "tag_scanned",
  "data": {
    "tag_id": "df72ea0e-c986-42a1-adcf-4313201c63c8",  // NDEF content, not UID
    "device_id": "nfc_reader_main"
  }
}
```

### Key Behavior Changes

- **Events only fire for NDEF tags**: Blank tags are detected but don't fire events
- **Tag ID is NDEF content**: Uses actual tag data instead of hardware UID
- **Supports Home Assistant tag URLs**: Automatically extracts tag IDs from `home-assistant.io/tag/` URLs
- **Backward compatible**: Works with existing HA tag automations

### Integration Steps

1. **Auto-register tags**: When you scan a new NDEF tag, it automatically appears in HA under Settings → Tags
2. **Fire events**: Each NDEF scan fires a `tag_scanned` event that you can use in automations  
3. **Create automations**: In HA, go to Settings → Automations → Create → Tag and select your scanned tag

**Example automation uses:**
- Toggle lights when scanning a tag
- Set thermostat temperature 
- Trigger scenes or scripts
- Send notifications
- Control media players

### Preparing NFC Tags

**For Home Assistant tags:**
1. In HA, go to Settings → Tags → Add Tag
2. Write the tag using HA mobile app or NFC Tools
3. The reader will extract the tag ID from the NDEF URL

**For custom tags:**
- Use NFC Tools app to write NDEF text/URI records
- The reader uses record 1 content as the tag ID

## Essential Files

This release includes the following files required for installation and operation:

### Core Files
- **`nfc_reader_service.py`** - Main service application
- **`nfc_reader_ha_events.py`** - Interactive version  
- **`nfc_config.py`** - Configuration handler
- **`config.yaml.template`** - Configuration template
- **`requirements.txt`** - Python dependencies

### Service Installation
- **`install-service.sh`** - Service installer
- **`nfc-reader.service`** - Systemd service file

### Configuration Required
After cloning, you **must**:
1. Copy `config.yaml.template` to `config.yaml`
2. Edit `config.yaml` with your Home Assistant host, token, and device settings
3. Create virtual environment and install dependencies from `requirements.txt`

## Project Structure

```
nfc-reader/
├── nfc_reader_service.py      # Main service application
├── nfc_reader_ha_events.py    # Interactive version
├── nfc_config.py              # Configuration handler
├── install-service.sh         # Service installer
├── nfc-reader.service         # Systemd service file
├── config.yaml.template       # Configuration template
├── requirements.txt          # Python dependencies
├── Dockerfile                # Docker container build
├── docker-compose.yml        # Docker service orchestration
├── .env.template             # Docker environment variables template
├── docker-env-config.py      # Docker configuration loader
└── README.md                 # This documentation
```


## Troubleshooting

### Service Issues
```bash
# Check if service is running
sudo systemctl status nfc-reader

# View recent logs
journalctl -u nfc-reader -n 50

# Follow live logs
journalctl -u nfc-reader -f

# Restart the service
sudo systemctl restart nfc-reader
```

### Common Problems

**Service won't start:**
- Check that config.yaml exists and is properly configured
- Verify PN532 device is connected and detected
- Ensure virtual environment exists: `ls nfc_env/`
- Check logs: `journalctl -u nfc-reader -n 20`

**Connection Issues:**
- Device auto-detection usually works, manually check with `ls /dev/ttyUSB*` (Linux) or `ls /dev/cu.usbserial*` (macOS)
- Check PN532 wiring and power supply
- Ensure USB-to-serial drivers are installed
- Try different USB ports

**No Card Detection:**
- Verify PN532 is in card reader mode (not P2P/target mode)
- Check card compatibility (ISO14443A cards work best)
- Ensure proper antenna connection on PN532 module
- Cards must be within ~3cm of the reader

**Home Assistant Connection:**
- Verify HA host/IP and port in config.yaml
- Check that Long-Lived Access Token is valid
- Ensure HA is accessible from the device running the service
- Test API connection: check service logs for connection status

**Permission Errors:**
- Service runs as root, so permission issues are rare
- For manual testing, you may need to add user to dialout group: `sudo usermod -a -G dialout $USER`
- Log out and back in after adding to group

### Configuration Issues

**Invalid config.yaml:**
```bash
# Validate your config syntax
python3 -c "import yaml; yaml.safe_load(open('config.yaml'))"

# Compare with template
diff config.yaml.template config.yaml
```

## Technical Details

- **Communication:** Serial/UART at 115200 baud
- **Protocol:** PN532 native command set over HSU (High Speed UART)
- **NFC Standard:** ISO14443A (NFC Type A)
- **Range:** ~3cm depending on antenna and card type
- **Service Type:** systemd Type=simple with auto-restart
- **Logging:** systemd journal with structured logging
- **Security:** Runs as root with minimal privileges, sandboxed filesystem access
- **Resource Limits:** 256MB memory limit, managed file descriptors

### API Integration
- **Home Assistant:** RESTful API with Long-Lived Access Tokens
- **Event Type:** `tag_scanned` events with NDEF content and device info
- **Tag Registration:** Automatic tag entity creation in HA
- **NDEF Support:** Reads URI and text records from NFC tags
- **Smart Filtering:** Only fires events for tags with NDEF content
- **Retry Logic:** Exponential backoff for connection failures

### Dependencies
- `pyserial` - Serial communication with PN532
- `pyyaml` - Configuration file parsing
- `requests` - HTTP API communication with Home Assistant


## License

MIT License - feel free to modify and distribute.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

For bugs and feature requests, please open an issue.

---

## Docker Deployment

### Quick Docker Setup

1. **Environment Configuration:**
   ```bash
   cp .env.template .env
   # Edit .env with your settings:
   # - HA_TOKEN: Your Home Assistant long-lived access token
   # - HA_HOST: Your HA server address (use host.docker.internal for Docker Desktop)
   # - NFC_PORT: Device path (/dev/ttyUSB0 for most setups)
   ```

2. **Device Detection:**
   ```bash
   # macOS (look for cu.usbserial-*)
   ls /dev/cu.*
   
   # Linux (look for ttyUSB* or ttyACM*)
   ls /dev/tty*
   ```

3. **Update docker-compose.yml:**
   Edit the `devices` section to match your NFC device path.

4. **Deploy:**
   ```bash
   docker-compose up -d
   ```

### Registry Images

**GitHub Container Registry (Recommended):**
```bash
docker pull ghcr.io/l0cut15/pn532-nfc-reader-public:latest
```

**Docker Hub:**
```bash
docker pull l0cut15/nfc-reader:latest
```

### Docker Commands

```bash
# View logs
docker-compose logs -f nfc-reader

# Stop service
docker-compose down

# Rebuild and restart
docker-compose build --no-cache
docker-compose up -d

# Health check
docker-compose exec nfc-reader python nfc_reader_service.py health
```

### Device Access Notes

**macOS:** Use `/dev/cu.usbserial-*` device paths
**Linux:** Use `/dev/ttyUSB0` or `/dev/ttyACM0` paths  
**Permissions:** May require privileged mode or specific device mapping

### Security Features

- ✅ No secrets in Docker image
- ✅ Environment-based configuration  
- ✅ Registry-safe builds
- ✅ Minimal attack surface