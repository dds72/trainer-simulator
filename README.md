# Trainer Simulator

A planned local control panel for testing [TV Trainer](https://github.com/dds72/tv-trainer) with a virtual smart trainer and heart-rate monitor. The primary target is Android Emulator on Apple Silicon macOS, using a Google TV AVD. A separate radio mode is planned for the physical TV.

The simulator will run on the Mac and expose two Bluetooth LE peripherals through Android Emulator's Netsim virtual radio. TV Trainer will discover and connect to them using its existing Bluetooth code. The control panel will provide cadence and heart-rate sliders, adjustable notification rates, and a separate on/off switch for each device.

This repository currently contains the specification and implementation plan.

- [Specification](SPECIFICATION.md)
- [Implementation plan](tasks/plan.md)
- [Acceptance checklist](tasks/todo.md)
