"""Voice channel — speech-to-text + text-to-speech for conversational AI."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any

import structlog

from hauba.exceptions import HaubaError

logger = structlog.get_logger()

try:
    import sounddevice  # type: ignore[import-untyped]

    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False

try:
    import edge_tts  # type: ignore[import-untyped]

    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False


class VoiceChannelError(HaubaError):
    """Voice channel error."""


class VoiceChannel:
    """Voice input/output channel using Whisper STT and edge-tts TTS.

    Supports:
    - Push-to-talk recording via sounddevice
    - Speech-to-text via OpenAI Whisper (local)
    - Text-to-speech via edge-tts (offline-capable)
    - Audio streaming for real-time responses
    """

    def __init__(
        self,
        stt_model: str = "base",
        tts_voice: str = "en-US-AriaNeural",
        sample_rate: int = 16000,
    ) -> None:
        self.stt_model = stt_model
        self.tts_voice = tts_voice
        self.sample_rate = sample_rate
        self._whisper_model: Any = None
        self._recording = False

    async def initialize(self) -> None:
        """Load the Whisper model (lazy initialization)."""
        if self._whisper_model is not None:
            return

        try:
            import whisper  # type: ignore[import-untyped]

            self._whisper_model = whisper.load_model(self.stt_model)
            logger.info("voice.whisper_loaded", model=self.stt_model)
        except ImportError:
            raise VoiceChannelError(
                "openai-whisper not installed. Run: pip install hauba[voice]"
            )

    async def listen(self, duration: float = 5.0) -> str:
        """Record audio and transcribe to text.

        Args:
            duration: Recording duration in seconds.

        Returns:
            Transcribed text from the audio recording.
        """
        if not SOUNDDEVICE_AVAILABLE:
            raise VoiceChannelError(
                "sounddevice not installed. Run: pip install hauba[voice]"
            )

        await self.initialize()

        logger.info("voice.recording_start", duration=duration)
        self._recording = True

        # Record audio in a thread to avoid blocking the event loop
        audio_data = await asyncio.to_thread(
            sounddevice.rec,
            int(duration * self.sample_rate),
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
        )
        await asyncio.to_thread(sounddevice.wait)
        self._recording = False
        logger.info("voice.recording_done")

        # Save to temp file for Whisper
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            import numpy as np
            import scipy.io.wavfile as wav  # type: ignore[import-untyped]

            wav.write(tmp_path, self.sample_rate, (audio_data * 32767).astype(np.int16))

            # Transcribe
            result = await asyncio.to_thread(
                self._whisper_model.transcribe, tmp_path, language="en"
            )
            text = result.get("text", "").strip()
            logger.info("voice.transcribed", text=text[:100])
            return text
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    async def speak(self, text: str, output_path: str | None = None) -> str:
        """Convert text to speech and play it.

        Args:
            text: Text to speak.
            output_path: Optional path to save the audio file.

        Returns:
            Path to the generated audio file.
        """
        if not EDGE_TTS_AVAILABLE:
            raise VoiceChannelError(
                "edge-tts not installed. Run: pip install hauba[voice]"
            )

        if not output_path:
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            output_path = tmp.name
            tmp.close()

        communicate = edge_tts.Communicate(text, self.tts_voice)
        await communicate.save(output_path)
        logger.info("voice.tts_saved", path=output_path, length=len(text))

        # Play audio if sounddevice is available
        if SOUNDDEVICE_AVAILABLE:
            await self._play_audio(output_path)

        return output_path

    async def _play_audio(self, path: str) -> None:
        """Play an audio file via sounddevice."""
        try:
            import soundfile as sf  # type: ignore[import-untyped]

            data, samplerate = await asyncio.to_thread(sf.read, path)
            await asyncio.to_thread(sounddevice.play, data, samplerate)
            await asyncio.to_thread(sounddevice.wait)
        except ImportError:
            logger.warning("voice.soundfile_missing", msg="Cannot play audio — soundfile not installed")
        except Exception as exc:
            logger.error("voice.play_failed", error=str(exc))

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def is_available(self) -> bool:
        """Check if voice dependencies are available."""
        return SOUNDDEVICE_AVAILABLE and EDGE_TTS_AVAILABLE
