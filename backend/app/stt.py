"""ElevenLabs batch speech-to-text for raw 16 kHz s16le mono PCM."""
import io
import logging
import wave
from array import array

import httpx

from .config import env

log = logging.getLogger("footnote.stt")
URL = "https://api.elevenlabs.io/v1/speech-to-text"
SAMPLE_RATE = 16000

_client: httpx.AsyncClient | None = None


class SttError(RuntimeError):
    pass


def pcm_to_wav(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    return buf.getvalue()


def peak(pcm: bytes) -> int:
    """Loudest sample (0-32768). Used to skip silent chunks."""
    samples = array("h")
    samples.frombytes(pcm[: len(pcm) // 2 * 2])
    return max((abs(s) for s in samples), default=0)


def is_silent(pcm: bytes) -> bool:
    return peak(pcm) < int(env("SILENCE_PEAK", "1"))


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=4.5)
    return _client


async def warm_up() -> None:
    """Open the TLS connection ahead of the first real request (best effort)."""
    try:
        await _http().get("https://api.elevenlabs.io/")
    except httpx.HTTPError:
        pass


async def transcribe(pcm: bytes) -> str:
    key = env("ELEVENLABS_API_KEY")
    if not key:
        raise SttError("ELEVENLABS_API_KEY is not set")
    http = _http()
    data = {"model_id": env("ELEVENLABS_STT_MODEL", "scribe_v1"), "language_code": "en",
            "tag_audio_events": "false", "timestamps_granularity": "none"}
    try:
        r = await http.post(URL, headers={"xi-api-key": key}, data=data,
                            files={"file": ("chunk.wav", pcm_to_wav(pcm), "audio/wav")})
    except httpx.HTTPError as e:
        raise SttError(f"ElevenLabs request failed: {type(e).__name__}") from e
    if r.status_code != 200:
        log.warning("ElevenLabs STT HTTP %s: %s", r.status_code, r.text[:200])
        raise SttError(f"ElevenLabs returned HTTP {r.status_code}")
    try:
        text = r.json().get("text")
    except (ValueError, AttributeError) as e:
        raise SttError("ElevenLabs returned an invalid response") from e
    if not isinstance(text, str):
        raise SttError("ElevenLabs returned an invalid transcript")
    return text.strip()
