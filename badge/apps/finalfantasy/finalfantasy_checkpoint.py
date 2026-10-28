"""Bounded, checksummed, two-generation full-machine checkpoints.

Only /state/finalfantasy is written. Closing and verifying a temporary file before
LittleFS's atomic rename leaves the last committed checkpoint intact on reset.
If no generation matches this ROM, existing saves are preserved and writes stop.
"""
import binascii
import errno
import io
import os
import struct

try:
    import deflate
except ImportError:
    deflate = None
    import zlib

MAGIC = b"FF1STATE"
ABI = 1
MAX_STATE = 32768
PREFIX = "<8s6I32s"
HEADER = PREFIX + "I"
HEADER_SIZE = struct.calcsize(HEADER)


class CheckpointError(Exception):
    pass


def _compress(data):
    if deflate is None:
        return zlib.compress(data, 1)
    # Some badge firmware builds include only the DEFLATE decoder. The
    # checkpoint container already supports raw payloads; do not make saves
    # depend on an optional compressor or require a firmware replacement.
    if not hasattr(deflate.DeflateIO, "write"):
        return data
    stream = io.BytesIO()
    with deflate.DeflateIO(stream, deflate.ZLIB, 9) as compressor:
        compressor.write(data)
    return stream.getvalue()


def _decompress(data, expected):
    if deflate is None:
        decoder = zlib.decompressobj()
        result = decoder.decompress(data, expected + 1)
        if (len(result) != expected or not decoder.eof or
                decoder.unused_data or decoder.unconsumed_tail):
            raise CheckpointError("Invalid compressed state")
        return result
    with deflate.DeflateIO(io.BytesIO(data), deflate.ZLIB) as decoder:
        result = decoder.read(expected + 1)
        if len(result) != expected or decoder.read(1):
            raise CheckpointError("Invalid compressed state")
        return result


class Checkpoints:
    def __init__(self, rom_hash, directory="/state/finalfantasy"):
        if len(rom_hash) != 32:
            raise ValueError("Expected SHA-256 ROM identity")
        self.directory = directory
        self.rom_hash = rom_hash
        self.generation = 0
        self.last_frame = -1
        self.last_error = None
        self.recovered = False
        self.writable = True
        self.saving = False
        self.buffer = bytearray(MAX_STATE)

    def _path(self, slot):
        return self.directory + "/autosave." + str(slot)

    def _read(self, path):
        with open(path, "rb") as source:
            header = source.read(HEADER_SIZE)
            if len(header) != HEADER_SIZE:
                raise CheckpointError("Truncated checkpoint header")
            magic, abi, generation, frame, codec, raw_size, size, rom_hash, crc = struct.unpack(HEADER, header)
            if magic != MAGIC or abi != ABI:
                raise CheckpointError("Unsupported checkpoint format")
            if rom_hash != self.rom_hash:
                raise CheckpointError("Checkpoint belongs to another ROM")
            if (codec not in (0, 1) or not 16 <= raw_size <= MAX_STATE or
                    not 1 <= size <= MAX_STATE or generation < 1):
                raise CheckpointError("Invalid checkpoint size or generation")
            stored = source.read(size)
            if len(stored) != size or source.read(1):
                raise CheckpointError("Truncated or oversized checkpoint")
        actual = binascii.crc32(stored, binascii.crc32(header[:-4])) & 0xffffffff
        if actual != crc:
            raise CheckpointError("Checkpoint checksum failed")
        try:
            payload = _decompress(stored, raw_size) if codec else stored
        except Exception as exc:
            raise CheckpointError("Invalid compressed checkpoint: " + str(exc))
        if len(payload) != raw_size:
            raise CheckpointError("Incorrect decoded state size")
        return generation, frame, payload

    def restore(self, core):
        records = []
        problems = []
        for slot in (0, 1):
            try:
                records.append(self._read(self._path(slot)))
            except OSError as exc:
                if exc.args and exc.args[0] == errno.ENOENT:
                    continue
                problems.append(str(exc))
            except (CheckpointError, ValueError) as exc:
                problems.append(str(exc))
        records.sort(key=lambda item: item[0], reverse=True)
        for generation, frame, payload in records:
            try:
                core.restore(payload)
                if core.stats()[0] != frame:
                    raise CheckpointError("Checkpoint frame does not match machine state")
            except (RuntimeError, ValueError, CheckpointError) as exc:
                problems.append(str(exc))
                continue
            self.generation = max(item[0] for item in records)
            self.last_frame = frame
            self.recovered = bool(problems)
            self.last_error = "Recovered previous checkpoint" if problems else None
            return True
        if records or problems:
            self.writable = False
            self.last_error = "; ".join(problems) or "No usable machine state"
            raise CheckpointError("Resume failed; saves preserved: " + self.last_error)
        return False

    def save(self, core):
        if not self.writable or self.saving:
            return False
        frame = core.stats()[0]
        if frame == self.last_frame:
            return True
        self.saving = True
        try:
            size = core.save(self.buffer)
            if not 16 <= size <= MAX_STATE:
                raise CheckpointError("Core produced an invalid state size")
            raw = memoryview(self.buffer)[:size]
            compressed = _compress(raw)
            codec, stored = (1, compressed) if len(compressed) < size else (0, raw)
            generation = self.generation + 1
            if generation > 0xffffffff:
                raise CheckpointError("Checkpoint generation overflow")
            prefix = struct.pack(PREFIX, MAGIC, ABI, generation, frame,
                                 codec, size, len(stored), self.rom_hash)
            crc = binascii.crc32(stored, binascii.crc32(prefix)) & 0xffffffff
            try:
                os.mkdir(self.directory)
            except OSError as exc:
                if not exc.args or exc.args[0] != errno.EEXIST:
                    raise
            target = self._path(generation % 2)
            temporary = target + ".tmp"
            with open(temporary, "wb") as out:
                if out.write(prefix + struct.pack("<I", crc)) != HEADER_SIZE:
                    raise OSError("Short checkpoint header write")
                if out.write(stored) != len(stored):
                    raise OSError("Short checkpoint write")
            # Catch partial writes/storage errors before committing anything.
            verified = self._read(temporary)
            if verified[0] != generation or verified[1] != frame or verified[2] != bytes(raw):
                raise CheckpointError("Checkpoint verification failed")
            os.rename(temporary, target)
            if hasattr(os, "sync"):
                os.sync()
            self.generation, self.last_frame = generation, frame
            self.last_error = None
            return True
        except Exception as exc:
            self.last_error = str(exc)
            print("Final Fantasy USA checkpoint not saved:", exc)
            return False
        finally:
            self.saving = False
