"""2026 badge frontend for the unmodified Contra ROM and native NES core."""
import binascii
import gc
import hashlib
import time

from contra_checkpoint import Checkpoints
from contra_controls import Controls

ROM_SHA256 = "26541a5550ee22deeb3d5484e4a96130219b58cff74d068fb1eb6567fa5e5519"
ROM_SIZE = 131088
# NTSC NES ~60.0988 Hz, not the LCD's nominal 60 Hz. Never discard game ticks.
FRAME_US = 16639


class Game:
    def __init__(self, core, badge, screen, keys, watchdog=None,
                 rom_path="game.nes", state_dir="/state/contra", display=None):
        self.core = core
        self.badge = badge
        self.screen = screen
        self.watchdog = watchdog
        self.display = (display if display is not None and
                        hasattr(display, "set_async") and
                        hasattr(core, "advance") and hasattr(core, "present") else None)
        if self.display is not None:
            self.display.set_async(False)
        self.controls = Controls(keys)
        self.ready = False
        self.closed = False
        self.frame_due = time.ticks_us()
        self.save_ok = True
        self.save_pulse_until = 0
        self.feed()
        with open(rom_path, "rb") as rom_file:
            rom = rom_file.read(ROM_SIZE + 1)
        if len(rom) != ROM_SIZE:
            raise ValueError("Incorrect game.nes size; use the supplied original ROM")
        digest = hashlib.sha256(rom).digest()
        if binascii.hexlify(digest).decode() != ROM_SHA256:
            raise ValueError("game.nes does not match the supplied Contra ROM")
        if core.ABI != 1:
            raise ValueError("Native module and app versions do not match")
        self.arena = bytearray(core.ARENA_SIZE)
        core.load(rom, self.arena)
        del rom
        self.feed()
        self.checkpoints = Checkpoints(digest, state_dir)
        self.resumed = self.checkpoints.restore(core)
        self.ready = True
        # Explicitly exercise memory lifetime before the first frame.
        gc.collect()
        self.feed()
        self.frame_due = time.ticks_us()

    def feed(self):
        if self.watchdog is not None:
            self.watchdog.feed()

    def save(self):
        if self.closed:
            return self.save_ok  # Late/repeated exit notifications are harmless.
        if not self.ready:
            return False
        self.feed()
        if self.display is not None:
            self.display.set_async(False)  # Drain display work before flash I/O.
        self.save_ok = self.checkpoints.save(self.core)
        self.save_pulse_until = time.ticks_add(time.ticks_ms(), 600)
        self.feed()
        return self.save_ok

    def update(self):
        self.feed()
        if self.closed or not self.ready:
            return  # Never call into an unloaded VM from a late callback.
        # The framework owns input polling and display transfer. This function
        # advances exactly one whole NES frame, so checkpoints are coherent.
        now = time.ticks_us()
        wait = time.ticks_diff(self.frame_due, now)
        if wait > 0:
            time.sleep_us(wait)
        pad = self.controls.sample(self.badge)
        if self.display is None:
            self.core.step(self.screen.raw, pad, 0)
        else:
            try:
                # The CPU/PPU render into private memory while the previous
                # LCD transfer runs. Fence before touching the shared screen.
                self.core.advance(pad, 0)
                self.display.set_async(False)
                self.core.present(self.screen.raw)
            except Exception:
                self.display.set_async(False)
                raise
        self.frame_due = time.ticks_add(self.frame_due, FRAME_US)
        now = time.ticks_us()
        # Bound catch-up after long flash writes or a debug interruption, not
        # by skipping CPU/PPU frames or changing the game's simulation rate.
        if time.ticks_diff(now, self.frame_due) > 4 * FRAME_US:
            self.frame_due = now
        if self.controls.save_requested:
            self.save()
        if self.display is not None:
            self.display.set_async(True)  # run() queues the next transfer.

    def close(self):
        if self.closed:
            return self.save_ok
        # Only the explicit LEFT+RIGHT command writes a checkpoint. Exiting
        # must not bring back periodic/exit-time flash stalls or overwrite it.
        if self.display is not None:
            self.display.set_async(False)
        self.core.close()
        self.closed = True
        return self.save_ok
