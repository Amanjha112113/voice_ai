"""TTS Streaming API Routes for EchoDrive Control Plane."""

import asyncio
from fastapi import APIRouter, Query, Response, HTTPException
from fastapi.responses import StreamingResponse
import aiohttp
import logging
from typing import Optional

from ..config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tts", tags=["TTS"])


@router.get("/synthesize")
async def synthesize_speech(
    text: str = Query(..., description="Text to synthesize"),
    voice_id: Optional[str] = Query(default=None, description="Optional voice ID override"),
):
    """Synthesize text into real streaming MP3 audio using ElevenLabs or Deepgram Aura."""
    if not text.strip():
        raise HTTPException(status_code=400, detail="Empty text provided")

    # 1. Try ElevenLabs if configured
    eleven_key = settings.ELEVENLABS_API_KEY
    target_voice_id = voice_id or settings.ELEVENLABS_VOICE_ID or "oO7sLA3dWfQXsKeSAjpA"

    if eleven_key and not eleven_key.startswith("your_") and target_voice_id:
        try:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{target_voice_id}/stream?output_format=mp3_44100_128"
            headers = {
                "xi-api-key": eleven_key,
                "Content-Type": "application/json",
            }
            payload = {
                "text": text,
                "model_id": "eleven_flash_v2_5",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            }

            timeout = aiohttp.ClientTimeout(total=4.0, connect=1.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        audio_data = await resp.read()
                        return Response(content=audio_data, media_type="audio/mpeg")
                    else:
                        err_text = await resp.text()
                        logger.warning(f"ElevenLabs synthesis note ({resp.status}): {err_text[:100]}... Trying Deepgram Aura.")
        except Exception as e:
            logger.warning(f"ElevenLabs synthesis error: {e}. Trying Deepgram Aura.")

    # 2. Fallback to Deepgram Aura neural voice (Asteria / Luna)
    deepgram_key = settings.DEEPGRAM_API_KEY
    if deepgram_key and not deepgram_key.startswith("your_"):
        try:
            url = "https://api.deepgram.com/v1/speak?model=aura-asteria-en"
            headers = {
                "Authorization": f"Token {deepgram_key}",
                "Content-Type": "application/json",
            }
            payload = {"text": text}

            timeout = aiohttp.ClientTimeout(total=4.0, connect=1.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        audio_data = await resp.read()
                        return Response(content=audio_data, media_type="audio/mpeg")
        except Exception as e:
            logger.warning(f"Deepgram Aura synthesis error: {e}")

    raise HTTPException(status_code=500, detail="TTS synthesis failed across available neural providers")
