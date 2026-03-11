#!/usr/bin/env python3
"""
Home Assistant WebSocket connection manager.
Handles auth flow, heartbeat, and reconnection with exponential backoff.
"""

import asyncio
import json
import logging
from enum import Enum, auto

import websockets

logger = logging.getLogger(__name__)


class WSState(Enum):
    DISCONNECTED = auto()
    CONNECTING = auto()
    AUTHENTICATING = auto()
    READY = auto()


class HAWebSocketClient:
    def __init__(
        self,
        host: str,
        port: int,
        token: str,
        heartbeat: int = 30,
        reconnect_max: int = 60,
        on_state_change=None,
    ):
        self.host = host
        self.port = port
        self.token = token
        self.heartbeat = heartbeat
        self.reconnect_max = reconnect_max
        self._on_state_change = on_state_change

        self._ws = None
        self._state = WSState.DISCONNECTED
        self._msg_id = 0
        self._pending: dict = {}
        self._recv_task = None
        self._heartbeat_task = None

    @property
    def state(self) -> WSState:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._state == WSState.READY

    def _set_state(self, new_state: WSState) -> None:
        old = self._state
        self._state = new_state
        if self._on_state_change and old != new_state:
            self._on_state_change(old, new_state)

    def _next_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

    async def connect(self) -> None:
        """Connect, authenticate, and start background recv/heartbeat tasks."""
        url = f"ws://{self.host}:{self.port}/api/websocket"
        self._set_state(WSState.CONNECTING)
        logger.debug("Connecting to %s", url)

        self._ws = await websockets.connect(url)

        self._set_state(WSState.AUTHENTICATING)
        raw = await self._ws.recv()
        msg = json.loads(raw)
        if msg.get("type") != "auth_required":
            raise ValueError(f"Expected auth_required, got {msg}")

        await self._ws.send(json.dumps({"type": "auth", "access_token": self.token}))
        raw = await self._ws.recv()
        msg = json.loads(raw)
        if msg.get("type") != "auth_ok":
            raise PermissionError(f"Authentication failed: {msg}")

        self._set_state(WSState.READY)
        logger.info("Connected and authenticated to Home Assistant WebSocket")

        self._recv_task = asyncio.create_task(self._recv_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def disconnect(self) -> None:
        """Cleanly close the WebSocket and stop background tasks."""
        for task in (self._heartbeat_task, self._recv_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._heartbeat_task = None
        self._recv_task = None

        if self._ws:
            await self._ws.close()
            self._ws = None

        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()
        self._pending.clear()

        self._set_state(WSState.DISCONNECTED)
        logger.info("Disconnected from Home Assistant WebSocket")

    async def send_command(self, msg: dict) -> dict:
        """Send a command and await the matched response by id."""
        msg_id = self._next_id()
        payload = {**msg, "id": msg_id}
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self._pending[msg_id] = fut
        await self._ws.send(json.dumps(payload))
        return await fut

    async def connect_with_retry(self) -> None:
        """Connect with exponential backoff on failure."""
        backoff = 1
        while True:
            try:
                await self.connect()
                return
            except Exception as e:
                logger.warning(
                    "WebSocket connection failed: %s. Retrying in %ds", e, backoff
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self.reconnect_max)

    async def _recv_loop(self) -> None:
        """Receive messages and dispatch to pending futures."""
        try:
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                    msg_id = msg.get("id")
                    if msg_id and msg_id in self._pending:
                        fut = self._pending.pop(msg_id)
                        if not fut.done():
                            fut.set_result(msg)
                except json.JSONDecodeError:
                    logger.debug("Non-JSON message received")
        except (websockets.ConnectionClosed, asyncio.CancelledError):
            pass
        except Exception as e:
            logger.error("Recv loop error: %s", e)

    async def _heartbeat_loop(self) -> None:
        """Send periodic pings to maintain the connection."""
        try:
            while True:
                await asyncio.sleep(self.heartbeat)
                if self._state == WSState.READY:
                    try:
                        await self.send_command({"type": "ping"})
                        logger.debug("Heartbeat ping/pong OK")
                    except Exception as e:
                        logger.warning("Heartbeat failed: %s", e)
        except asyncio.CancelledError:
            pass
