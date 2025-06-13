#!/usr/bin/env python3
"""
Docker environment-based configuration loader
Replaces config.yaml with environment variables for security
"""

import os
from typing import Any, Optional


class DockerNFCConfig:
    """Configuration loader that uses environment variables instead of config.yaml"""
    
    def __init__(self):
        self._config = self._load_from_env()
    
    def _load_from_env(self) -> dict:
        """Load configuration from environment variables"""
        return {
            'home_assistant': {
                'host': os.getenv('HA_HOST', 'host.docker.internal'),
                'port': int(os.getenv('HA_PORT', '8123')),
                'token': os.getenv('HA_TOKEN', '')
            },
            'nfc_reader': {
                'auto_detect': os.getenv('NFC_AUTO_DETECT', 'false').lower() == 'true',
                'baudrate': int(os.getenv('NFC_BAUDRATE', '115200')),
                'location': os.getenv('NFC_LOCATION', 'Docker Container'),
                'port': os.getenv('NFC_PORT', '/dev/ttyUSB0'),
                'reader_id': os.getenv('NFC_READER_ID', 'nfc_reader_docker'),
                'reader_name': os.getenv('NFC_READER_NAME', 'Docker NFC Reader'),
                'timeout': float(os.getenv('NFC_TIMEOUT', '1.0'))
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation (e.g., 'home_assistant.host')"""
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_device_port(self) -> Optional[str]:
        """Get the NFC device port, with auto-detection disabled in Docker"""
        if self.get('nfc_reader.auto_detect', False):
            # Auto-detection is disabled in Docker for predictable device paths
            print("⚠️  Auto-detection disabled in Docker environment")
            
        return self.get('nfc_reader.port')


def get_nfc_config():
    """Factory function to get configuration - Docker version"""
    return DockerNFCConfig()