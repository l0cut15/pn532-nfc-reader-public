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
        time.sleep(0.2)  # Reduced wakeup delay
        response = self.serial.read_all()
        
        # Get firmware version to confirm communication
        fw_cmd = b'\x00\x00\xFF\x02\xFE\xD4\x02\x2A\x00'
        self.serial.write(fw_cmd)
        time.sleep(0.5)
        response = self.serial.read_all()
    
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
        time.sleep(0.1)
        
        response = self.serial.read_all()
        if not response or len(response) < 15:
            return None
        
        card_data = self._parse_card_data(response)
        if card_data:
            # Try to read NDEF data
            ndef_data = self._read_ndef_record_1(card_data.get('target_id', 1))
            if ndef_data:
                card_data['tag_value'] = ndef_data
        
        return card_data
    
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
                                'sel_res': sel_res,
                                'target_id': 1  # Default target ID for PN532
                            }
        return None
    
    def _read_ndef_record_1(self, target_id):
        """Read NDEF record 1 from NFC tag with bulk reading and validation"""
        try:
            # Read the NDEF tag starting from block 4 (typical for MIFARE Ultralight)
            # First, read the capability container to determine NDEF structure
            cc_data = self._read_tag_data(target_id, 3, 1)  # Read CC from block 3
            if not cc_data:
                return None
            
            # Read NDEF data in larger chunks for better performance
            # Read blocks 4-47 to ensure we get complete NDEF messages (176 bytes total)
            ndef_data = self._read_tag_data_bulk(target_id, 4, 44)
            
            if not ndef_data or len(ndef_data) < 4:  # Need at least TLV header
                return None
            
            # Parse NDEF message to extract record 1 with validation
            return self._parse_ndef_record_1_validated(ndef_data)
            
        except Exception as e:
            print(f"Failed to read NDEF record 1: {e}")
            return None
    
    def _read_tag_data(self, target_id, start_block, num_blocks):
        """Read data from NFC tag using InDataExchange"""
        try:
            # MIFARE Ultralight READ command (0x30) - reads 4 blocks at once
            read_cmd_data = [0x30, start_block]
            
            # Build InDataExchange command: D4 40 TG [data]
            # TG = target number (should be 1 for the detected card)
            data_payload = [0xD4, 0x40, 0x01] + read_cmd_data  # Use target 1
            
            # Build full frame: 00 00 FF LEN LCS [data] DCS 00
            data_len = len(data_payload)
            lcs = (256 - data_len) & 0xFF
            
            cmd = [0x00, 0x00, 0xFF, data_len, lcs] + data_payload
            
            # Calculate DCS (Data Checksum) - checksum of data payload only
            dcs = (256 - sum(data_payload)) & 0xFF
            cmd.append(dcs)
            cmd.append(0x00)  # Postamble
            
            self.serial.write(bytes(cmd))
            time.sleep(0.1)  # Optimized response time
            
            response = self.serial.read_all()
            
            if not response or len(response) < 8:
                return None
            
            # Parse response
            return self._parse_data_exchange_response(response)
            
        except Exception as e:
            print(f"Failed to read tag data: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _parse_data_exchange_response(self, data):
        """Parse InDataExchange response"""
        data_bytes = list(data)
        
        # Look for response frame: 0000FF + len + lcs + D5 + 41 + status + data
        for i in range(len(data_bytes) - 8):
            if (data_bytes[i:i+3] == [0x00, 0x00, 0xFF] and 
                i + 7 < len(data_bytes) and
                data_bytes[i+5] == 0xD5 and 
                data_bytes[i+6] == 0x41):  # InDataExchange response
                
                status = data_bytes[i+7]
                
                if status == 0x00:  # Success
                    # Extract data payload
                    frame_len = data_bytes[i+3]
                    data_len = frame_len - 3  # Subtract D5, 41, status
                    
                    if i + 8 + data_len <= len(data_bytes):
                        payload = data_bytes[i+8:i+8+data_len]
                        return payload
        
        return None
    
    def _read_tag_data_bulk(self, target_id, start_block, num_blocks):
        """Read multiple blocks from NFC tag in bulk for better performance"""
        try:
            all_data = []
            blocks_per_read = 4  # MIFARE Ultralight reads 4 blocks at once
            max_retries = 2
            
            for block_start in range(start_block, start_block + num_blocks, blocks_per_read):
                block_data = None
                
                # Retry failed reads to handle intermittent communication issues
                for retry in range(max_retries):
                    block_data = self._read_tag_data(target_id, block_start, 1)
                    if block_data:
                        break
                    elif retry < max_retries - 1:
                        time.sleep(0.05)  # Brief pause before retry
                
                if block_data:
                    all_data.extend(block_data)
                else:
                    # For NDEF reading, we need the complete message
                    # If we're past block 8 and have some data, return what we have
                    if block_start > start_block + 16 and len(all_data) > 50:
                        break
                    else:
                        # Early blocks are critical, fail if we can't read them
                        return None
            
            return all_data if all_data else None
            
        except Exception as e:
            print(f"Failed to bulk read tag data: {e}")
            return None
    
    def _parse_ndef_record_1_validated(self, ndef_data):
        """Parse NDEF data with complete record validation"""
        if not ndef_data or len(ndef_data) < 3:
            return None
        
        try:
            # Look for NDEF message start
            i = 0
            
            # Skip initial bytes until we find NDEF message
            while i < len(ndef_data):
                if ndef_data[i] == 0x03:  # NDEF message TLV
                    i += 1
                    
                    # Get message length
                    if i >= len(ndef_data):
                        break
                    msg_len = ndef_data[i]
                    i += 1
                    
                    # Validate we have enough data for the complete message
                    if i + msg_len > len(ndef_data):
                        # Try to read more data if we're close
                        if len(ndef_data) - i > msg_len * 0.8:  # We have at least 80% of the message
                            available_data = ndef_data[i:len(ndef_data)]
                            if len(available_data) > 10:  # Minimum viable NDEF record
                                result = self._parse_first_ndef_record(available_data)
                                if result:
                                    return result
                        return None
                    
                    # Extract the complete NDEF message
                    ndef_message = ndef_data[i:i + msg_len]
                    
                    # Parse the first record with length validation
                    return self._parse_first_ndef_record(ndef_message)
                    
                elif ndef_data[i] == 0x00 or ndef_data[i] == 0xFE:  # Skip padding/terminator
                    i += 1
                else:
                    i += 1
                
        except Exception as e:
            print(f"NDEF validation error: {e}")
            return None
        
        return None
    
    def _parse_first_ndef_record(self, ndef_message):
        """Parse the first NDEF record with complete validation"""
        if not ndef_message or len(ndef_message) < 3:
            return None
        
        try:
            i = 0
            header = ndef_message[i]
            
            # Parse header flags
            mb = (header & 0x80) != 0  # Message Begin
            me = (header & 0x40) != 0  # Message End
            cf = (header & 0x20) != 0  # Chunk Flag
            sr = (header & 0x10) != 0  # Short Record
            il = (header & 0x08) != 0  # ID Length present
            tnf = header & 0x07        # Type Name Format
            
            i += 1
            
            # Get type length
            if i >= len(ndef_message):
                return None
            type_len = ndef_message[i]
            i += 1
            
            # Get payload length
            if sr:  # Short record
                if i >= len(ndef_message):
                    return None
                payload_len = ndef_message[i]
                i += 1
            else:  # Normal record
                if i + 3 >= len(ndef_message):
                    return None
                payload_len = (ndef_message[i] << 24) | (ndef_message[i+1] << 16) | (ndef_message[i+2] << 8) | ndef_message[i+3]
                i += 4
            
            # Skip ID length if present
            id_len = 0
            if il:
                if i >= len(ndef_message):
                    return None
                id_len = ndef_message[i]
                i += 1
            
            # Validate we have enough data for type, id, and payload
            required_len = type_len + id_len + payload_len
            if i + required_len > len(ndef_message):
                return None
            
            # Read type
            record_type = ndef_message[i:i+type_len]
            i += type_len
            
            # Skip ID if present
            if il:
                i += id_len
            
            # Read complete payload
            payload = ndef_message[i:i+payload_len]
            
            # Validate minimum tag ID length
            tag_value = self._extract_tag_value(record_type, payload)
            if tag_value and len(tag_value.strip()) >= 8:  # Minimum 8 chars for valid tag ID
                return tag_value
            else:
                return None
                
        except Exception as e:
            print(f"NDEF record parsing error: {e}")
            return None
        
        return None
    
    def _extract_tag_value(self, record_type, payload):
        """Extract tag value from NDEF record payload"""
        try:
            # Handle URI record specifically
            if record_type and record_type[0] == 0x55:  # 'U' for URI
                if payload and len(payload) > 0:
                    uri_id = payload[0]
                    uri_prefixes = {
                        0x00: "",
                        0x01: "http://www.",
                        0x02: "https://www.",
                        0x03: "http://",
                        0x04: "https://",
                        0x05: "tel:",
                        0x06: "mailto:",
                        0x07: "ftp://anonymous:anonymous@",
                        0x08: "ftp://ftp.",
                        0x09: "ftps://",
                        0x0A: "sftp://",
                        0x0B: "smb://",
                        0x0C: "nfs://",
                        0x0D: "ftp://",
                        0x0E: "dav://",
                        0x0F: "news:",
                        0x10: "telnet://",
                        0x11: "imap:",
                        0x12: "rtsp://",
                        0x13: "urn:",
                        0x14: "pop:",
                        0x15: "sip:",
                        0x16: "sips:",
                        0x17: "tftp:",
                        0x18: "btspp://",
                        0x19: "btl2cap://",
                        0x1A: "btgoep://",
                        0x1B: "tcpobex://",
                        0x1C: "irdaobex://",
                        0x1D: "file://",
                        0x1E: "urn:epc:id:",
                        0x1F: "urn:epc:tag:",
                        0x20: "urn:epc:pat:",
                        0x21: "urn:epc:raw:",
                        0x22: "urn:epc:",
                        0x23: "urn:nfc:"
                    }
                    
                    prefix = uri_prefixes.get(uri_id, f"[{uri_id:02X}]")
                    uri_suffix = bytes(payload[1:]).decode('utf-8', errors='ignore')
                    full_uri = prefix + uri_suffix
                    
                    # Extract just the tag ID suffix from Home Assistant URLs
                    # Pattern: https://www.home-assistant.io/tag/[TAG_ID]
                    if '/tag/' in uri_suffix:
                        tag_id = uri_suffix.split('/tag/')[-1]
                        return tag_id
                    else:
                        # For non-HA URLs, return the full URI
                        return full_uri
            
            # Handle text record
            elif record_type and record_type[0] == 0x54:  # 'T' for Text
                if payload and len(payload) > 0:
                    lang_len = payload[0] & 0x3F
                    if len(payload) > lang_len + 1:
                        text_data = bytes(payload[lang_len + 1:])
                        text = text_data.decode('utf-8', errors='ignore')
                        return text
            
            # Fallback: return payload as text if possible
            try:
                text = bytes(payload).decode('utf-8', errors='ignore')
                if text.strip():
                    return text
            except:
                pass
            
            # Last resort: return hex
            return ''.join(f'{b:02X}' for b in payload)
            
        except Exception as e:
            print(f"Tag value extraction error: {e}")
            return None
    
    def _parse_ndef_record_1(self, ndef_data):
        """Parse NDEF data to extract record 1 content"""
        if not ndef_data or len(ndef_data) < 3:
            return None
        
        try:
            # Look for NDEF message start
            i = 0
            
            # Skip initial bytes until we find NDEF message
            while i < len(ndef_data):
                if ndef_data[i] == 0x03:  # NDEF message TLV
                    i += 1
                    
                    # Get message length
                    if i >= len(ndef_data):
                        break
                    msg_len = ndef_data[i]
                    i += 1
                    
                    # Now parse the NDEF record
                    if i >= len(ndef_data):
                        break
                        
                    header = ndef_data[i]
                    
                    # Parse header flags
                    mb = (header & 0x80) != 0  # Message Begin
                    me = (header & 0x40) != 0  # Message End
                    cf = (header & 0x20) != 0  # Chunk Flag
                    sr = (header & 0x10) != 0  # Short Record
                    il = (header & 0x08) != 0  # ID Length present
                    tnf = header & 0x07        # Type Name Format
                    
                    i += 1
                    
                    # Get type length
                    if i >= len(ndef_data):
                        break
                    type_len = ndef_data[i]
                    i += 1
                    
                    # Get payload length
                    if sr:  # Short record
                        if i >= len(ndef_data):
                            break
                        payload_len = ndef_data[i]
                        i += 1
                    else:  # Normal record
                        if i + 3 >= len(ndef_data):
                            break
                        payload_len = (ndef_data[i] << 24) | (ndef_data[i+1] << 16) | (ndef_data[i+2] << 8) | ndef_data[i+3]
                        i += 4
                    
                    # Skip ID length if present
                    if il:
                        if i >= len(ndef_data):
                            break
                        id_len = ndef_data[i]
                        i += 1
                    
                    # Read type
                    if i + type_len > len(ndef_data):
                        break
                    record_type = ndef_data[i:i+type_len]
                    i += type_len
                    
                    # Skip ID if present
                    if il:
                        i += id_len
                    
                    # Read payload - ensure we get the complete payload
                    if i + payload_len > len(ndef_data):
                        # Take what we can get - the extended reading should have captured enough
                        payload = ndef_data[i:]
                    else:
                        payload = ndef_data[i:i+payload_len]
                    
                    # Handle URI record specifically
                    if record_type and record_type[0] == 0x55:  # 'U' for URI
                        if payload and len(payload) > 0:
                            uri_id = payload[0]
                            uri_prefixes = {
                                0x00: "",
                                0x01: "http://www.",
                                0x02: "https://www.",
                                0x03: "http://",
                                0x04: "https://",
                                0x05: "tel:",
                                0x06: "mailto:",
                                0x07: "ftp://anonymous:anonymous@",
                                0x08: "ftp://ftp.",
                                0x09: "ftps://",
                                0x0A: "sftp://",
                                0x0B: "smb://",
                                0x0C: "nfs://",
                                0x0D: "ftp://",
                                0x0E: "dav://",
                                0x0F: "news:",
                                0x10: "telnet://",
                                0x11: "imap:",
                                0x12: "rtsp://",
                                0x13: "urn:",
                                0x14: "pop:",
                                0x15: "sip:",
                                0x16: "sips:",
                                0x17: "tftp:",
                                0x18: "btspp://",
                                0x19: "btl2cap://",
                                0x1A: "btgoep://",
                                0x1B: "tcpobex://",
                                0x1C: "irdaobex://",
                                0x1D: "file://",
                                0x1E: "urn:epc:id:",
                                0x1F: "urn:epc:tag:",
                                0x20: "urn:epc:pat:",
                                0x21: "urn:epc:raw:",
                                0x22: "urn:epc:",
                                0x23: "urn:nfc:"
                            }
                            
                            prefix = uri_prefixes.get(uri_id, f"[{uri_id:02X}]")
                            uri_suffix = bytes(payload[1:]).decode('utf-8', errors='ignore')
                            full_uri = prefix + uri_suffix
                            
                            # Extract just the tag ID suffix from Home Assistant URLs
                            # Pattern: https://www.home-assistant.io/tag/[TAG_ID]
                            if '/tag/' in uri_suffix:
                                tag_id = uri_suffix.split('/tag/')[-1]
                                return tag_id
                            else:
                                # For non-HA URLs, return the full URI
                                return full_uri
                    
                    # Handle text record
                    elif record_type and record_type[0] == 0x54:  # 'T' for Text
                        if payload and len(payload) > 0:
                            lang_len = payload[0] & 0x3F
                            if len(payload) > lang_len + 1:
                                text_data = bytes(payload[lang_len + 1:])
                                text = text_data.decode('utf-8', errors='ignore')
                                print(f"Decoded text: {text}")
                                return text
                    
                    # Fallback: return payload as text if possible
                    try:
                        text = bytes(payload).decode('utf-8', errors='ignore')
                        if text.strip():
                            return text
                    except:
                        pass
                    
                    # Last resort: return hex
                    return ''.join(f'{b:02X}' for b in payload)
                    
                elif ndef_data[i] == 0x00 or ndef_data[i] == 0xFE:  # Skip padding/terminator
                    i += 1
                else:
                    i += 1
                
        except Exception as e:
            print(f"NDEF parsing error: {e}")
            import traceback
            traceback.print_exc()
            return None
        
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
        """Fire a tag_scanned event to Home Assistant using configurable payload type"""
        if not self.ha_token:
            print("❌ No HA API token configured")
            return False
        
        # Get payload type configuration (default to 'ndef' for backward compatibility)
        payload_type = self.config.get('nfc_reader.payload_type', 'ndef').lower()
        
        # Determine tag_id based on payload type
        if payload_type == 'uuid':
            # Use UUID as tag_id
            tag_id = card_data['uid']
            print(f"📋 Using UUID as payload: {tag_id}")
        else:
            # Use NDEF content as tag_id (default behavior)
            if 'tag_value' not in card_data or not card_data['tag_value']:
                print(f"📋 No NDEF data found for UID {card_data['uid']} - no event fired")
                return False
            tag_id = card_data['tag_value']
            print(f"📋 Using NDEF content as payload: {tag_id}")
        
        # Create the tag_scanned event payload
        event_data = {
            'tag_id': tag_id,
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
                print(f"🏠 Fired tag_scanned event with tag_id: {tag_id}")
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
                        print(f"   📋 UID: {card['uid']} (logged only)")
                        print(f"   🎴 Type: {card['type']}")
                        print(f"   📡 Protocol: {card['protocol']}")
                        if 'tag_value' in card and card['tag_value']:
                            print(f"   🏷️  NDEF Tag Value: {card['tag_value']}")
                        else:
                            print(f"   ⚠️  No NDEF data found")
                        
                        # Fire Home Assistant event (only if NDEF data available)
                        self.fire_tag_scanned_event(card)
                        
                        print("   " + "─" * 40)
                        self.last_uid = card['uid']
                else:
                    if self.last_uid:
                        # Card removed
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        print(f"📤 [{timestamp}] Card removed")
                        self.last_uid = None
                
                time.sleep(0.2)
                
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