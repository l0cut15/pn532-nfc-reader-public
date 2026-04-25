#!/usr/bin/env python3
"""
Home Assistant mobile_app device registration.
Persists webhook_id to disk so registration survives restarts.
"""

import json
import logging
import platform
import uuid
from pathlib import Path

import aiohttp

logger = logging.getLogger(__name__)

VERSION = "3.0.2"
_REGISTRATION_FILE = ".nfc_reader_registration.json"


class DeviceRegistrar:
    def __init__(
        self,
        ha_host: str,
        ha_port: int,
        token: str,
        device_name: str = "PN532 NFC Reader",
        registration_file: str = _REGISTRATION_FILE,
    ):
        self._url = f"http://{ha_host}:{ha_port}"
        self._token = token
        self._device_name = device_name
        self._reg_path = Path(registration_file)
        self._webhook_id: str | None = None
        self._device_id: str | None = None

    @property
    def webhook_id(self) -> str | None:
        return self._webhook_id

    async def ensure_registered(self) -> str:
        """Return webhook_id, registering with HA if not already done."""
        if self._reg_path.exists():
            try:
                data = json.loads(self._reg_path.read_text())
                wid = data.get("webhook_id")
                did = data.get("device_id")
                if wid:
                    self._webhook_id = wid
                    self._device_id = did
                    logger.debug("Loaded existing registration from disk")
                    return wid
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(
                    "Failed to read registration file: %s — re-registering", e
                )
        return await self._register()

    async def re_register(self) -> str:
        """Delete stored registration and re-register with HA."""
        if self._reg_path.exists():
            self._reg_path.unlink()
        self._webhook_id = None
        self._device_id = None
        return await self._register()

    async def _register(self) -> str:
        device_id = str(uuid.uuid4())
        payload = {
            "device_id": device_id,
            "app_id": "pn532-nfc-reader",
            "app_name": "PN532 NFC Reader",
            "app_version": VERSION,
            "device_name": self._device_name,
            "manufacturer": "PN532",
            "model": "USB NFC Reader",
            "os_name": "Linux",
            "os_version": platform.release(),
            "supports_encryption": False,
        }
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        url = f"{self._url}/api/mobile_app/registrations"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                data = await resp.json()

        webhook_id = data["webhook_id"]
        self._webhook_id = webhook_id
        self._device_id = device_id
        self._reg_path.write_text(
            json.dumps({"webhook_id": webhook_id, "device_id": device_id})
        )
        logger.info("Registered with Home Assistant as '%s'", self._device_name)
        logger.debug("Stored webhook_id (omitted from INFO log for security)")
        return webhook_id
