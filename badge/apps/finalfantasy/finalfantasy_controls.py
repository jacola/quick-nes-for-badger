"""NES input with reliable physical START and manual-save combinations."""

A, B, SELECT, START, UP, DOWN, LEFT, RIGHT = 1, 2, 4, 8, 16, 32, 64, 128
START_PULSE_FRAMES = 4


class Controls:
    def __init__(self, keys):
        self.keys = keys
        self.menu_was_down = False
        self.menu_chord = False
        self.block_back = False
        self.save_requested = False
        self.save_latched = False
        self.start_latched = False
        self.start_frames = 0

    def sample(self, badge):
        up, down, left, right, action, back, menu = self.keys
        touched = getattr(badge, "touched", None)
        def active(key):
            if badge.held(key) or badge.pressed(key):
                return True
            # MENU/BACK have no physical switches. Some firmware exposes their
            # capacitive state through touched() before the button event sets.
            return bool(touched and (key == menu or key == back) and touched(key))

        u, d, l, r = active(up), active(down), active(left), active(right)

        # The two actual UP/DOWN switches provide an unambiguous START input.
        # Keep it held until BOTH release, so a partial release/bounce cannot
        # generate repeated pause presses. Short taps last at least four NES
        # frames, rather than a single frame that a game may not poll.
        if u and d:
            if not self.start_latched:
                self.start_frames = START_PULSE_FRAMES
            self.start_latched = True
        elif not u and not d:
            self.start_latched = False

        self.save_requested = l and r and not self.save_latched
        if l and r:
            self.save_latched = True
        elif not l and not r:
            self.save_latched = False

        result = 0
        if not self.start_latched:
            result |= UP if u and not d else DOWN if d and not u else 0
        if not self.save_latched:
            result |= LEFT if l and not r else RIGHT if r and not l else 0
        if active(action):
            result |= A

        menu_down, back_down = active(menu), active(back)
        if not back_down:
            self.block_back = False
        if menu_down:
            if not self.menu_was_down:
                self.menu_chord = False
            if back_down:
                self.menu_chord = True
                self.block_back = True
                result |= SELECT
        elif self.menu_was_down and not self.menu_chord:
            self.start_frames = START_PULSE_FRAMES
        if back_down and not menu_down and not self.block_back:
            result |= B
        self.menu_was_down = menu_down

        if self.start_latched or self.start_frames:
            result |= START
        if self.start_frames:
            self.start_frames -= 1
        return result
