"""Verify original Mario gameplay and checkpoint replay on the real badge.

Uses scratch checkpoints, not player saves. The watchdog is armed before
native import and the badge resets after printing the explicit pass/fail marker.
"""
import machine
wdt=machine.WDT(timeout=8000)
import sys, os, gc, time, hashlib, binascii, json

APP="/system/apps/mario"
sys.path.insert(0,APP)
scratch=None
try:
    import _nes_core as core
    from mario_game import core_rom, ROM_SHA256
    from mario_checkpoint import Checkpoints
    rom=open(APP+"/game.nes","rb").read()
    digest=hashlib.sha256(rom).digest()
    assert binascii.hexlify(digest).decode()==ROM_SHA256
    core.load(core_rom(rom),bytearray(core.ARENA_SIZE))
    del rom
    gc.collect()
    badge.mode(HIRES);badge.default_clear=None
    display.set_async(False)
    screen.pen=color.rgb(0,0,0);screen.clear()

    def frames(count,pad=0):
        for i in range(count):
            wdt.feed()
            core.step(screen.raw,pad,0)
            if i%30==29:display.update()
        assert core.stats()[1]==0

    frames(120)
    assert binascii.crc32(screen.raw)&0xffffffff==0xc01c3bff
    frames(2,8);frames(200)
    assert binascii.crc32(screen.raw)&0xffffffff==0x70ef10cc
    for n in range(100):
        p="/state/mario-native-probe-%02d"%n
        try:os.mkdir(p);scratch=p;break
        except OSError as exc:
            if exc.args[0]!=17:raise
    assert scratch
    store=Checkpoints(digest,scratch)
    assert store.save(core),store.last_error
    frames(90,0x82);frames(30,0x83);frames(50,0x82)
    expected_pixels=binascii.crc32(screen.raw)
    assert expected_pixels&0xffffffff==0x54764fe1
    buf=bytearray(core.STATE_SIZE)
    length=core.save(buf)
    assert length==12792
    expected_state=binascii.crc32(memoryview(buf)[:length])
    core.close();gc.collect()
    rom=open(APP+"/game.nes","rb").read()
    core.load(core_rom(rom),bytearray(core.ARENA_SIZE));del rom
    assert Checkpoints(digest,scratch).restore(core)
    assert core.stats()[0]==322
    gc.collect()
    frames(90,0x82);frames(30,0x83);frames(50,0x82)
    length=core.save(buf)
    assert binascii.crc32(screen.raw)==expected_pixels
    assert binascii.crc32(memoryview(buf)[:length])==expected_state
    started=time.ticks_us()
    for _ in range(120):
        wdt.feed()
        core.advance(0,0)
        display.set_async(False);core.present(screen.raw)
        display.set_async(True);display.update();badge.poll()
    display.set_async(False)
    elapsed=time.ticks_diff(time.ticks_us(),started)
    assert core.stats()[1]==0
    print("MARIO_NATIVE_PASS",json.dumps({"frames":core.stats()[0],
        "cpu_errors":0,"arena":core.stats()[2],"state_size":length,
        "title_and_1_1":True,"run_jump":True,"resume":True,"gc":True,
        "pipelined_fps":120000000/elapsed}))
except Exception as exc:
    print("MARIO_NATIVE_FAIL");sys.print_exception(exc)
finally:
    wdt.feed()
    display.set_async(False)
    if scratch:
        for name in os.listdir(scratch):os.remove(scratch+"/"+name)
        os.rmdir(scratch)
    time.sleep_ms(250)
    machine.reset()
