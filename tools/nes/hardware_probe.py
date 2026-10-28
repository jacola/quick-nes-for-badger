"""Run with mpremote AFTER installation; uses scratch saves, never player saves.

A watchdog is armed BEFORE importing the native module. The board is reset
at the end (or automatically within eight seconds if native code stalls).
Look for ZELDA_NATIVE_PASS in captured output; no other output proves success.
"""
import machine
watchdog = machine.WDT(timeout=8000)

import os
import sys
import gc
import time
import binascii
import hashlib
import json

APP = "/system/apps/zelda"
sys.path.insert(0, APP)
scratch = None

try:
    import _nes_core as core
    from checkpoint import Checkpoints
    watchdog.feed()
    rom = open(APP + "/game.nes", "rb").read()
    digest = hashlib.sha256(rom).digest()
    assert binascii.hexlify(digest).decode() == "89232edf4f9b52e3cb872094bc78973de080befca2ddea893b6e936066514d4e"
    # Deliberately leave ownership solely with the native module's root list.
    core.load(rom, bytearray(core.ARENA_SIZE))
    del rom
    gc.collect()
    badge.mode(HIRES)
    badge.default_clear = None
    screen.pen = color.rgb(0, 0, 0)
    screen.clear()
    total_us = 0
    worst_us = 0
    for frame in range(600):
        watchdog.feed()
        started = time.ticks_us()
        core.step(screen.raw, 0, 0)
        elapsed = time.ticks_diff(time.ticks_us(), started)
        total_us += elapsed
        worst_us = max(worst_us, elapsed)
        # Repeated GC + allocation pressure checks the actual native roots.
        if frame % 17 == 0:
            junk = [bytearray(31) for _ in range(16)]
            del junk
            gc.collect()
        if frame % 60 == 59:
            display.update()
            print("ZELDA_FRAME", core.stats(), "us", elapsed)
    assert core.stats()[0:2] == (600, 0)
    assert binascii.crc32(screen.raw) & 0xffffffff == 0xc2d244c6

    for suffix in range(100):
        candidate = "/state/zelda-native-probe-%02d" % suffix
        try:
            os.mkdir(candidate)
            scratch = candidate
            break
        except OSError as exc:
            if exc.args[0] != 17: raise
    assert scratch is not None
    store = Checkpoints(digest, scratch)
    watchdog.feed()
    assert store.save(core), store.last_error
    for frame in range(30):
        watchdog.feed()
        core.step(screen.raw, 8 if frame < 2 else 0, 0)
    expected_pixels = binascii.crc32(screen.raw)
    buf = bytearray(core.STATE_SIZE)
    length = core.save(buf)
    expected_state = binascii.crc32(memoryview(buf)[:length])
    assert store.save(core), store.last_error

    # Simulate interruption/corruption of the latest committed slot. The prior
    # generation must still resume correctly after rebuilding the entire VM.
    with open(scratch + "/autosave.0", "wb") as out:
        out.write(b"interrupted probe save")
    core.close()
    gc.collect()
    rom = open(APP + "/game.nes", "rb").read()
    core.load(rom, bytearray(core.ARENA_SIZE))
    del rom
    watchdog.feed()
    recovered = Checkpoints(digest, scratch)
    assert recovered.restore(core) and recovered.recovered
    assert core.stats()[0] == 600
    gc.collect()
    for frame in range(30):
        watchdog.feed()
        core.step(screen.raw, 8 if frame < 2 else 0, 0)
    length = core.save(buf)
    assert binascii.crc32(screen.raw) == expected_pixels
    assert binascii.crc32(memoryview(buf)[:length]) == expected_state
    assert core.stats()[1] == 0
    display.update()
    watchdog.feed()
    full_started = time.ticks_us()
    for _ in range(60):
        watchdog.feed()
        core.advance(0, 0)
        display.set_async(False)
        core.present(screen.raw)
        display.set_async(True)
        display.update()
        badge.poll()
    display.set_async(False)
    full_us = time.ticks_diff(time.ticks_us(), full_started)
    assert core.stats()[1] == 0
    print("ZELDA_NATIVE_PASS", json.dumps({
        "frames": core.stats()[0], "cpu_errors": core.stats()[1],
        "arena": core.stats()[2], "mean_core_us": total_us // 600,
        "worst_core_us": worst_us, "unpaced_display_fps": 60000000 / full_us,
        "gc": True, "resume": True, "fallback": True, "pipelined": True,
    }))
except Exception as exc:
    print("ZELDA_NATIVE_FAIL")
    sys.print_exception(exc)
finally:
    watchdog.feed()
    display.set_async(False)
    if scratch is not None:
        for name in os.listdir(scratch):
            os.remove(scratch + "/" + name)
        os.rmdir(scratch)
    # Let the USB CDC FIFO drain before reset so the result is captured.
    time.sleep_ms(250)
    # This is a hardware reset, not flashing or changing startup configuration.
    machine.reset()
