# Trainer Simulator specification

## Purpose

Test TV Trainer's actual Android Bluetooth discovery, GATT setup, live metrics, workout control, and reconnection on a Mac without a smart trainer or chest strap. Operate both simulated peripherals from a separate local browser app while the Android Virtual Device (AVD) runs TV Trainer. The same controls should support physical-TV testing when real BLE radio hardware is available.

## Control panel

| Control | Trainer | Heart-rate monitor |
| --- | --- | --- |
| Device power | On / Off | On / Off |
| Reading | Cadence slider, 0–150 rpm in 1 rpm steps. Default 85 rpm. | Heart-rate slider, 30–240 bpm in 1 bpm steps. Default 140 bpm. |
| Notification frequency | 0.5, 1, 2, 4, 5 or 10 Hz. Default 2 Hz. | 0.5, 1, 2, 4, 5 or 10 Hz. Default 1 Hz. |
| Status | Off, Advertising, Connected or Sending. Show current reported watts, accepted ERG target or resistance, and actual send rate. | Off, Advertising, Connected or Sending. Show actual send rate. |

Both devices start Off. Slider and rate changes affect only the selected peripheral and take effect on its next notification. Display the values and units beside each slider and support keyboard adjustment. A cadence of 0 rpm is a valid reading. The power switch simulates turning the peripheral itself off. It cancels notifications, stops advertising and terminates the active GATT connection. Turning it back on advertises the same simulator identity. The other device keeps its link and its settings.

Frequency means **GATT measurement notifications per second**, separate from advertising rate, the BLE connection interval, cadence in rpm, and heart rate in bpm. Higher settings are test inputs. Each peripheral has its own monotonic scheduler and sends only while the central is subscribed. Skip missed deadlines after host stalls and resume at the next deadline. Report measured send rates over a short rolling window. TV Trainer can apply its existing recording limits on receipt.

## Bluetooth behavior

Expose two independent connectable devices with stable, distinct simulator addresses and names, such as **Sim Trainer** and **Sim HRM**. Include the advertised service UUIDs so the TV Trainer device filters discover the correct role.

### Trainer

- Advertise Fitness Machine Service `0x1826`. Implement Fitness Machine Feature `0x2ACC`, Indoor Bike Data `0x2AD2` notifications, supported resistance and power range reads `0x2AD6` and `0x2AD8`, and Fitness Machine Control Point `0x2AD9` writes and indications. Advertise capability bits only for implemented features.
- Include speed, cadence and instantaneous power in the baseline Indoor Bike Data packet. Use the Bluetooth SIG units, flags and field order. Include observed resistance when using the current encoding. Baseline capability and byte fixtures should match the standard-compatible path in TV Trainer; the older resistance encoding can be added as a separate compatibility fixture.
- Support Request Control, Set Target Power, Set Target Resistance, Start or Resume, and Stop or Pause with the FTMS response indication that references the original opcode. Validate targets against the ranges returned by GATT reads. Return a protocol failure for invalid or unauthorized commands. A write acknowledgment alone leaves the command pending.
- Keep accepted target and simulated measured power separate. For predictable tests, derive reported power from the accepted target and cadence in ERG, and from a documented synthetic cadence/resistance function in resistance mode. At zero cadence, report zero measured power. Reset control authorization and active load when the link ends. Resolve the exact synthetic model and fixture ranges in implementation.

### Heart-rate monitor

- Advertise Heart Rate Service `0x180D`. Send standard Heart Rate Measurement `0x2A37` notifications with the BPM slider value and valid flags. An 8-bit BPM measurement is sufficient for the initial range.
- Use a separate connection and subscription lifecycle from the trainer. Advertise again using the same address after a simulated power cycle.

