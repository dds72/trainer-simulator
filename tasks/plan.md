# Implementation plan

The initial work is a proof of the Android Bluetooth path on Apple Silicon macOS. Keep the simulator, its local controls and its peripheral runtime in this repository. Leave the TV Trainer application runtime on its existing BLE implementation.

| Milestone | Depends on | Observable outcome |
| --- | --- | --- |
| 1. Prove the Mac AVD transport | Google TV AVD and Android Emulator | TV Trainer discovers and receives a measurement from the documented Bumble GATT transport. |
| 2. Complete both device workflows | 1 | The browser changes cadence, BPM and rates live. Either device can be switched off and rediscovered independently. |
| 3. Verify trainer control and debug workflow | 2 | The dedicated debug APK runs an ERG and free-ride sequence and demonstrates pause, disconnect and explicit resume. |
| 4. Verify a real radio transport | 2–3, test controller and physical TV | The same simulator UI drives both roles over real BLE. |

Keep Bluetooth connections, notification scheduling and packet encoding separate from the UI. Use original packet fixtures and documented specifications. Pin the tested Bumble dependency once the transport milestone passes. Build a small runner that makes the target AVD, transport status and test APK explicit. Run the checklist after each milestone. Report the emulator image, versions and hardware actually used.
