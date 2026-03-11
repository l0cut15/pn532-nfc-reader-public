#!/usr/bin/env python3
"""
NFC Tag Reader Service - systemd compatible async daemon
Service wrapper for the NFC reader with proper daemon behavior
"""

import asyncio
import logging
import logging.handlers
import os
import signal
import sys
from pathlib import Path

from ha_registration import DeviceRegistrar, VERSION
from ha_tag_scanner import TagScanner
from ha_websocket import HAWebSocketClient, WSState
from nfc_config import get_nfc_config
from nfc_reader_ha_events import NFCReaderHA


class NFCReaderService:
    def __init__(self):
        self.reader = None
        self.running = False
        self._ws_client = None
        self._registrar = None
        self._scanner = None
        self.setup_logging()

    def setup_logging(self):
        """Configure logging for service operation"""
        log_dir = Path('/var/log/nfc-reader')
        log_dir.mkdir(exist_ok=True, parents=True)

        log_file = log_dir / 'nfc-reader.log'
        handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5
        )
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)

        # Configure root logger so ha_websocket / ha_registration / ha_tag_scanner
        # module loggers are all captured by the same handlers.
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        root.addHandler(handler)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root.addHandler(console_handler)

        self.logger = logging.getLogger('nfc-reader-service')

    def stop(self):
        """Signal the service to stop."""
        self.logger.info("Shutdown signal received, stopping...")
        self.running = False

    def _on_ws_state_change(self, old: WSState, new: WSState) -> None:
        """Callback fired when WS state changes; replay queued scans on reconnect."""
        self.logger.debug("WS state: %s → %s", old.name, new.name)
        if new == WSState.READY and self._scanner:
            asyncio.ensure_future(self._scanner.replay_queue())

    async def start(self) -> bool:
        """Start the NFC reader service."""
        self.logger.info("Starting NFC Reader Service v%s...", VERSION)
        config = get_nfc_config()
        ws_enabled = config.get('websocket.enabled', True)

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self.stop)

        try:
            self.reader = NFCReaderHA()
            connected = await asyncio.to_thread(self.reader.connect_serial)
            if not connected:
                self.logger.error("Failed to connect to NFC reader")
                return False

            if ws_enabled:
                await self._start_ws(config)
            else:
                ok = await asyncio.to_thread(self.reader.test_ha_connection)
                if not ok:
                    self.logger.error("Failed to connect to Home Assistant API")
                    return False

            self.logger.info("NFC Reader Service started successfully")
            self.running = True
            await self.monitor_loop()

        except Exception as e:
            self.logger.error("Failed to start service: %s", e)
            return False
        finally:
            if self._ws_client:
                await self._ws_client.disconnect()
            if self.reader:
                self.reader.disconnect()
                self.reader = None

        return True

    async def _start_ws(self, config) -> None:
        """Initialize WS client, registrar, and scanner; connect to HA."""
        ha_host = config.get('home_assistant.host')
        ha_port = config.get('home_assistant.port', 8123)
        ha_token = config.get('home_assistant.token')
        device_name = config.get('device.name', 'PN532 NFC Reader')
        heartbeat = config.get('websocket.heartbeat', 30)
        reconnect_max = config.get('websocket.reconnect_max', 60)
        queue_max = config.get('scan.queue_max', 50)
        stale_seconds = config.get('scan.stale_seconds', 300)

        self._ws_client = HAWebSocketClient(
            ha_host, ha_port, ha_token,
            heartbeat=heartbeat,
            reconnect_max=reconnect_max,
            on_state_change=self._on_ws_state_change,
        )
        self._registrar = DeviceRegistrar(
            ha_host, ha_port, ha_token, device_name=device_name
        )
        self._scanner = TagScanner(
            self._ws_client, self._registrar,
            queue_max=queue_max,
            stale_seconds=stale_seconds,
        )

        await self._registrar.ensure_registered()
        await self._ws_client.connect_with_retry()

    async def monitor_loop(self) -> None:
        """Main async monitoring loop; NFC I/O runs in a thread."""
        self.logger.info("Starting NFC card monitoring...")
        last_uid = None
        ws_enabled = self._scanner is not None

        try:
            while self.running:
                try:
                    card = await asyncio.to_thread(self.reader.scan_for_card)

                    if card:
                        if card['uid'] != last_uid:
                            log_msg = (
                                f"NFC Card detected - UID: {card['uid']} (logged only), "
                                f"Type: {card['type']}"
                            )
                            if card.get('tag_value'):
                                log_msg += f", NDEF Value: {card['tag_value']}"
                            self.logger.info(log_msg)

                            if ws_enabled:
                                if card.get('tag_value'):
                                    ok = await self._scanner.scan_tag(card['tag_value'])
                                    if not ok:
                                        self.logger.warning(
                                            "WS scan failed for tag: %s", card['tag_value']
                                        )
                                else:
                                    self.logger.info(
                                        "No NDEF data for UID %s — no event fired",
                                        card['uid'],
                                    )
                            else:
                                fired = await asyncio.to_thread(
                                    self.reader.fire_tag_scanned_event, card
                                )
                                if fired:
                                    self.logger.info(
                                        "Fired tag_scanned event: %s", card.get('tag_value')
                                    )
                                elif not card.get('tag_value'):
                                    self.logger.info(
                                        "No NDEF data for UID %s — no event fired",
                                        card['uid'],
                                    )
                                else:
                                    self.logger.warning(
                                        "Failed to fire tag_scanned event for: %s",
                                        card.get('tag_value'),
                                    )

                            last_uid = card['uid']
                    else:
                        if last_uid:
                            self.logger.debug("Card removed")
                            last_uid = None

                    await asyncio.sleep(0.5)

                except Exception as e:
                    self.logger.error("Error in monitoring loop: %s", e)
                    await asyncio.sleep(5)

        except Exception as e:
            self.logger.error("Fatal error in monitor loop: %s", e)
            self.running = False

    def health_check(self) -> bool:
        """Synchronous health check for Docker/systemd probes."""
        if not self.running:
            return False
        if not self.reader or not self.reader.serial:
            return False
        try:
            return self.reader.test_ha_connection()
        except Exception:
            return False


async def async_main() -> int:
    """Async service entry point."""
    if os.geteuid() != 0:
        print("Warning: Service typically runs as root for device access")

    service = NFCReaderService()

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command == 'start':
            return 0 if await service.start() else 1
        elif command == 'health':
            return 0 if service.health_check() else 1
        else:
            print(f"Usage: {sys.argv[0]} [start|health]")
            return 1
    else:
        return 0 if await service.start() else 1


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    sys.exit(main())
