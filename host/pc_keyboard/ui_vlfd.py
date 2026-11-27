# -*- coding: utf-8 -*-
"""Tk UI: same keyboard layout as electronic_keyboard, FIFO instead of serial."""

from __future__ import annotations

import sys
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk
import tkinter as tk
from typing import Optional, Set

import pygame

# zxy/electronic_keyboard for audio + core + widgets
_ZXY = Path(__file__).resolve().parent.parent.parent
_EK = _ZXY / "electronic_keyboard"
if str(_EK) not in sys.path:
    sys.path.insert(0, str(_EK))

from audio.engine import AudioEngine
from core.events import EventKind
from core.notes import KeyBinding, binding_map_by_key_id, build_default_octave_bindings, midi_to_name
from core.recorder import PerformanceRecorder
from widgets.led_strip import LedStripCanvas
from widgets.piano_keys import PianoKeysCanvas

from .vlfd_manager import VlfdFifoManager


def _event_key_id(event: tk.Event) -> Optional[str]:
    ch = getattr(event, "char", "") or ""
    if ch and ch.isalpha():
        return ch.lower()
    ks = (getattr(event, "keysym", "") or "").lower()
    if len(ks) == 1 and ks.isalpha():
        return ks
    return None


def _focus_is_text_entry(widget: Optional[tk.Misc]) -> bool:
    """True if focus is in a text field so we do not steal A/S/D as piano keys."""
    if widget is None:
        return False
    cls = widget.winfo_class()
    return cls in ("Entry", "TEntry", "Text")


