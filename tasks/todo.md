# Acceptance checklist

## 1. Prove the Mac AVD transport

- [ ] Attach one Bumble peripheral through Netsim on Apple Silicon. Use TV Trainer's ordinary discovery and connect flow to receive a valid HR measurement.
- [ ] Record the AVD, emulator, Bumble versions, launch arguments, and subscription evidence.

## 2. Complete both device workflows

- [ ] Start independent FTMS and Heart Rate Service peripherals with distinct stable addresses. Add usable value sliders, frequency controls and power switches.
- [ ] Test legal boundary values, frequency changes and missed deadlines with deterministic clocks. Demonstrate that switching one peripheral off closes its connection and leaves the other active.

## 3. Verify trainer control and debug workflow

- [ ] Add the emulator-targeted debug APK build/install workflow. Verify it refuses a non-emulator serial.
- [ ] Validate feature and range reads, control-point acknowledgment, invalid target handling and the synthetic telemetry model.
- [ ] Run structured auto-pause/resume, HR and trainer reconnect, ERG/free-ride transition, and FIT export scenarios on Google TV.

## 4. Verify a real radio transport

- [ ] Select and validate an external real BLE controller. Confirm independent roles and identity stability.
- [ ] Verify the physical TV discovers both peripherals and run independent disconnect/reconnect smoke checks.
