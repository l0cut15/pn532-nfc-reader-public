#!/usr/bin/env python3
"""
NFC Tag Reader with Home Assistant Event Integration
Sends tag_scanned events directly to HA API (like mobile app)
"""

import serial
import time
import sys
import requests
import json
from datetime import datetime
from nfc_config import get_nfc_config


class NFCReaderHA:
    def __init__(self):
        self.config = get_nfc_config()
        self.port = self.config.get_device_port()
        self.baudrate = self.config.get('nfc_reader.baudrate', 115200)
        self.serial = None
        self.last_uid = None
        
        # Home Assistant API settings
        self.ha_host = self.config.get('home_assistant.host')
        self.ha_port = self.config.get('home_assistant.port', 8123)
        self.ha_token = self.config.get('home_assistant.token')
        self.ha_url = f"http://{self.ha_host}:{self.ha_port}"
        
    def connect_serial(self):
        """Connect to PN532"""
        if not self.port:
            print("❌ No NFC device found")
            return False
            
        try:
            print(f"🔌 Connecting to PN532 on {self.port}...")
            self.serial = serial.Serial(self.port, self.baudrate, timeout=0.5)
            
            # Initialize PN532
            self._wakeup()
            self._configure()
            
            print("✅ PN532 ready for NFC detection")
            return True
        except Exception as e:
            print(f"❌ Serial connection failed: {e}")
            return False
    
    def _wakeup(self):
        """Wake up PN532 with proper HSU sequence"""
        # HSU wakeup sequence that actually works
        wakeup_cmd = b'\x55\x55\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xFF\x03\xFD\xD4\x14\x01\x17\x00'
        self.serial.write(wakeup_cmd)
        time.sleep(1)  # Give more time for response
        response = self.serial.read_all()
        print(f"🔧 Wakeup response: {response.hex() if response else 'None'}")
        
        # Get firmware version to confirm communication
        fw_cmd = b'\x00\x00\xFF\x02\xFE\xD4\x02\x2A\x00'
        self.serial.write(fw_cmd)
        time.sleep(0.5)
        response = self.serial.read_all()
        print(f"🔧 Firmware response: {response.hex() if response else 'None'}")
    
    def _configure(self):
        """Configure PN532 for card detection"""
        config_cmd = b'\x00\x00\xFF\x05\xFB\xD4\x14\x01\x14\x01\x02\x00'
        self.serial.write(config_cmd)
        time.sleep(0.2)
        self.serial.read_all()  # Clear response
    
    def scan_for_card(self):
        """Scan for NFC card and return card info if found"""
        scan_cmd = b'\x00\x00\xFF\x04\xFC\xD4\x4A\x01\x00\xE1\x00'
        self.serial.write(scan_cmd)
        time.sleep(0.3)
        
        response = self.serial.read_all()
        if not response or len(response) < 15:
            return None
        
        return self._parse_card_data(response)
    
    def _parse_card_data(self, data):
        """Parse card data from PN532 response"""
        data_bytes = list(data)
        
        # Find frame start
        for i in range(len(data_bytes) - 10):
            if (data_bytes[i:i+3] == [0x00, 0x00, 0xFF] and 
                i + 6 < len(data_bytes) and 
                data_bytes[i+5] == 0xD5 and 
                data_bytes[i+6] == 0x4B):
                
                # Parse target data
                if i + 12 < len(data_bytes):
                    num_targets = data_bytes[i+7]
                    if num_targets > 0:
                        sens_res = data_bytes[i+9:i+11]
                        sel_res = data_bytes[i+11]
                        uid_len = data_bytes[i+12]
                        
                        if i + 13 + uid_len <= len(data_bytes):
                            uid = data_bytes[i+13:i+13+uid_len]
                            uid_hex = ''.join(f'{b:02X}' for b in uid)
                            
                            # Determine card type
                            card_types = {
                                0x00: "MIFARE Ultralight",
                                0x08: "MIFARE Classic 1K", 
                                0x18: "MIFARE Classic 4K",
                                0x20: "MIFARE DESFire",
                                0x44: "MIFARE Plus"
                            }
                            
                            card_type = card_types.get(sel_res, f"Unknown (SAK: 0x{sel_res:02X})")
                            
                            return {
                                'uid': uid_hex,
                                'type': card_type,
                                'protocol': 'ISO14443A',
                                'sens_res': sens_res,
                                'sel_res': sel_res
                            }
        return None
    
    def test_ha_connection(self):
        """Test Home Assistant API connection"""
        if not self.ha_token or self.ha_token == 'YOUR_LONG_LIVED_ACCESS_TOKEN':
            print("❌ Please set your Home Assistant long-lived access token in config.yaml")
            print("   Go to HA → Profile → Long-Lived Access Tokens → Create Token")
            return False
        
        try:
            headers = {
                'Authorization': f'Bearer {self.ha_token}',
                'Content-Type': 'application/json'
            }
            response = requests.get(f"{self.ha_url}/api/", headers=headers, timeout=5)
            
            if response.status_code == 200:
                print("✅ Home Assistant API connection successful")
                return True
            else:
                print(f"❌ HA API returned status {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Failed to connect to HA API: {e}")
            return False
    
    def fire_tag_scanned_event(self, card_data):
        """Fire a tag_scanned event to Home Assistant (like mobile app)"""
        if not self.ha_token:
            print("❌ No HA API token configured")
            return False
        
        # Create the tag_scanned event payload (matching mobile app format)
        event_data = {
            'tag_id': card_data['uid'],  # Use UID as tag_id
            'device_id': self.config.get('nfc_reader.reader_id', 'nfc_reader_main')
        }
        
        headers = {
            'Authorization': f'Bearer {self.ha_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            url = f"{self.ha_url}/api/events/tag_scanned"
            response = requests.post(url, headers=headers, json=event_data, timeout=5)
            
            if response.status_code == 200:
                print(f"🏠 Fired tag_scanned event: {card_data['uid']}")
                return True
            else:
                print(f"❌ HA API error {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Failed to fire HA event: {e}")
            return False
    
    def start_monitoring(self):
        """Start continuous monitoring for NFC cards"""
        print("\n📡 Monitoring for NFC cards...")
        print("Tag scans will fire tag_scanned events in Home Assistant")
        print("Press Ctrl+C to exit\n")
        
        try:
            while True:
                card = self.scan_for_card()
                
                if card:
                    if card['uid'] != self.last_uid:
                        # New card detected
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        print(f"🏷️  [{timestamp}] NFC Card Detected!")
                        print(f"   📋 UID: {card['uid']}")
                        print(f"   🎴 Type: {card['type']}")
                        print(f"   📡 Protocol: {card['protocol']}")
                        
                        # Fire Home Assistant event
                        self.fire_tag_scanned_event(card)
                        
                        print("   " + "─" * 40)
                        self.last_uid = card['uid']
                else:
                    if self.last_uid:
                        # Card removed
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        print(f"📤 [{timestamp}] Card removed")
                        self.last_uid = None
                
                time.sleep(0.5)
                
        except KeyboardInterrupt:
            print("\n👋 Stopping NFC monitor...")
    
    def disconnect(self):
        """Close connections"""
        if self.serial:
            self.serial.close()


def main():
    print("🎯 PN532 NFC Reader - Home Assistant Events")
    print("=" * 50)
    
    reader = NFCReaderHA()
    
    # Test HA connection first
    if not reader.test_ha_connection():
        print("\n💡 To fix this:")
        print("1. Go to Home Assistant → Profile → Long-Lived Access Tokens")
        print("2. Create a new token")
        print("3. Copy the token to config.yaml under home_assistant.token")
        return 1
    
    # Connect to serial port
    if not reader.connect_serial():
        return 1
    
    try:
        reader.start_monitoring()
    finally:
        reader.disconnect()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())