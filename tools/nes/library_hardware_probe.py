"""Guarded cartridge gameplay/replay test. Host prepends NES_PROBE config.

Uses UP+DOWN through the real frontend Controls class for every scripted START.
All writes go to a new scratch directory, never a player's checkpoint path.
"""
import machine
wdt=machine.WDT(timeout=8000)
import os,sys,time,gc,json,hashlib,binascii

config=globals()['NES_PROBE']
slug=config['slug']
assert slug in ('contra','mario3','megaman2','tetris','finalfantasy','finalfantasyjp')
APP='/system/apps/'+slug
sys.path.insert(0,APP)
scratch=None
try:
    import _nes_core as core
    frontend=__import__(slug+'_game')
    storage=__import__(slug+'_checkpoint')
    rom=open(APP+'/game.nes','rb').read()
    digest=hashlib.sha256(rom).digest()
    assert binascii.hexlify(digest).decode()==config['sha256']
    core.load(rom,bytearray(core.ARENA_SIZE));del rom
    gc.collect()
    badge.mode(HIRES);badge.default_clear=None
    display.set_async(False)
    screen.pen=color.rgb(0,0,0);screen.clear()
    controls=frontend.Controls((BUTTON_UP,BUTTON_DOWN,BUTTON_LEFT,BUTTON_RIGHT,
                               BUTTON_SELECT,BUTTON_BACK,BUTTON_MENU))
    class Inputs:
        mask=0
        def held(self,key):
            mask=self.mask
            if key==BUTTON_UP:return bool(mask&16 or mask&8)
            if key==BUTTON_DOWN:return bool(mask&32 or mask&8)
            if key==BUTTON_LEFT:return bool(mask&64)
            if key==BUTTON_RIGHT:return bool(mask&128)
            if key==BUTTON_SELECT:return bool(mask&1)
            if key==BUTTON_BACK:return bool(mask&2)
            return False
        def pressed(self,key):return False
    inputs=Inputs()
    def frames(count,pad):
        inputs.mask=pad
        for i in range(count):
            wdt.feed()
            translated=controls.sample(inputs)
            assert translated==pad,(pad,translated)
            core.step(screen.raw,translated,0)
            if i%60==59:
                gc.collect();display.update()
        assert core.stats()[1]==0
    for count,pad in config['boot']:frames(count,pad)
    boot_crc=binascii.crc32(screen.raw)&0xffffffff
    assert boot_crc==config['boot_crc'],(boot_crc,config['boot_crc'])
    for i in range(100):
        p='/state/nes-cart-probe-%s-%02d'%(slug,i)
        try:os.mkdir(p);scratch=p;break
        except OSError as exc:
            if exc.args[0]!=17:raise
    assert scratch
    saves=storage.Checkpoints(digest,scratch)
    assert saves.save(core),saves.last_error
    for count,pad in config['replay']:frames(count,pad)
    expected_pixels=binascii.crc32(screen.raw)&0xffffffff
    assert expected_pixels==config['end_crc']
    buf=bytearray(core.STATE_SIZE);length=core.save(buf)
    expected_state=binascii.crc32(memoryview(buf)[:length])&0xffffffff
    core.close();gc.collect()
    rom=open(APP+'/game.nes','rb').read()
    core.load(rom,bytearray(core.ARENA_SIZE));del rom
    assert storage.Checkpoints(digest,scratch).restore(core)
    controls=frontend.Controls((BUTTON_UP,BUTTON_DOWN,BUTTON_LEFT,BUTTON_RIGHT,
                               BUTTON_SELECT,BUTTON_BACK,BUTTON_MENU))
    for count,pad in config['replay']:frames(count,pad)
    length=core.save(buf)
    assert binascii.crc32(screen.raw)&0xffffffff==expected_pixels
    assert binascii.crc32(memoryview(buf)[:length])&0xffffffff==expected_state
    started=time.ticks_us()
    for _ in range(90):
        wdt.feed()
        core.advance(0,0)
        display.set_async(False);core.present(screen.raw)
        display.set_async(True);display.update();badge.poll()
    display.set_async(False)
    elapsed=time.ticks_diff(time.ticks_us(),started)
    assert core.stats()[1]==0
    print('NES_LIBRARY_PASS',json.dumps({'app':slug,'frames':core.stats()[0],
        'cpu_errors':0,'physical_start_path':True,'gc':True,'resume':True,
        'arena':core.stats()[2],'state_bytes':length,'pipelined_fps':90000000/elapsed,
        'boot_crc':boot_crc,'replay_crc':expected_pixels}))
except Exception as exc:
    print('NES_LIBRARY_FAIL',slug);sys.print_exception(exc)
finally:
    display.set_async(False)
    wdt.feed()
    if scratch:
        for name in os.listdir(scratch):os.remove(scratch+'/'+name)
        os.rmdir(scratch)
    time.sleep_ms(250);machine.reset()
