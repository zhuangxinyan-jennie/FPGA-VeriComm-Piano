# -*- coding: utf-8 -*-
# pygame: local MIDI preview OR single voice driven by FPGA frequency (Hz).

from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pygame

from core.notes import midi_to_freq


class AudioEngine:
    def __init__(self, sample_rate: int = 44100, buffer: int = 256) -> None:
        self._sr = sample_rate
        if not pygame.mixer.get_init():
            pygame.mixer.pre_init(self._sr, size=-16, channels=2, buffer=buffer)
            pygame.mixer.init()
        n = pygame.mixer.get_num_channels()
        if n < 16:
            pygame.mixer.set_num_channels(16)
        self._midi_channel: Dict[int, pygame.mixer.Channel] = {}
        self._sounds: Dict[int, pygame.mixer.Sound] = {}
        self._hz_sound_cache: Dict[int, pygame.mixer.Sound] = {}
        self._fpga_channel: Optional[pygame.mixer.Channel] = None

    def _ensure_sound_midi(self, midi: int) -> pygame.mixer.Sound:
        if midi in self._sounds:
            return self._sounds[midi]
        freq = midi_to_freq(midi)
        snd = self._make_loop_sound_hz(freq)
        self._sounds[midi] = snd
        return snd

    def _make_loop_sound_hz(self, freq: float) -> pygame.mixer.Sound:
        duration = 0.25
        n_samples = int(self._sr * duration)
        t = np.linspace(0.0, duration, n_samples, dtype=np.float64)
        mono = (np.sin(2 * np.pi * freq * t) * 0.25 * 32767).astype(np.int16)
        stereo = np.column_stack((mono, mono))
        return pygame.sndarray.make_sound(stereo)

    def _ensure_sound_hz(self, hz: float) -> pygame.mixer.Sound:
        key = int(round(hz))
        if key in self._hz_sound_cache:
            return self._hz_sound_cache[key]
        if len(self._hz_sound_cache) > 64:
            self._hz_sound_cache.clear()
        snd = self._make_loop_sound_hz(float(key))
        self._hz_sound_cache[key] = snd
        return snd

    def play_freq_hz(self, hz: float) -> None:
        """Speaker voice driven by FPGA FREQ (single main tone)."""
        self.stop_fpga_voice()
        if hz <= 0:
            return
        ch = pygame.mixer.find_channel(True)
        if ch is None:
            return
        snd = self._ensure_sound_hz(hz)
        ch.play(snd, loops=-1)
        self._fpga_channel = ch

    def stop_fpga_voice(self) -> None:
        if self._fpga_channel is not None:
            self._fpga_channel.stop()
            self._fpga_channel = None

    def note_on(self, midi: int) -> None:
        """Local-only preview when serial is offline."""
        if midi in self._midi_channel:
            return
        ch = pygame.mixer.find_channel(True)
        if ch is None:
            return
        snd = self._ensure_sound_midi(midi)
        ch.play(snd, loops=-1)
        self._midi_channel[midi] = ch

    def note_off(self, midi: int) -> None:
        ch = self._midi_channel.pop(midi, None)
        if ch is not None:
            ch.stop()

    def all_off(self) -> None:
        self.stop_fpga_voice()
        for ch in self._midi_channel.values():
            ch.stop()
        self._midi_channel.clear()
