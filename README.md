# PN532 NFC Card Reader

A Python application to read NFC cards using a USB-connected PN532 reader via serial communication.

## Features

- 🏷️ Real-time NFC card detection
- 📋 Card UID extraction and display
- 🎴 Card type identification (MIFARE Classic, Ultralight, etc.)
- 📡 ISO14443A protocol support
- 🔄 Continuous monitoring with timestamps
- 📤 Card removal detection

## Hardware Requirements

- PN532 NFC module connected via USB-to-serial adapter (like CH340)
- Compatible with any PN532 breakout board

## Setup

1. **Create virtual environment:**
```bash
python3 -m venv nfc_env
source nfc_env/bin/activate  # On Windows: nfc_env\Scripts\activate
```

2. **Install dependencies:**
```bash
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
- **Home Assistant host**: Your HA server IP address
- **HA Token**: Create a Long-Lived Access Token in HA Profile settings
- **Device path**: Update with your PN532 device path (e.g., `/dev/cu.usbserial-4120`)

4. **Connect your PN532:**
   - Connect PN532 to USB-to-serial adapter
   - Find device path with `ls /dev/cu.usbserial*` (macOS) or `ls /dev/ttyUSB*` (Linux)

## Usage

Run the NFC reader with Home Assistant integration:
```bash
source nfc_env/bin/activate
python nfc_reader_ha_events.py
```

**What it does:**
- Detects NFC cards and fires `tag_scanned` events to Home Assistant
- Automatically registers new tags in HA (just like the mobile app)
- Creates automations in HA using the Tag ID for various actions

Place NFC cards near the reader to detect them. The application will display:
- Card UID (unique identifier)
- Card type (MIFARE Classic, Ultralight, etc.)
- Detection timestamps
- Card removal events

Press `Ctrl+C` to exit.

## Example Output

```
🎯 PN532 NFC Card Reader
==============================
🔌 Connecting to PN532 on /dev/cu.usbserial-4120...
✅ PN532 ready for NFC detection

📡 Monitoring for NFC cards...
Place a card near the reader to detect it
Press Ctrl+C to exit

🏷️  [14:23:45] NFC Card Detected!
   📋 UID: 0411436E240289
   🎴 Type: MIFARE Ultralight
   📡 Protocol: ISO14443A
   ────────────────────────────────────────
📤 [14:23:50] Card removed
```

## Supported Card Types

- MIFARE Classic 1K/4K
- MIFARE Ultralight
- MIFARE DESFire
- MIFARE Plus
- Other ISO14443A compatible cards

## Home Assistant Integration

Once running, the NFC reader will:

1. **Auto-register tags**: When you scan a new NFC tag, it automatically appears in HA under Settings → Tags
2. **Fire events**: Each scan fires a `tag_scanned` event that you can use in automations
3. **Create automations**: In HA, go to Settings → Automations → Create → Tag and select your scanned tag

**Example automation uses:**
- Toggle lights when scanning a tag
- Set thermostat temperature 
- Trigger scenes or scripts
- Send notifications
- Control media players

## Files

- `nfc_reader_ha_events.py` - Main NFC reader with HA integration
- `nfc_config.py` - Configuration file parser
- `config.yaml.template` - Configuration template (copy to config.yaml)
- `requirements.txt` - Python dependencies
- `README.md` - This documentation


## Troubleshooting

**Connection Issues:**
- Verify USB device path with `ls /dev/cu.usbserial*` (macOS) or `ls /dev/ttyUSB*` (Linux)
- Check PN532 wiring and power supply
- Ensure USB-to-serial drivers are installed

**No Card Detection:**
- Verify PN532 is in card reader mode (not P2P/target mode)
- Check card compatibility (ISO14443A cards work best)
- Ensure proper antenna connection on PN532 module

**Permission Errors:**
- On Linux/macOS, you may need to add user to dialout group or run with sudo
- Check device file permissions

## Technical Details

- **Communication:** Serial/UART at 115200 baud
- **Protocol:** PN532 native command set
- **NFC Standard:** ISO14443A (NFC Type A)
- **Range:** ~3cm depending on antenna and card type

## License

MIT License - feel free to modify and distribute.