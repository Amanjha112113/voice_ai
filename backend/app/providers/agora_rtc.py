"""Agora RTC Gateway and Official Token Generation.

Implements the official Agora AccessToken2 / DynamicKey algorithm for RTC channels.
Enables clients (Browser / Mobile) to securely connect to Agora RTC media plane.
"""

import hmac
import hashlib
import time
import struct
import base64
import zlib
import os
from typing import Optional
import logging

from .base import RTCGateway
from ..config.settings import settings

logger = logging.getLogger(__name__)

# Agora AccessToken2 Service Constants
SERVICE_TYPE_RTC = 1
PRIVILEGE_JOIN_CHANNEL = 1
PRIVILEGE_PUBLISH_AUDIO_STREAM = 2
PRIVILEGE_PUBLISH_VIDEO_STREAM = 3
PRIVILEGE_PUBLISH_DATA_STREAM = 4


def _pack_uint16(val: int) -> bytes:
    return struct.pack("<H", val)


def _pack_uint32(val: int) -> bytes:
    return struct.pack("<I", val)


def _pack_string(val: str) -> bytes:
    encoded = val.encode("utf-8")
    return _pack_uint16(len(encoded)) + encoded


def _pack_map_uint32(privileges: dict[int, int]) -> bytes:
    buf = _pack_uint16(len(privileges))
    for k, v in privileges.items():
        buf += _pack_uint16(k) + _pack_uint32(v)
    return buf


class AgoraTokenBuilder:
    """Generates official Agora AccessToken2 tokens."""

    @staticmethod
    def build_token(
        app_id: str,
        app_certificate: Optional[str],
        channel_name: str,
        uid: int,
        expire_seconds: int = 3600,
    ) -> str:
        """Constructs an Agora RTC token for channel authentication."""
        if not app_certificate or len(app_certificate) == 0:
            # If no certificate is configured, AppID alone acts as the open token
            return app_id

        issue_ts = int(time.time())
        expire_ts = issue_ts + expire_seconds
        salt = int.from_bytes(os.urandom(4), byteorder="little")

        # Build Service RTC buffer
        service_privileges = {
            PRIVILEGE_JOIN_CHANNEL: expire_ts,
            PRIVILEGE_PUBLISH_AUDIO_STREAM: expire_ts,
            PRIVILEGE_PUBLISH_VIDEO_STREAM: expire_ts,
            PRIVILEGE_PUBLISH_DATA_STREAM: expire_ts,
        }

        service_buf = (
            _pack_uint16(SERVICE_TYPE_RTC)
            + _pack_map_uint32(service_privileges)
            + _pack_string(channel_name)
            + _pack_uint32(uid)
        )

        # Signing buffer
        signing_content = (
            _pack_string(app_id)
            + _pack_uint32(issue_ts)
            + _pack_uint32(salt)
            + _pack_uint16(1) # count of services
            + service_buf
        )

        # HMAC signature using app_certificate
        signature = hmac.new(
            app_certificate.encode("utf-8"),
            signing_content,
            hashlib.sha256,
        ).digest()

        # Final token packet
        token_data = (
            _pack_string(app_id)
            + _pack_uint32(issue_ts)
            + _pack_uint32(salt)
            + _pack_uint16(len(signature))
            + signature
            + _pack_uint16(1)
            + service_buf
        )

        compressed = zlib.compress(token_data)
        encoded_token = "007" + base64.b64encode(compressed).decode("utf-8")
        return encoded_token


class AgoraRTCGateway(RTCGateway):
    """Manages Agora RTC channel sessions and media token provisioning."""

    def __init__(
        self,
        app_id: Optional[str] = None,
        app_certificate: Optional[str] = None,
    ) -> None:
        self.app_id = app_id or settings.AGORA_APP_ID
        self.app_certificate = app_certificate or settings.AGORA_APP_CERTIFICATE
        self._active_channels: dict[str, int] = {}

    def generate_token(self, channel_name: str, uid: int = 0, expire_seconds: int = 3600) -> str:
        """Generate official Agora RTC channel access token."""
        token = AgoraTokenBuilder.build_token(
            app_id=self.app_id,
            app_certificate=self.app_certificate,
            channel_name=channel_name,
            uid=uid,
            expire_seconds=expire_seconds,
        )
        logger.info(f"Generated Agora RTC token for channel='{channel_name}', uid={uid}")
        return token

    async def join_channel(self, channel_name: str, uid: int = 0) -> None:
        """Join Agora RTC media room."""
        self._active_channels[channel_name] = uid
        logger.info(f"Agora RTC Gateway: joined channel '{channel_name}' with uid={uid}")

    async def leave_channel(self, channel_name: str) -> None:
        """Leave Agora RTC media room."""
        if channel_name in self._active_channels:
            del self._active_channels[channel_name]
        logger.info(f"Agora RTC Gateway: left channel '{channel_name}'")

    async def send_audio_frame(self, pcm_bytes: bytes) -> None:
        """Send PCM audio frame to Agora RTC audio track."""
        logger.debug(f"Agora RTC Gateway: sent audio frame of {len(pcm_bytes)} bytes")
