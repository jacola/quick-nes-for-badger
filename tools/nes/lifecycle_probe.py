"""Real MonaOS manual-save/lifecycle regression (scratch saves, no player writes).

Set NES_APP='mario' before exec to test Mario; default is Zelda.
LEFT+RIGHT is held, partially released, pressed again, fully released, and
pressed again. Only the two fully re-armed requests may write. HOME and exit
notifications must never write. Two relaunches must resume the last manual save.
"""
import machine
wdt = machine.WDT(timeout=8000)
import os
import sys
import time
import json

slug = globals().get("NES_APP", "zelda")
assert slug in ("zelda", "mario", "contra", "mario3", "megaman2", "tetris", "finalfantasy", "finalfantasyjp")
APP = "/system/apps/" + slug
sys.path.insert(0, APP)
checkpoint = __import__("checkpoint" if slug == "zelda" else slug + "_checkpoint")
original_store = checkpoint.Checkpoints
original_call = run.__call__
original_pressed = badge.pressed
scratch = None
for suffix in range(100):
    candidate = "/state/nes-lifecycle-%s-%02d" % (slug, suffix)
    try:
        os.mkdir(candidate)
        scratch = candidate
        break
    except OSError as exc:
        if exc.args[0] != 17:
            raise
assert scratch is not None


class ProbeStore(original_store):
    def __init__(self, digest, directory=None):
        super().__init__(digest, scratch)


checkpoint.Checkpoints = ProbeStore
frames = 0
context = None
speeds = []


def injected_pressed(button=None):
    active = None
    if 160 <= frames < 180 or 190 <= frames < 200 or 210 <= frames < 230:
        active = (BUTTON_LEFT, BUTTON_RIGHT)
    elif 180 <= frames < 190:
        active = (BUTTON_LEFT,)
    elif 230 <= frames < 240:
        active = (BUTTON_RIGHT,)
    elif frames >= 260:
        active = (BUTTON_HOME,)
    if active is not None:
        return set(active) if button is None else button in active
    return original_pressed() if button is None else original_pressed(button)


def guarded_call(self, callback):
    global context
    candidate = callback.__globals__
    if candidate.get("APP_DIR") != APP:
        return original_call(self, callback)
    context = candidate
    initial_generation = context["game"].checkpoints.generation
    started = time.ticks_us()

    def wrapped():
        global frames
        wdt.feed()
        frames += 1
        result = callback()
        game = context["game"]
        if context.get("error"):
            raise AssertionError(context["error"])
        if frames == 20:
            for _ in range(10):
                context["on_exit"]()
                assert not game.closed
                assert game.checkpoints.generation == initial_generation
        if frames == 159:
            assert game.checkpoints.generation == initial_generation
            speeds.append(159000000 / time.ticks_diff(time.ticks_us(), started))
        if frames == 199:
            assert game.checkpoints.generation == initial_generation + 1
        if frames == 259:
            assert game.checkpoints.generation == initial_generation + 2
        if frames > 265:
            raise AssertionError("HOME did not stop the app")
        return result
    return original_call(self, wrapped)


try:
    run.__call__ = guarded_call
    badge.pressed = injected_pressed
    saved = []
    for iteration in range(3):
        frames = 0
        context = None
        wdt.feed()
        launch(APP)
        assert context is not None
        game = context["game"]
        assert context["error"] is None
        assert game.closed and game.save_ok
        assert game.checkpoints.last_frame == 210 * (iteration + 1)
        assert game.checkpoints.generation == 2 * (iteration + 1)
        assert game.resumed == (iteration > 0)
        saved.append(game.checkpoints.last_frame)
    print("NES_MANUAL_SAVE_PASS", json.dumps({"app":slug,"saved_frames":saved,
          "exit_notifications":30,"home_exits":3,"checkpoints":6,
          "held_combo_did_not_repeat":True,"no_implicit_writes":True,
          "empty_initial_save":True,"relaunch_resume":True,"fps_samples":speeds}))
except Exception as exc:
    print("NES_MANUAL_SAVE_FAIL",slug)
    sys.print_exception(exc)
finally:
    run.__call__ = original_call
    badge.pressed = original_pressed
    checkpoint.Checkpoints = original_store
    display.set_async(False)
    wdt.feed()
    for name in os.listdir(scratch):
        os.remove(scratch + "/" + name)
    os.rmdir(scratch)
    time.sleep_ms(250)
    machine.reset()
