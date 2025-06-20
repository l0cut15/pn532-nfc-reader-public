#!/usr/bin/env python3
"""
NFC Tag Reader Service - systemd compatible daemon
Service wrapper for the NFC reader with proper daemon behavior
Version 2.2 - Configurable NDEF/UUID payload delivery
"""

__version__ = "2.2"

import sys
import signal
import logging
import logging.handlers
import time
import os
from pathlib import Path
from nfc_reader_ha_events import NFCReaderHA


class NFCReaderService:
    def __init__(self):
        self.reader = None
        self.running = False
        self.setup_logging()
        self.setup_signal_handlers()
        
    def setup_logging(self):
        """Configure logging for service operation"""
        # Create logs directory if it doesn't exist
        log_dir = Path('/var/log/nfc-reader')
        log_dir.mkdir(exist_ok=True, parents=True)
        
        # Setup rotating file handler
        log_file = log_dir / 'nfc-reader.log'
        handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=5
        )
        
        # Setup formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        
        # Configure logger
        self.logger = logging.getLogger('nfc-reader-service')
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(handler)
        
        # Also log to stdout for systemd journal
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        signal_names = {signal.SIGTERM: 'SIGTERM', signal.SIGINT: 'SIGINT'}
        self.logger.info(f"Received {signal_names.get(signum, signum)}, initiating shutdown...")
        self.stop()
        
    def start(self):
        """Start the NFC reader service"""
        self.logger.info("Starting NFC Reader Service...")
        
        try:
            # Initialize the NFC reader
            self.reader = NFCReaderHA()
            
            # Test Home Assistant connection
            if not self.reader.test_ha_connection():
                self.logger.error("Failed to connect to Home Assistant API")
                return False
            
            # Connect to NFC reader
            if not self.reader.connect_serial():
                self.logger.error("Failed to connect to NFC reader")
                return False
                
            self.logger.info("NFC Reader Service started successfully")
            self.running = True
            
            # Start monitoring loop
            self.monitor_loop()
            
        except Exception as e:
            self.logger.error(f"Failed to start service: {e}")
            return False
            
        return True
        
    def stop(self):
        """Stop the NFC reader service"""
        self.logger.info("Stopping NFC Reader Service...")
        self.running = False
        
        if self.reader:
            self.reader.disconnect()
            self.reader = None
            
        self.logger.info("NFC Reader Service stopped")
        
    def monitor_loop(self):
        """Main monitoring loop with service-appropriate behavior"""
        self.logger.info("Starting NFC card monitoring...")
        last_uid = None
        
        try:
            while self.running:
                try:
                    card = self.reader.scan_for_card()
                    
                    if card:
                        if card['uid'] != last_uid:
                            # New card detected
                            log_msg = f"NFC Card detected - UID: {card['uid']} (logged only), Type: {card['type']}"
                            if 'tag_value' in card and card['tag_value']:
                                log_msg += f", NDEF Value: {card['tag_value']}"
                            self.logger.info(log_msg)
                            
                            # Fire Home Assistant event (only if NDEF data available)
                            if self.reader.fire_tag_scanned_event(card):
                                self.logger.info(f"Successfully fired tag_scanned event with tag_id: {card['tag_value']}")
                            else:
                                if 'tag_value' not in card or not card['tag_value']:
                                    self.logger.info(f"No NDEF data found for UID {card['uid']} - no event fired")
                                else:
                                    self.logger.warning(f"Failed to fire tag_scanned event for NDEF value: {card['tag_value']}")
                            
                            last_uid = card['uid']
                    else:
                        if last_uid:
                            # Card removed
                            self.logger.debug("Card removed")
                            last_uid = None
                    
                    time.sleep(0.5)
                    
                except Exception as e:
                    self.logger.error(f"Error in monitoring loop: {e}")
                    # Brief pause before retrying
                    time.sleep(5)
                    
        except Exception as e:
            self.logger.error(f"Fatal error in monitor loop: {e}")
            self.running = False
            
    def health_check(self):
        """Perform health check for service monitoring"""
        if not self.running:
            return False
            
        if not self.reader or not self.reader.serial:
            return False
            
        # Test HA connection
        try:
            return self.reader.test_ha_connection()
        except Exception:
            return False


def main():
    """Main service entry point"""
    # Check if running as root/service user
    if os.geteuid() != 0:
        print("Warning: Service typically runs as root for device access")
    
    service = NFCReaderService()
    
    # Handle command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'start':
            return 0 if service.start() else 1
        elif command == 'health':
            return 0 if service.health_check() else 1
        else:
            print(f"Usage: {sys.argv[0]} [start|health]")
            return 1
    else:
        # Default behavior - start service
        return 0 if service.start() else 1


if __name__ == "__main__":
    sys.exit(main())