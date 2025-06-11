#!/usr/bin/env python3
"""
NFC Reader Configuration Module
Handles device detection and configuration management
"""

import yaml
import glob
import serial
import time
from pathlib import Path


class NFCConfig:
    def __init__(self, config_file='config.yaml'):
        self.config_file = config_file
        self.config = self._load_or_create_config()
    
    def _load_or_create_config(self):
        """Load existing config or create default"""
        config_path = Path(self.config_file)
        
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    return yaml.safe_load(f)
            except Exception as e:
                print(f"⚠️  Error loading config: {e}")
                print("🔧 Creating new config...")
        
        # Create default config
        default_config = self._create_default_config()
        self._save_config(default_config)
        return default_config
    
    def _create_default_config(self):
        """Create default configuration"""
        return {
            'nfc_reader': {
                'baudrate': 115200,
                'timeout': 1.0,
                'auto_detect': True,
                'reader_id': 'nfc_reader_main',
                'reader_name': 'Main NFC Reader',
                'location': 'Living Room'
            },
            'home_assistant': {
                'host': 'YOUR_HA_IP_ADDRESS',
                'port': 8123,
                'token': 'YOUR_LONG_LIVED_ACCESS_TOKEN'
            }
        }
    
    def _save_config(self, config):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, indent=2)
        except Exception as e:
            print(f"⚠️  Error saving config: {e}")
    
    def find_nfc_device(self):
        """Auto-detect PN532 USB device"""
        print("🔍 Searching for PN532 devices...")
        
        # Look for USB serial devices
        possible_devices = []
        
        # Check common USB serial patterns
        patterns = [
            '/dev/cu.usbserial*',  # macOS
            '/dev/ttyUSB*',        # Linux
            '/dev/ttyACM*',        # Linux alternative
        ]
        
        for pattern in patterns:
            devices = glob.glob(pattern)
            possible_devices.extend(devices)
        
        if not possible_devices:
            print("❌ No USB serial devices found")
            return None
        
        print(f"📱 Found {len(possible_devices)} USB device(s): {possible_devices}")
        
        # Test each device for PN532 response
        for device in possible_devices:
            if self._test_pn532_device(device):
                print(f"✅ PN532 found on {device}")
                # Update config with found device
                self.config['nfc_reader']['port'] = device
                self._save_config(self.config)
                return device
        
        print("❌ No PN532 devices found on available ports")
        return None
    
    def _test_pn532_device(self, device_path):
        """Test if device is a PN532"""
        try:
            print(f"🔧 Testing {device_path}...")
            ser = serial.Serial(device_path, self.config['nfc_reader']['baudrate'], timeout=1)
            
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
            
            # Check if we got a valid PN532 firmware response
            if response and len(response) > 10:
                # Look for PN532 firmware response pattern
                if b'\xd5\x03' in response:  # PN532 firmware response
                    return True
            
            return False
            
        except Exception as e:
            print(f"❌ Error testing {device_path}: {e}")
            return False
    
    def get_device_port(self):
        """Get the device port, with auto-detection if enabled"""
        if self.config['nfc_reader'].get('auto_detect', True):
            # Try auto-detection first
            detected_port = self.find_nfc_device()
            if detected_port:
                return detected_port
        
        # Fall back to configured port
        configured_port = self.config['nfc_reader'].get('port')
        if configured_port:
            print(f"📌 Using configured port: {configured_port}")
            return configured_port
        
        # No port found
        print("❌ No NFC device port available")
        return None
    
    def get(self, key_path, default=None):
        """Get configuration value using dot notation (e.g., 'mqtt.host')"""
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, key_path, value):
        """Set configuration value using dot notation"""
        keys = key_path.split('.')
        config = self.config
        
        # Navigate to the parent of the target key
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        # Set the value
        config[keys[-1]] = value
        self._save_config(self.config)


# Convenience function to get a configured NFC reader instance
def get_nfc_config():
    """Get NFC configuration instance"""
    return NFCConfig()


if __name__ == "__main__":
    # Test the configuration system
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