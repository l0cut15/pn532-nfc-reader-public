#!/usr/bin/env python3
"""
Tag scanner: dispatches NFC tag scans to HA via WebSocket webhook/handle messages.
Queues scans when disconnected; replays on reconnection, discarding stale entries.
"""

import collections
import json
import logging
import time

from ha_websocket import HAWebSocketClient

logger = logging.getLogger(__name__)


class TagScanner:
    def __init__(
        self,
        ws_client: HAWebSocketClient,
        registrar,
        queue_max: int = 50,
        stale_seconds: int = 300,
    ):
        self._ws = ws_client
        self._registrar = registrar
        self._queue: collections.deque = collections.deque(maxlen=queue_max)
        self._stale_seconds = stale_seconds

    async def scan_tag(self, tag_id: str) -> bool:
        """Send a scan_tag webhook or enqueue if WS is not ready."""
        if self._ws.is_connected:
            return await self._send_scan(tag_id)
        logger.debug("WS not ready — queuing scan for tag '%s'", tag_id)
        self._queue.append((tag_id, time.monotonic()))
        return False

    async def replay_queue(self) -> None:
        """Replay queued scans, discarding entries older than stale_seconds."""
        if not self._queue:
            return
        now = time.monotonic()
        fresh = [
            (tag_id, ts)
            for tag_id, ts in self._queue
            if now - ts <= self._stale_seconds
        ]
        stale = len(self._queue) - len(fresh)
        self._queue.clear()
        if stale:
            logger.debug("Discarded %d stale queued scan(s)", stale)
        if not fresh:
            return
        logger.info("Replaying %d queued scan(s)", len(fresh))
        for tag_id, _ in fresh:
            await self._send_scan(tag_id)

    async def _send_scan(self, tag_id: str) -> bool:
        webhook_id = self._registrar.webhook_id
        if not webhook_id:
            logger.warning(
                "No webhook_id available, cannot send scan for '%s'", tag_id
            )
            return False

        body = json.dumps({"type": "scan_tag", "data": {"tag_id": tag_id}})
        msg = {
            "type": "webhook/handle",
            "webhook_id": webhook_id,
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": body,
        }
        try:
            result = await self._ws.send_command(msg)
            status = result.get("result", {}).get("status")
            if status == 410:
                logger.warning("Webhook returned 410, re-registering and retrying...")
                await self._registrar.re_register()
                return await self._send_scan(tag_id)
            if status == 200:
                logger.info("Tag scanned: %s", tag_id)
                return True
            logger.warning(
                "Tag scan returned unexpected status %s for '%s'", status, tag_id
            )
            return False
        except Exception as e:
            logger.warning("Error sending tag scan for '%s': %s", tag_id, e)
            return False
