# Implementation plan

Keep the simulator, browser controls, and peripheral runtime in this repository. Use TV Trainer's existing Android Bluetooth adapter for emulator acceptance.

| Milestone | Depends on | Observable outcome |
| --- | --- | --- |
| 1. Prove the Mac AVD transport | Google TV AVD and Android Emulator | TV Trainer discovers and receives measurements over Bumble's Netsim transport. |
| 2. Complete both device workflows | 1 | The browser changes cadence, BPM, and rates live. Either device can be switched off and rediscovered independently. |
| 3. Verify trainer control and debug workflow | 2 | The debug APK records rides and demonstrates FTMS commands, pause, disconnect, and explicit resume. |
| 4. Verify a real radio transport | 2–3, dedicated controllers and a physical TV | The same simulator UI drives both roles over real BLE. |

The runtime path is browser → loopback HTTP → independent GATT peripherals → Bumble HCI transport → Android Bluetooth. Packet fixtures and scheduler timing tests run without a radio. The build/install script stages the TV Trainer debug APK independently of simulator startup.
