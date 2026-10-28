# Setup and troubleshooting

Start with the [quick start](../README.md). You do not need to build the emulator,
flash firmware, or connect to Wi-Fi to use a matching prebuilt app.

## Check the badge, not just its appearance

This targets the **Universe 2026 RP2350 / Cortex-M33 badge with PSRAM** and its
MonaOS/Badgeware API. The earlier RP2040 badge and generic MicroPython boards are
not drop-in targets. Do not copy the native module to them and hope it works.

For an optional firmware check, install the serial utility in a Python environment:

```sh
python3 -m pip install mpremote
mpremote devs
mpremote connect <port> exec "import sys,os,machine; print(os.uname()); print(sys.implementation); print('mpy',sys.implementation._mpy); print('Hz',machine.freq())"
mpremote connect <port> reset
```

Use the port discovered for the badge (normally USB VID/PID `2e8a:1101`), not a
Bluetooth/debug console. A macOS port usually starts `/dev/cu.usbmodem`; Linux
usually `/dev/ttyACM`; Windows uses `COM...`. The suffix and serial number vary.
Only one serial client may own it. Close other REPL programs before using mpremote.

**A serial command can interrupt the running app. Save/pause first.** The tested
native ABI reports `7942` and accepts `.mpy` v6.3; see [compatibility](compatibility.md).
A matching integer alone is not proof that another board exposes the required
badge/display APIs. Rebuild and test deliberately for other firmware.

## Enter USB app-storage mode

The normal firmware mounts `/system` read-only. This is why a direct command such
as `mpremote fs cp ... :/system/apps/...` can fail with `EROFS`.

Open the **Mass Storage** app on the badge. Alternatively, with a working REPL:

```sh
mpremote connect <port> exec "import powman; powman.reset_into_msc()"
```

The USB connection drops/re-enumerates; that disconnect is expected. Wait for the
app filesystem to mount. Its root contains `main.py` and `apps/` and corresponds
to the badge's `/system` directory. Do not replace either wholesale.

If the drive is named **RP2350**, that is BOOTSEL/firmware-upload mode. It is not
the app filesystem. Leave it without holding the boot control (normally unplug
and reconnect), then enter the firmware's Mass Storage app instead. No UF2 is
provided or needed by this project.

## Choose the actual mount path

Examples only—discover yours:

| Host | Example `--mount` |
| --- | --- |
| macOS | `/Volumes/BADGER` |
| Linux | `/media/your-user/BADGER` |
| Windows | `E:\` |

On Windows, run commands on one line and use `python` if `python3` is unavailable.
For example:

```text
python tools/nes/install.py --game mario --rom "C:\path\your-own-game.nes" --mount E:\ --write
```

The installer requires a matching ROM hash and native build manifest, checks
space, and refuses symlinked app/backup directories. The selected app is staged
outside `apps/`, checked, and promoted. A failed replacement retains/rolls back
the previous app. It never writes `/state`, firmware, the launcher, or credentials.

## Updating

Use the same profile/ROM with `--replace --write`. The previous complete app is
kept under `.<slug>-backups/` on the app volume. **That backup contains your ROM**;
do not upload it or add it to this repository. Preserve it until the update works.

These on-badge backups occupy space. If necessary, deliberately archive them on
your computer and verify the copy before removing one. The installer will not
delete backups, unrelated apps, or saves to make an update fit. Use
[the separate save backup procedure](saves.md); app backups are not save backups.

## Finish cleanly

Eject the app volume using your operating system. On macOS:

```sh
diskutil eject /Volumes/BADGER
```

Some firmware restarts itself on eject. Otherwise reset the badge after ejection.
If using serial, rediscover the port before `mpremote connect <port> reset`.

## Common problems

| Problem | What to check |
| --- | --- |
| No USB device | A data-capable cable, correct port, and no competing serial client |
| ROM hash mismatch | Run `inspect_rom.py`; compare region/revision/size/hash. Do not rewrite headers or bypass the identity check |
| `.mpy` missing/invalid | Download/extract the whole project, not an HTML file from a file-preview page; keep `_nes_core.mpy` |
| Incompatible native ABI | Check the exact badge/firmware; use the [build guide](building.md), not a random binary |
| App not in launcher | Confirm `apps/<slug>/__init__.py` exists on the app volume, then restart |
| Wrong/new game after exit | Only completed LEFT+RIGHT checkpoints persist; HOME deliberately does not save |
| Red save indicator | Stop assuming progress is safe; check writable `/state` space and retain previous checkpoints |
| Unreadable checkpoint | Files are preserved. Back up both generations before investigating; don't delete them to hide the error |
| No sound / slower than console | Known hardware/performance limits; see [compatibility](compatibility.md) |

If reporting a problem, include the profile, ROM **hash only**, firmware/native
ABI, and exact error. Do not attach ROMs, save files, credentials, or device dumps.