class VlfdMainWindow:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Piano VLFD - FIFO / VeriComm (PC keyboard)")
        self.root.minsize(640, 520)
        self.root.geometry("920x640")

        self._octave = 4
        self._bindings: list[KeyBinding] = build_default_octave_bindings(self._octave)
        self._by_key: dict[str, KeyBinding] = binding_map_by_key_id(self._bindings)

        self._pressed: Set[int] = set()
        self._fpga_led_mask = 0
        self._led_source_local = True

        self._audio = AudioEngine()
        self._recorder = PerformanceRecorder()
        self._vlfd = VlfdFifoManager(on_rx_sample=self._on_rx_sample_thread)

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(80, self._focus_play_area)

    def _on_rx_sample_thread(self, sample: dict, cmd_kind: str) -> None:
        self.root.after(
            0,
            lambda s=sample.copy(), k=cmd_kind: self._apply_rx_sample(s, k),
        )

    def _apply_rx_sample(self, sample: dict, cmd_kind: str) -> None:
        if cmd_kind == "error" or "error" in sample:
            self._append_log(f"FIFO error: {sample.get('error')}")
            self._audio.stop_fpga_voice()
            return
        leds = sample.get("led") or []
        if len(leds) >= 12:
            m = 0
            for i, v in enumerate(leds[:12]):
                if v:
                    m |= 1 << i
            self._fpga_led_mask = m
        freq = int(sample.get("freq_hz") or 0)
        ts_v = int(sample.get("last_event_ts") or 0)
        self._append_log(f"RX freq={freq} ts={ts_v} ({cmd_kind})")
        if self._vlfd.is_open:
            if cmd_kind == "on":
                if freq > 0:
                    self._lbl_audio_src.configure(text="Audio: FPGA Hz")
                    self._audio.play_freq_hz(float(freq))
                    self._lbl_note.configure(text=f"FPGA FREQ={freq} Hz (TS={ts_v})")
                else:
                    self._audio.stop_fpga_voice()
            else:
                self._audio.stop_fpga_voice()
        if not self._led_source_local:
            self._update_led_display()

    def _focus_play_area(self) -> None:
        try:
            self._play_area.focus_set()
        except tk.TclError:
            pass

    def _build_ui(self) -> None:
        bar = ttk.Frame(self.root, padding=4)
        bar.pack(fill=tk.X)
        self._lbl_fifo = ttk.Label(bar, text="FIFO: disconnected")
        self._lbl_mode = ttk.Label(bar, text="Mode: live")
        self._lbl_octave = ttk.Label(bar, text=f"Octave: {self._octave}")
        self._lbl_audio_src = ttk.Label(bar, text="Audio: local MIDI")
        self._lbl_note = ttk.Label(bar, text="Note: --")
        for w in (
            self._lbl_fifo,
            self._lbl_mode,
            self._lbl_octave,
            self._lbl_audio_src,
            self._lbl_note,
        ):
            w.pack(side=tk.LEFT, padx=4)

        fifo_box = ttk.LabelFrame(self.root, text="VLFD / SMIMS FIFO", padding=6)
        fifo_box.pack(fill=tk.X, padx=6, pady=2)
        row = ttk.Frame(fifo_box)
        row.pack(fill=tk.X)
        ttk.Label(row, text="Backend").pack(side=tk.LEFT)
        self._combo_back = ttk.Combobox(
            row,
            values=("mock (no USB)", "vlfd-ffi DLL"),
            state="readonly",
            width=22,
        )
        self._combo_back.current(0)
        self._combo_back.pack(side=tk.LEFT, padx=4)
        ttk.Label(row, text="DLL path (optional)").pack(side=tk.LEFT)
        self._var_dll = tk.StringVar(value="")
        ttk.Entry(row, textvariable=self._var_dll, width=40).pack(side=tk.LEFT, padx=4)
        self._btn_fifo = ttk.Button(row, text="Connect", command=self._toggle_fifo)
        self._btn_fifo.pack(side=tk.LEFT, padx=4)
        self._combo_led_src = ttk.Combobox(
            row,
            values=(
                "LED strip: local PC keys only",
                "LED strip: FPGA key_state (same as Rabbit LEDs)",
            ),
            state="readonly",
            width=36,
        )
        self._combo_led_src.current(0)
        self._combo_led_src.bind("<<ComboboxSelected>>", self._on_led_source_changed)
        self._combo_led_src.pack(side=tk.LEFT, padx=8)

        self._play_area = ttk.Frame(self.root)
        self._play_area.pack(fill=tk.BOTH, expand=True, padx=6, pady=2)
        self._play_area.configure(takefocus=1)
        self._play_area.bind("<Button-1>", lambda e: self._play_area.focus_set())

        led_box = ttk.LabelFrame(self._play_area, text="LEDs (12 semitones C..B)", padding=4)
        led_box.pack(fill=tk.X, pady=2)
        self._led = LedStripCanvas(led_box)
        self._led.pack(fill=tk.X, expand=False)

        piano_box = ttk.LabelFrame(
            self._play_area,
            text="Piano - click here, then A S D F G H J / W E T Y U",
            padding=4,
        )
        piano_box.pack(fill=tk.BOTH, expand=True, pady=2)
        self._piano = PianoKeysCanvas(self._bindings, piano_box)
        self._piano.pack(fill=tk.BOTH, expand=True)
        self._piano.bind("<Button-1>", lambda e: self._play_area.focus_set())

        # Use bind_all so keys work after clicking piano canvas / LEDs (child focus);
        # parent Frame alone often never receives KeyPress on Windows.
        self.root.bind_all("<KeyPress>", self._on_key_press)
        self.root.bind_all("<KeyRelease>", self._on_key_release)

        rec_box = ttk.LabelFrame(self.root, text="Recording", padding=6)
        rec_box.pack(fill=tk.X, padx=6, pady=2)
        r = ttk.Frame(rec_box)
        r.pack(fill=tk.X)
        self._lbl_rec = ttk.Label(r, text="Idle")
        self._lbl_rec_count = ttk.Label(r, text="Events: 0")
        self._lbl_rec_last = ttk.Label(r, text="Last event t: --")
        self._lbl_rec.pack(side=tk.LEFT, padx=4)
        self._lbl_rec_count.pack(side=tk.LEFT, padx=4)
        self._lbl_rec_last.pack(side=tk.LEFT, padx=4)
        ttk.Button(r, text="Record start", command=self._rec_start).pack(side=tk.RIGHT, padx=2)
        ttk.Button(r, text="Record stop", command=self._rec_stop).pack(side=tk.RIGHT, padx=2)
        ttk.Button(r, text="Clear", command=self._rec_clear).pack(side=tk.RIGHT, padx=2)

        log_box = ttk.LabelFrame(self.root, text="Log", padding=4)
        log_box.pack(fill=tk.BOTH, expand=False, padx=6, pady=4)
        self._log = scrolledtext.ScrolledText(log_box, height=8, state=tk.DISABLED, wrap=tk.WORD)
        self._log.pack(fill=tk.BOTH, expand=True)

        self._append_log(
            "Goal: PC keyboard -> FIFO -> FPGA; FPGA returns freq + LED state via RX (decoded here). "
            "Use vlfd-ffi DLL for real hardware. If connect fails: check DLL path, USB, board power, "
            "and that no other app (e.g. Rabbit) holds the same device."
        )

    def _toggle_fifo(self) -> None:
        if self._vlfd.is_open:
            self._vlfd.disconnect()
            self._btn_fifo.configure(text="Connect")
            self._lbl_fifo.configure(text="FIFO: disconnected")
            self._lbl_audio_src.configure(text="Audio: local MIDI")
            self._audio.stop_fpga_voice()
            self._combo_led_src.current(0)
            self._led_source_local = True
            self._update_led_display()
            self._append_log("FIFO disconnected")
            return
        back = self._combo_back.current()
        dll = self._var_dll.get().strip() or None
        ok = False
        if back == 0:
            ok = self._vlfd.connect_mock()
        else:
            try:
                ok = self._vlfd.connect_vlfd_ffi(dll_path=dll)
            except Exception as e:
                messagebox.showerror("VLFD", str(e))
                return
        if ok:
            self._btn_fifo.configure(text="Disconnect")
            self._lbl_fifo.configure(text="FIFO: connected")
            self._append_log("FIFO connected: LED strip switched to FPGA RX (like Rabbit).")
            self._combo_led_src.current(1)
            self._led_source_local = False
            self._update_led_display()
        else:
            err = getattr(self._vlfd, "last_connect_error", None) or ""
            if err:
                self._append_log(f"FIFO connect failed: {err}")
            messagebox.showwarning(
                "FIFO",
                "Could not connect.\nSee Log for the error detail.",
            )

    def _on_led_source_changed(self, _event=None) -> None:
        idx = self._combo_led_src.current()
        self._led_source_local = idx == 0
        self._update_led_display()

    def _append_log(self, text: str) -> None:
        self._log.configure(state=tk.NORMAL)
        self._log.insert(tk.END, text + "\n")
        self._log.see(tk.END)
        self._log.configure(state=tk.DISABLED)

    def _rec_start(self) -> None:
        self._recorder.start()
        self._lbl_rec.configure(text="Recording")

    def _rec_stop(self) -> None:
        self._recorder.stop()
        self._lbl_rec.configure(text="Stopped")

    def _rec_clear(self) -> None:
        self._recorder.clear()

    def _local_led_mask(self) -> int:
        base = 12 * (self._octave + 1)
        m = 0
        for midi in self._pressed:
            if base <= midi < base + 12:
                m |= 1 << (midi - base)
        return m

    def _update_led_display(self) -> None:
        if self._led_source_local:
            self._led.set_mask(self._local_led_mask())
        else:
            self._led.set_mask(self._fpga_led_mask)

    def _on_key_press(self, event: tk.Event) -> None:
        if _focus_is_text_entry(self.root.focus_get()):
            return
        kid = _event_key_id(event)
        if not kid:
            return
        b = self._by_key.get(kid)
        if b is None:
            return
        if b.midi in self._pressed:
            return
        self._pressed.add(b.midi)
        self._note_on(b)

    def _on_key_release(self, event: tk.Event) -> None:
        if _focus_is_text_entry(self.root.focus_get()):
            return
        kid = _event_key_id(event)
        if not kid:
            return
        b = self._by_key.get(kid)
        if b is None:
            return
        if b.midi not in self._pressed:
            return
        self._pressed.discard(b.midi)
        self._note_off(b)

    def _note_on(self, b: KeyBinding) -> None:
        name = midi_to_name(b.midi)
        kid = b.fpga_key_id
        self._lbl_note.configure(text=f"Note: {name} (FPGA id={kid})")
        self._piano.set_pressed(self._pressed)
        self._update_led_display()
        if self._vlfd.is_open:
            self._vlfd.send_key_on(kid)
            self._append_log(f"FIFO KEY_ON id={kid}")
        else:
            self._audio.note_on(b.midi)
            self._lbl_audio_src.configure(text="Audio: local MIDI")
            self._append_log(f"note_on {name} (local sine)")

        self._recorder.record(EventKind.NOTE_ON, b.midi, name)

    def _note_off(self, b: KeyBinding) -> None:
        name = midi_to_name(b.midi)
        kid = b.fpga_key_id
        if not self._pressed:
            self._lbl_note.configure(text="Note: --")
        else:
            top = max(self._pressed)
            self._lbl_note.configure(text=f"Note: {midi_to_name(top)}")
        self._piano.set_pressed(self._pressed)
        self._update_led_display()
        if self._vlfd.is_open:
            self._vlfd.send_key_off(kid)
            self._append_log(f"FIFO KEY_OFF id={kid}")
            # play_freq_hz() uses loops=-1; stop here so release does not wait for RX(freq==0).
            # Next RX sample will call play_freq_hz again if FPGA still has a main note (e.g. other keys).
            self._audio.stop_fpga_voice()
        else:
            self._audio.note_off(b.midi)

        self._recorder.record(EventKind.NOTE_OFF, b.midi, name)

    def _on_close(self) -> None:
        try:
            self.root.unbind_all("<KeyPress>")
            self.root.unbind_all("<KeyRelease>")
        except tk.TclError:
            pass
        self._vlfd.disconnect()
        self._audio.all_off()
        pygame.mixer.quit()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
