"""ctypes adapter for deterministic tests of the exact native engine sources."""
import ctypes as C
from pathlib import Path
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parent


class Core:
    def __init__(self, rom, library=None):
        path = library or ROOT / "build-host" / (
            "libbadge_nes.dylib" if sys.platform == "darwin" else "libbadge_nes.so")
        self.lib = C.CDLL(str(path))
        specs = {
            "bnes_open": ([C.c_void_p, C.c_size_t, C.c_void_p, C.c_size_t], C.c_char_p),
            "bnes_step": ([C.c_void_p, C.c_uint, C.c_uint], C.c_char_p),
            "bnes_advance": ([C.c_uint, C.c_uint], C.c_char_p),
            "bnes_present": ([C.c_void_p], C.c_char_p),
            "bnes_save": ([C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)], C.c_char_p),
            "bnes_load": ([C.c_void_p, C.c_size_t], C.c_char_p),
            "bnes_close": ([], None),
            "bnes_frame_count": ([], C.c_uint),
            "bnes_errors": ([], C.c_uint),
        }
        for name, (args, ret) in specs.items():
            fn = getattr(self.lib, name)
            fn.argtypes, fn.restype = args, ret
        self.arena = C.create_string_buffer(1024 * 1024)
        self.pixels = bytearray(320 * 240 * 2)
        self.framebuffer = (C.c_uint16 * (320 * 240)).from_buffer(self.pixels)
        self.state = C.create_string_buffer(32768)
        rom = bytes(rom)
        self.check(self.lib.bnes_open(rom, len(rom), self.arena, len(self.arena)))

    @staticmethod
    def check(error):
        if error:
            raise RuntimeError(error.decode())

    def step(self, p1=0, p2=0):
        self.check(self.lib.bnes_step(self.framebuffer, p1, p2))

    def advance(self, p1=0, p2=0):
        self.check(self.lib.bnes_advance(p1, p2))

    def present(self):
        self.check(self.lib.bnes_present(self.framebuffer))

    def save(self, target=None):
        size = C.c_size_t()
        self.check(self.lib.bnes_save(self.state, len(self.state), C.byref(size)))
        data = self.state.raw[:size.value]
        if target is not None:
            if len(target) < len(data):
                raise ValueError("State buffer is too small")
            target[:len(data)] = data
            return len(data)
        return data

    def restore(self, data):
        self.check(self.lib.bnes_load(data, len(data)))

    def stats(self):
        return self.lib.bnes_frame_count(), self.lib.bnes_errors()

    def close(self):
        self.lib.bnes_close()

    def png(self, path):
        # Standard-library-only RGB565 -> RGB PNG, at the device resolution.
        pixels = struct.unpack("<76800H", self.pixels)
        data = bytearray()
        for y in range(240):
            data.append(0)
            for p in pixels[y * 320:(y + 1) * 320]:
                r, g, b = p >> 11, (p >> 5) & 63, p & 31
                data.extend(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)))
        def chunk(tag, body):
            return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body))
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", 320, 240, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(data)) + chunk(b"IEND", b""))
