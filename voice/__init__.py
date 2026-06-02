"""
DREX Voice Module

Provides:
  - Listener: Resilient continuous/single-utterance microphone input
  - Speaker: Dual-engine TTS (pyttsx3 offline + edge-tts online)
  - VoiceActivityDetector: Real-time VAD using webrtcvad (optional)
  - WakeWordDetector: Background wake word detection (optional)
"""

from voice.listener import Listener
from voice.speaker import Speaker
from voice.vad import VoiceActivityDetector
from voice.wake_word import WakeWordDetector

__all__ = [
    "Listener",
    "Speaker",
    "VoiceActivityDetector",
    "WakeWordDetector",
]