Specifications and current client behavior. [Bluetooth SIG Fitness Machine Service](https://www.bluetooth.com/specifications/specs/fitness-machine-service-1-0-1/) · [Bluetooth SIG Heart Rate Service](https://www.bluetooth.com/specifications/specs/heart-rate-service-1-0/) · [TV Trainer Bluetooth adapter](https://github.com/dds72/tv-trainer/tree/b37759cd302895ed3e90edf5e623ddeb261bb07e/core/bluetooth)

## Integration

### Primary target: Google TV AVD on macOS

Run a small Python service on the Mac using Bumble. Serve the controls over loopback and use two Bumble peripheral instances attached to the same Netsim instance as the AVD through Bumble's `android-netsim` host transport. Give each peripheral its own virtual controller and unique name. Support automatic Netsim discovery and a configurable loopback endpoint for multiple emulator instances. Fail visibly if the endpoint is unavailable. The browser talks to the simulator locally. The AVD receives ordinary BLE advertisements, events and GATT traffic.

```text
Local browser controls → Simulator service → Bumble trainer + HRM
                                                    ↕
                                           Netsim virtual radio
                                                    ↕
                         Google TV AVD → Android Bluetooth → TV Trainer debug APK
```

Google documents BLE support on emulator images at API 31 and above. The local setup has Android Emulator 37.2.13 and a running `Television_4K` Google TV API 36 ARM64 AVD with Leanback and Bluetooth LE features. The guest Bluetooth adapter reported On, and the host Netsim process had loopback listeners. This verifies the available environment. A Bumble peripheral connecting and sending notifications to TV Trainer is the first implementation acceptance check. Start with that AVD. Add API 34 to the verified matrix when the same check passes there.

The simulator should first try the existing AVD launch defaults. Bumble documents `-packet-streamer-endpoint default` as an explicit launch option on versions that need it. Record the exact emulator and Bumble versions and startup sequence that pass the first check.

[Android Emulator networking](https://developer.android.com/studio/run/emulator-networking) · [AOSP Netsim device types](https://android.googlesource.com/platform/tools/netsim/+/refs/heads/main/guide/src/) · [Bumble with Android Emulator](https://google.github.io/bumble/platforms/android.html) · [Bumble Netsim transport](https://google.github.io/bumble/transports/android_emulator.html)

### Dedicated TV Trainer debug build

Add a build/install workflow in this repo around the existing TV Trainer `:app:assembleDebug` task. It takes a separate TV Trainer checkout and an explicit ADB serial, verifies that the target is an emulator with Leanback and Bluetooth LE, and stages an emulator debug artifact. Use a dedicated test AVD and a guest or synthetic workout. Setup should keep production data and account credentials out of the test environment. The test APK can use the existing debug application ID because the AVD is isolated. A future side-by-side installation in one AVD would need a flavor or application ID suffix as a build-only change.

The simulator connects outside the app process. Both the emulator debug build and the regular TV build use the same Android BLE API and TV Trainer adapter. An HTTP or in-process fake injected into TV Trainer would bypass Bluetooth discovery, GATT setup and disconnects. A second AVD running an Android peripheral app is a fallback to evaluate if host attachment fails. That approach adds another AVD to operate and depends on its support for advertising and GATT server mode. Prefer the single-AVD Netsim approach when it passes the acceptance check.

### Physical TV

The same host controls and peripheral behavior should support a physical TV using an explicitly selected real BLE transport. Netsim traffic stays inside the emulator environment. Evaluate a Bumble-supported external USB HCI controller on a Linux host or small Linux board as the first hardware option. Verify two simultaneous peripheral identities and role isolation before claiming support. Use a dedicated controller per simulated role if a single controller cannot provide stable separate identities. This path is an opt-in hardware milestone. The Mac AVD path does not require any USB adapter or changes to the Mac's Bluetooth settings. [Bumble USB HCI transport](https://google.github.io/bumble/transports/usb.html)

## Acceptance

1. On the Mac, start the simulator and install the TV Trainer debug APK on the chosen AVD. Find both devices using TV Trainer's normal discovery screens and connect to both.
2. Change cadence from 85 to 50 rpm and HR from 140 to 160 bpm while connected. Verify the new values on Ride and the overlay. Change one notification frequency and verify that the other stream's counted rate stays stable.
3. Start a synthetic structured ride with positive cadence. Set cadence to zero to exercise auto-pause, then raise it to exercise cadence-based resume. Confirm the trainer stayed connected throughout.
4. Turn HR Off during a ride, observe its disconnection and verify the workout continues. Turn it On and confirm the client reconnects and readings return. Turn the trainer Off, confirm the workout enters its interruption flow, turn it On, and verify trainer load waits for explicit Resume.
5. Start an ERG workout that contains a timed open effort. Verify acknowledged power, resistance and power commands in that order and observe the independent simulated measurements.
6. Record known cadence and heart-rate patterns at 1, 2 and 10 Hz. Compare simulator send counts, TV Trainer Bluetooth diagnostics and exported synthetic FIT fields. Confirm that the simulator can exercise actual client-side thinning without forcing a particular number of FIT samples.
7. Repeat the core discovery and disconnection checks on a physical TV once the external BLE transport passes its own validation.
