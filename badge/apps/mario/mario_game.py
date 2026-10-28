"""2026 badge frontend for the unmodified Mario ROM and native NES core."""
import binascii
import gc
import hashlib
import time

from mario_checkpoint import Checkpoints
from mario_controls import Controls

ROM_SHA256 = "0b3d9e1f01ed1668205bab34d6c82b0e281456e137352e4f36a9b2cfa3b66dea"
ROM_SIZE = 40976
# NTSC NES ~60.0988 Hz, not the LCD's nominal 60 Hz. Never discard game ticks.
FRAME_US = 16639


SOURCE_HEADER = b'NES\x1a\x02\x01\x01\x08\x00\x00\x00\x00\x02\x00\x00\x01'


def core_rom(data):
    """Adapt only known NES 2.0 metadata in RAM; never change PRG/CHR/file bytes."""
    if len(data) != ROM_SIZE or bytes(data[:16]) != SOURCE_HEADER:
        raise ValueError("Unsupported cartridge metadata")
    adapted = bytearray(data)
    adapted[7] = 0
    adapted[8:16] = bytes(8)
    return adapted


class Game:
    def __init__(self, core, badge, screen, keys, watchdog=None,
                 rom_path="game.nes", state_dir="/state/mario", display=None):
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
            raise ValueError("game.nes does not match the supplied Mario ROM")
        if core.ABI != 1:
            raise ValueError("Native module and app versions do not match")
        self.arena = bytearray(core.ARENA_SIZE)
        core.load(core_rom(rom), self.arena)
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
