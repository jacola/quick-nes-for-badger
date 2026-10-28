"""Final Fantasy (USA) running locally in a native NES emulator."""
import os
import sys
import time

APP_DIR = next((p for p in ("/remote/apps/finalfantasy", "/system/apps/finalfantasy", "/apps/finalfantasy")
                if is_dir(p)), os.getcwd())
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

previous_mode = badge.mode()
previous_clear = badge.default_clear
if hasattr(display, "set_async"):
    display.set_async(False)
badge.mode(HIRES)  # 320x240, no LCD-vsync throttling of the NES frame clock.
badge.default_clear = None
screen.font = font.nope
screen.pen = color.rgb(0, 0, 0)
screen.clear()
screen.pen = color.rgb(210, 210, 210)
screen.text("Loading the original Final Fantasy USA ROM...", 24, 100)
screen.text("UP + DOWN: START   LEFT + RIGHT: SAVE", 12, 118)
display.update()

game = None
watchdog = None
error = None
save_border = rect(8, 224, 8, 8)
save_dot = rect(10, 226, 4, 4)

try:
    # A bad native module must never strand the badge in an unrecoverable
    # tight loop. A watchdog reset returns to the unchanged MonaOS launcher.
    import machine
    watchdog = machine.WDT(timeout=8000)
    import _nes_core
    from finalfantasy_game import Game
    game = Game(_nes_core, badge, screen,
                (BUTTON_UP, BUTTON_DOWN, BUTTON_LEFT, BUTTON_RIGHT,
                 BUTTON_SELECT, BUTTON_BACK, BUTTON_MENU), watchdog, display=display)
    screen.pen = color.rgb(0, 0, 0)
    screen.clear()
    # Static legends stay in the unused side borders, outside the NES image.
    screen.font = getattr(font, "desert", font.nope)
    screen.pen = color.rgb(150, 150, 150)
    for x, first, second in ((1, "U+D", "START"), (289, "L+R", "SAVE")):
        screen.text(first, x, 12)
        label = second if screen.measure_text(second)[0] <= 30 else ("GO" if x == 1 else "SV")
        screen.text(label, x, 25)
    screen.font = font.nope
except Exception as exc:
    error = str(exc)
    sys.print_exception(exc)


def show_error(message):
    if hasattr(display, "set_async"):
        display.set_async(False)
    screen.pen = color.rgb(0, 0, 0)
    screen.clear()
    screen.pen = color.rgb(255, 120, 110)
    screen.text("Final Fantasy USA could not continue", 12, 12)
    screen.pen = color.rgb(230, 230, 230)
    # Basic wrapping avoids relying on version-specific text overflow APIs.
    words = message.split()
    line, y = "", 42
    for word in words:
        if len(line) + len(word) > 37:
            screen.text(line, 12, y)
            line, y = "", y + 15
        line += (" " if line else "") + word
    if line:
        screen.text(line, 12, y)
    screen.text("Saves are preserved. HOME: launcher", 12, 218)


def update():
    global error
    if watchdog:
        watchdog.feed()
    if badge.pressed(BUTTON_HOME):
        return True  # Explicitly exit without creating a new checkpoint.
    if error is not None:
        show_error(error)
        return None
    try:
        game.update()
        # Status belongs in the unused border, never over the NES picture.
        screen.pen = color.rgb(0, 0, 0)
        screen.rectangle(save_border)
        if not game.save_ok:
            screen.pen = color.rgb(255, 70, 60)
            screen.rectangle(save_dot)
        elif time.ticks_diff(game.save_pulse_until, time.ticks_ms()) > 0:
            screen.pen = color.rgb(70, 220, 100)
            screen.rectangle(save_dot)
    except Exception as exc:
        error = str(exc)
        sys.print_exception(exc)
    return None


def on_exit():
    # Notifications can arrive before the loop has stopped. Do not unload
    # the VM or save implicitly: LEFT+RIGHT is the sole checkpoint command.
    pass


try:
    run(update)
finally:
    # Native teardown belongs only after the actual run loop has returned.
    if hasattr(display, "set_async"):
        display.set_async(False)
    if game is not None:
        game.close()
    badge.default_clear = previous_clear
    badge.mode(previous_mode)
