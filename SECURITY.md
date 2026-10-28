# Safety and reporting

Native `.mpy` modules execute machine code on the badge. Only install a build you
trust for the correct RP2350/Cortex-M33 firmware/native ABI. The watchdog and
validation checks reduce failure risk but do not make incompatible native code
safe. Do not flash firmware just to install this project.

Preserve your player checkpoints before experiments. Installers must not erase
unrelated apps, credentials, or `/state` files, and new tests must use scratch
locations. Use only one serial client and save/pause before connecting.

Never submit a ROM, save, credential file, token, or full device dump in an issue.
Report a suspected vulnerability through the maintainer's GitHub contact or a
private security report when available. Describe affected versions and reproduction
steps using synthetic data, not someone else's private files.

The publication audit is defense in depth, not a guarantee against every possible
secret/encoding. Contributors and maintainers remain responsible for reviewing
what they commit and distribute.
