#!/usr/bin/env python3
"""
NFC Reader Configuration Module
Reads configuration from environment variables (set via .env for all deployment methods)
"""

import os
import glob
import serial
import time
from pathlib import Path


def _load_dotenv(path='.env'):
    """Load key=value pairs from a .env file into os.environ (skip if already set)."""
    env_path = Path(path)
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


_load_dotenv()


class NFCConfig:
    def __init__(self):
        self._config = {
            'home_assistant': {
                'host':  os.getenv('HA_HOST', 'localhost'),
                'port':  int(os.getenv('HA_PORT', '8123')),
                'token': os.getenv('HA_TOKEN', ''),
            },
            'nfc_reader': {
                'baudrate':    int(os.getenv('NFC_BAUDRATE', '115200')),
                'timeout':     float(os.getenv('NFC_TIMEOUT', '1.0')),
                'auto_detect': os.getenv('NFC_AUTO_DETECT', 'true').lower() == 'true',
                'port':        os.getenv('NFC_PORT', ''),
                'reader_id':   os.getenv('NFC_READER_ID', 'nfc_reader_main'),
                'reader_name': os.getenv('NFC_READER_NAME', 'Main NFC Reader'),
                'location':    os.getenv('NFC_LOCATION', 'Living Room'),
            },
            'websocket': {
                'enabled':       os.getenv('HA_WS_ENABLED', 'true').lower() == 'true',
                'heartbeat':     int(os.getenv('HA_WS_HEARTBEAT', '30')),
                'reconnect_max': int(os.getenv('HA_WS_RECONNECT_MAX', '60')),
            },
            'device': {
                'name': os.getenv('DEVICE_NAME', 'PN532 NFC Reader'),
            },
            'scan': {
                'queue_max':     int(os.getenv('SCAN_QUEUE_MAX', '50')),
                'stale_seconds': int(os.getenv('SCAN_STALE_SECONDS', '300')),
            },
        }

    def get(self, key_path, default=None):
        """Get configuration value using dot notation (e.g., 'home_assistant.host')"""
        keys = key_path.split('.')
        value = self._config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def get_device_port(self):
        """Get the device port, with auto-detection if enabled"""
        if self._config['nfc_reader'].get('auto_detect', True):
            detected_port = self.find_nfc_device()
            if detected_port:
                return detected_port

        configured_port = self._config['nfc_reader'].get('port')
        if configured_port:
            print(f"📌 Using configured port: {configured_port}")
            return configured_port

        print("❌ No NFC device port available")
        return None

    def find_nfc_device(self):
        """Auto-detect PN532 USB device"""
        print("🔍 Searching for PN532 devices...")

        possible_devices = []
        patterns = [
            '/dev/cu.usbserial*',  # macOS
            '/dev/ttyUSB*',        # Linux
            '/dev/ttyACM*',        # Linux alternative
        ]

        for pattern in patterns:
            possible_devices.extend(glob.glob(pattern))

        if not possible_devices:
            print("❌ No USB serial devices found")
            return None

        print(f"📱 Found {len(possible_devices)} USB device(s): {possible_devices}")

        for device in possible_devices:
            if self._test_pn532_device(device):
                print(f"✅ PN532 found on {device}")
                return device

        print("❌ No PN532 devices found on available ports")
        return None

    def _test_pn532_device(self, device_path):
        """Test if device is a PN532"""
        try:
            print(f"🔧 Testing {device_path}...")
            ser = serial.Serial(device_path, self._config['nfc_reader']['baudrate'], timeout=1)

            # Send PN532 wakeup command
            wakeup_cmd = b'\x55\x55\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xFF\x03\xFD\xD4\x14\x01\x17\x00'
            ser.write(wakeup_cmd)
            time.sleep(0.5)

            # Get firmware version
            fw_cmd = b'\x00\x00\xFF\x02\xFE\xD4\x02\x2A\x00'
            ser.write(fw_cmd)
            time.sleep(0.5)

            response = ser.read_all()
            ser.close()

            if response and len(response) > 10:
                if b'\xd5\x03' in response:
                    return True

            return False

        except Exception as e:
            print(f"❌ Error testing {device_path}: {e}")
            return False


def get_nfc_config():
    """Get NFC configuration instance"""
    return NFCConfig()


if __name__ == "__main__":
    config = NFCConfig()
    print("🔧 Testing NFC Configuration")
    print("=" * 40)

    port = config.get_device_port()
    if port:
        print(f"✅ NFC device ready on {port}")
    else:
        print("❌ No NFC device found")

    print(f"📊 HA Host: {config.get('home_assistant.host')}")
    print(f"📊 Reader ID: {config.get('nfc_reader.reader_id')}")
