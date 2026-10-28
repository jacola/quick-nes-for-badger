# Validation scope

Public validation/compatibility information is maintained in
[docs/compatibility.md](../../docs/compatibility.md).

The port was validated during development on the Universe 2026 RP2350 badge with
stock clock/firmware, including original-cartridge frame/state replay, the actual
ARM native module, manual-only checkpoint behavior, GC/lifecycle, and launcher
relaunch. This repository deliberately does not include player files, private
probe outputs, screenshots, cartridge binaries, local paths, or device serials.

The fresh public export can be verified without a commercial ROM using the host
suite, generated-program ARM smoke test, package parity checks, and publication
audit. Local-ROM integration checks remain available for contributors who supply
their own files; absence of those files is reported as skipped coverage, not as
a passing commercial-game test.

Extended playthroughs, all-scene/full-speed claims, arbitrary cartridges/boards,
and every physical orientation are outside the verified scope. See
[building.md](../../docs/building.md) for reproduction commands and the native
build manifest alongside each `_nes_core.mpy` for exact build provenance.

## Standalone-export checks

The standalone source rebuild produced the same **77,942-byte** native module as
the physical-badge-tested build:

```text
SHA-256: ae7cfcf86297f38d26ba37587aa59962f2b94847d3c2a4b5e7cc9da080883c38
```

- 97 host tests pass with locally supplied matching ROMs kept outside the project.
- The ROM-free run completes the same suite with five commercial-ROM cases skipped.
- The generated-program ARM smoke test passes all five implemented mappers,
  comparing host/native pixels, state, reset, and replay.
- ASan/UBSan reports deterministic replay through 1,000 host frames with zero
  CPU errors in the local integration check.
- Package/artwork regeneration and the ROM/private-artifact/source-manifest
  publication audit pass. Original controller icons are generated without ROM input.
- Historical deployment logs, user saves, ROMs, device identities, and prior Git
  history are not part of this standalone export.
