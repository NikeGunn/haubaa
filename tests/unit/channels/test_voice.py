"""Tests for VoiceChannel — speech-to-text + text-to-speech."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hauba.channels.voice import VoiceChannel, VoiceChannelError


@pytest.fixture
def voice() -> VoiceChannel:
    return VoiceChannel(stt_model="base", tts_voice="en-US-AriaNeural")


# --- Initialization ---


def test_voice_channel_defaults(voice: VoiceChannel) -> None:
    assert voice.stt_model == "base"
    assert voice.tts_voice == "en-US-AriaNeural"
    assert voice.sample_rate == 16000
    assert not voice.is_recording


def test_voice_channel_custom_params() -> None:
    vc = VoiceChannel(stt_model="small", tts_voice="en-GB-RyanNeural", sample_rate=22050)
    assert vc.stt_model == "small"
    assert vc.tts_voice == "en-GB-RyanNeural"
    assert vc.sample_rate == 22050


# --- Availability ---


def test_is_available_false_when_deps_missing(voice: VoiceChannel) -> None:
    with patch("hauba.channels.voice.SOUNDDEVICE_AVAILABLE", False), \
         patch("hauba.channels.voice.EDGE_TTS_AVAILABLE", False):
        assert not voice.is_available


def test_is_available_true_when_deps_present(voice: VoiceChannel) -> None:
    with patch("hauba.channels.voice.SOUNDDEVICE_AVAILABLE", True), \
         patch("hauba.channels.voice.EDGE_TTS_AVAILABLE", True):
        assert voice.is_available


# --- Listen ---


async def test_listen_requires_sounddevice(voice: VoiceChannel) -> None:
    with patch("hauba.channels.voice.SOUNDDEVICE_AVAILABLE", False):
        with pytest.raises(VoiceChannelError, match="sounddevice not installed"):
            await voice.listen()


async def test_listen_requires_whisper_init(voice: VoiceChannel) -> None:
    with patch("hauba.channels.voice.SOUNDDEVICE_AVAILABLE", True):
        with pytest.raises(VoiceChannelError, match="openai-whisper not installed"):
            await voice.listen()


# --- Speak ---


async def test_speak_requires_edge_tts(voice: VoiceChannel) -> None:
    with patch("hauba.channels.voice.EDGE_TTS_AVAILABLE", False):
        with pytest.raises(VoiceChannelError, match="edge-tts not installed"):
            await voice.speak("hello")


async def test_speak_with_mocked_tts(voice: VoiceChannel, tmp_path) -> None:
    out_path = str(tmp_path / "test.mp3")
    mock_communicate = AsyncMock()
    mock_communicate.save = AsyncMock()

    with patch("hauba.channels.voice.EDGE_TTS_AVAILABLE", True), \
         patch("hauba.channels.voice.SOUNDDEVICE_AVAILABLE", False), \
         patch("hauba.channels.voice.edge_tts", create=True) as mock_tts:
        mock_tts.Communicate = MagicMock(return_value=mock_communicate)
        result = await voice.speak("hello world", output_path=out_path)
        assert result == out_path
        mock_tts.Communicate.assert_called_once_with("hello world", "en-US-AriaNeural")
        mock_communicate.save.assert_called_once_with(out_path)
