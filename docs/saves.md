# Checkpoints and saved progress

## The rule

**LEFT + RIGHT together saves. HOME does not.** Release both directions to re-arm
before another save. There is no timer, periodic autosave, or exit-time write.
Wait for the green border dot before leaving; red means the write failed.

Reopening an app resumes its most recent completed checkpoint. With no checkpoint,
it starts the original game normally. All progress since the last completed
checkpoint is lost on HOME, reset, power-off, or a battery failure.

## What is saved

A checkpoint captures the emulator CPU, PPU, APU, mapper, and RAM state, including
battery-backed cartridge RAM. An original game's in-game save (for example an
inn/tent save) changes emulated RAM; make a badge checkpoint to persist that RAM.
These are emulator snapshots, not interchangeable `.sav` files for other emulators.

Each app/version has its own identity and directory:

```text
/state/<profile>/autosave.0
/state/<profile>/autosave.1
```

The historical filenames do not imply automatic saving. File headers bind a state
to the ROM and emulator ABI. Two generations, bounded reads, checksums, verified
temporary writes, and atomic rename retain the prior generation if a write fails.
A corrupt newest generation falls back to the older valid one. If both are invalid,
the app preserves them and reports an error instead of silently overwriting them.

On decoder-only DeflateIO firmware, states are stored raw. Other compatible firmware
may compress them. A raw state is about 13–21 KB for the tested cartridges; two
completed generations are kept. Save writes can briefly pause emulation.

## Back up saves separately from app files

`/state` is on a different filesystem from the USB app volume. The installer's
app backup contains code/assets and your ROM, **not your checkpoint directory**.
Use serial file copies for saves, after saving and stopping play:

```sh
mpremote devs
# Replace <port>; make a private local backup directory first.
mpremote connect <port> fs cp :/state/zelda/autosave.0 /path/to/private-backup/autosave.0
mpremote connect <port> fs cp :/state/zelda/autosave.1 /path/to/private-backup/autosave.1
mpremote connect <port> reset
```

A generation may not exist yet. Substitute the selected profile's directory.
Keep both files and verify the copies. **Never commit or publish saves**: they can
contain personal names and game data. Local backup directories are gitignored,
but that is not a substitute for checking what you publish.

To deliberately start over, first back up both generations, then remove only that
profile's checkpoints while the app is not running. There is no destructive erase
shortcut in the frontend. Do not copy another game's save into the directory,
rename a ROM to bypass identity checks, or restore an older backup over newer
progress without checking what you are replacing.

The installer leaves all `/state` files untouched. An emulator ABI change can make
older checkpoints incompatible even when the ROM is unchanged; preserve your
backups and read release notes before changing core versions.
