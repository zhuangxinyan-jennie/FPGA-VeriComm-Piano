# -*- coding: utf-8 -*-
# Main window: tkinter (stdlib) + pygame audio + serial.

from __future__ import annotations

import re
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from typing import Optional, Set

import pygame

from audio.engine import AudioEngine
from core.events import EventKind
from core.notes import KeyBinding, binding_map_by_key_id, build_default_octave_bindings, midi_to_name
from core.recorder import PerformanceRecorder
from serial_comm.manager import SerialManager
from widgets.led_strip import LedStripCanvas
from widgets.piano_keys import PianoKeysCanvas


def _event_key_id(event: tk.Event) -> Optional[str]:
    ch = getattr(event, "char", "") or ""
    if ch and ch.isalpha():
        return ch.lower()
    ks = (getattr(event, "keysym", "") or "").lower()
    if len(ks) == 1 and ks.isalpha():
        return ks
    return None


class MainWindow:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Electronic keyboard (PC, tkinter)")
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
        self._serial = SerialManager(on_line=self._on_serial_line_thread)

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(80, self._focus_play_area)

    def _focus_play_area(self) -> None:
        try:
            self._play_area.focus_set()
        except tk.TclError:
            pass

    def _base_midi_for_octave(self) -> int:
        return 12 * (self._octave + 1)

    def _on_serial_line_thread(self, line: str) -> None:
        self.root.after(0, lambda l=line: self._handle_serial_line_safe(l))

    def _handle_serial_line_safe(self, line: str) -> None:
        self._append_log(f"serial recv: {line}")
        if self._recorder.is_recording:
            self._recorder.record(
                EventKind.SERIAL_RECV,
                0,
                "",
                extra=line,
            )
        s = line.strip()
        # fpga_piano_top.v: STATE:bbbbbbbbbbbb,FREQ:261,TS:12345
        mfpga = re.match(r"^STATE:([01]{12}),FREQ:(\d{3}),TS:(\d{5})\s*$", s)
        if mfpga:
            try:
                self._fpga_led_mask = int(mfpga.group(1), 2) & 0xFFF
            except ValueError:
                pass
            freq = int(mfpga.group(2), 10)
            ts_v = int(mfpga.group(3), 10)
            if self._serial.is_open:
                self._lbl_audio_src.configure(text="Audio: FPGA Hz")
                if freq > 0:
                    self._audio.play_freq_hz(float(freq))
                    self._lbl_note.configure(text=f"FPGA FREQ={freq} Hz (TS={ts_v})")
                else:
                    self._audio.stop_fpga_voice()
                    self._lbl_note.configure(text=f"idle (TS={ts_v})")
            if not self._led_source_local:
                self._update_led_display()
            return
        mhex = re.match(r"^STATE:\s*([0-9A-Fa-f]+)\s*$", s, re.I)
        if mhex:
            try:
                self._fpga_led_mask = int(mhex.group(1), 16) & 0xFFF
            except ValueError:
                pass
            if not self._led_source_local:
                self._update_led_display()

    def _build_ui(self) -> None:
        bar = ttk.Frame(self.root, padding=4)
        bar.pack(fill=tk.X)
        self._lbl_serial = ttk.Label(bar, text="Serial: disconnected")
        self._lbl_mode = ttk.Label(bar, text="Mode: live")
        self._lbl_octave = ttk.Label(bar, text=f"Octave: {self._octave}")
        self._lbl_voice = ttk.Label(bar, text="Voice: sine")
        self._lbl_audio_src = ttk.Label(bar, text="Audio: local MIDI")
        self._lbl_note = ttk.Label(bar, text="Note: --")
        for w in (
            self._lbl_serial,
            self._lbl_mode,
            self._lbl_octave,
            self._lbl_voice,
            self._lbl_audio_src,
            self._lbl_note,
        ):
            w.pack(side=tk.LEFT, padx=4)

        serial_box = ttk.LabelFrame(self.root, text="Serial", padding=6)
        serial_box.pack(fill=tk.X, padx=6, pady=2)
        srow = ttk.Frame(serial_box)
        srow.pack(fill=tk.X)
        ttk.Label(srow, text="Port").pack(side=tk.LEFT)
        self._combo_port = ttk.Combobox(srow, width=14)
        self._combo_port.pack(side=tk.LEFT, padx=4)
        ttk.Label(srow, text="Baud").pack(side=tk.LEFT)
        self._baud_var = tk.StringVar(value="115200")
        ttk.Entry(srow, textvariable=self._baud_var, width=10).pack(side=tk.LEFT, padx=4)
        ttk.Button(srow, text="Refresh ports", command=self._refresh_ports).pack(
            side=tk.LEFT, padx=4
        )
        self._btn_serial = ttk.Button(srow, text="Connect", command=self._toggle_serial)
        self._btn_serial.pack(side=tk.LEFT, padx=4)
        self._combo_led_src = ttk.Combobox(
            srow,
            values=("LEDs: local keys", "LEDs: serial STATE"),
            state="readonly",
            width=22,
        )
        self._combo_led_src.current(0)
        self._combo_led_src.bind("<<ComboboxSelected>>", self._on_led_source_changed)
        self._combo_led_src.pack(side=tk.LEFT, padx=8)
        self._refresh_ports()

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

        self._play_area.bind("<KeyPress>", self._on_key_press)
        self._play_area.bind("<KeyRelease>", self._on_key_release)

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
            "Ready. With serial connected: send KEY_ON/KEY_OFF (0..11); "
            "sound follows FPGA line STATE:12bits,FREQ:3digits,TS:5digits. "
            "Offline: local MIDI sine."
        )

    def _refresh_ports(self) -> None:
        ports = SerialManager.list_ports()
        if ports:
            self._combo_port["values"] = tuple(ports)
            self._combo_port.set(ports[0])
        else:
            self._combo_port["values"] = ("COM3",)
            self._combo_port.set("COM3")

    def _toggle_serial(self) -> None:
        if self._serial.is_open:
            self._serial.disconnect()
            self._btn_serial.configure(text="Connect")
            self._lbl_serial.configure(text="Serial: disconnected")
            self._lbl_audio_src.configure(text="Audio: local MIDI")
            self._audio.stop_fpga_voice()
            self._append_log("serial: disconnected")
            return
        port = self._combo_port.get().strip()
        try:
            baud = int(self._baud_var.get().strip())
        except ValueError:
            messagebox.showerror("Serial", "Invalid baud rate.")
            return
        if self._serial.connect(port, baud):
            self._btn_serial.configure(text="Disconnect")
            self._lbl_serial.configure(text=f"Serial: {port} @ {baud}")
            self._lbl_audio_src.configure(text="Audio: FPGA Hz (wait for lines)")
            self._append_log(f"serial: connected {port} {baud}")
        else:
            messagebox.showwarning(
                "Serial",
                "Could not open port (check name and other apps using it).",
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
        self._sync_rec_labels()

    def _rec_stop(self) -> None:
        self._recorder.stop()
        self._lbl_rec.configure(text="Stopped")
        self._sync_rec_labels()

    def _rec_clear(self) -> None:
        self._recorder.clear()
        self._sync_rec_labels()

    def _sync_rec_labels(self) -> None:
        self._lbl_rec_count.configure(text=f"Events: {self._recorder.count}")
        last = self._recorder.last_event()
        if last:
            self._lbl_rec_last.configure(text=f"Last event t: {last.t_ms} ms")
        else:
            self._lbl_rec_last.configure(text="Last event t: --")

    def _local_led_mask(self) -> int:
        base = self._base_midi_for_octave()
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
        if self._serial.is_open:
            self._serial.send_key_on(kid)
            self._append_log(f"note_on {name} -> KEY_ON:{kid}")
            self._append_log(f"serial send: KEY_ON:{kid}")
        else:
            self._audio.note_on(b.midi)
            self._lbl_audio_src.configure(text="Audio: local MIDI")
            self._append_log(f"note_on {name} (local sine)")

        self._recorder.record(EventKind.NOTE_ON, b.midi, name)
        if self._recorder.is_recording:
            self._recorder.record(
                EventKind.SERIAL_SEND,
                b.midi,
                name,
                extra=f"KEY_ON:{kid}",
            )
        self._sync_rec_labels()

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
        if self._serial.is_open:
            self._serial.send_key_off(kid)
            self._append_log(f"note_off {name} -> KEY_OFF:{kid}")
            self._append_log(f"serial send: KEY_OFF:{kid}")
        else:
            self._audio.note_off(b.midi)

        self._recorder.record(EventKind.NOTE_OFF, b.midi, name)
        if self._recorder.is_recording:
            self._recorder.record(
                EventKind.SERIAL_SEND,
                b.midi,
                name,
                extra=f"KEY_OFF:{kid}",
            )
        self._sync_rec_labels()

    def _on_close(self) -> None:
        self._serial.disconnect()
        self._audio.all_off()
        pygame.mixer.quit()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
