# Acceptance checklist

## 1. Mac AVD transport

- [x] Discover and connect to both roles through TV Trainer's ordinary discovery screens. TV Trainer showed both roles Ready and the Bumble log showed each measurement subscription.
- [x] Record the working environment and startup.

| Component | Verified configuration |
| --- | --- |
| Host | Apple Silicon macOS, Python 3.14.5 |
| Android Emulator | 37.2.13, build 16740729 |
| AVD | `Television_4K`, Google TV API 36 ARM64, `emulator-5554` |
| Bumble | 0.0.236, two `android-netsim` host connections |
| TV Trainer | Debug build of `b37759cd302895ed3e90edf5e623ddeb261bb07e` |

The running emulator used `-netdelay none -netspeed full -avd Television_4K -qt-hide-window -grpc-use-token -idle-grpc-timeout 300`. The test attached to that AVD as launched, built and installed the debug APK with the script, then connected through the app. Bumble automatic discovery and explicit loopback endpoint selection both worked. An unavailable endpoint exited with an error.

- [ ] Repeat discovery and live measurements on a Google TV API 34 image. The tested SDK had an API 36 Google TV image.

## 2. Device controls and rates

- [x] Verified the panel on desktop and mobile. GATT tests covered current packets, legal boundaries, scheduling after missed deadlines, and independent power cycles.
- [x] Verified a live change from 85 to 50 rpm and 140 to 160 bpm on Ride. The overlay also displayed the later 83 rpm and 173 bpm pattern. Six-second trainer samples at 1, 2, and 10 Hz sent 6, 12, and 60 notifications while HRM remained at 6.
- [x] Verified HRM Off removed heart rate during recording and On restored it without interrupting the ride. Trainer Off interrupted the ride. After reconnection the trainer's accepted target was cleared until explicit Resume.

## 3. Trainer control, app build, and recording

- [x] Built and installed the debug APK on the specified serial. The script rejected a non-emulator serial and a phone emulator without Leanback.
- [x] Validated feature and range reads, invalid and unauthorized command responses, and the separate target and reported-power values.
- [x] Verified a guest synthetic structured ride with a temporary Android test APK that supplied the workout to TV Trainer's session coordinator. Both sensors used the ordinary Android Bluetooth adapter. Zero cadence auto-paused, restoring cadence resumed on the same trainer connection, and the timed open effort produced successful 100 W → resistance level 0 → 150 W indications.
- [x] Compared notification counts, Android Bluetooth diagnostics, persisted observations, and FIT records from a guest ride. The Google TV image routes the export picker to a stub that cancels, so a temporary Android test invoked the app's FIT exporter directly. The FIT contained the 61 rpm / 151 bpm, 72 rpm / 162 bpm, and 83 rpm / 173 bpm patterns with distinct whole-second record timestamps. Recording retained fewer observations than it received at 10 Hz, and FIT export grouped those observations by second. The client debug logs counted 30, 60, and 296 notifications per role in separate approximately 30-second windows at 1, 2, and 10 Hz.
- [ ] Verify interactive FIT export on an Android image or physical TV with a working document picker.

## 4. Real radio hardware

- [ ] Validate two dedicated USB HCI controllers on Linux for simultaneous advertising and stable identity.
- [ ] Verify physical TV discovery and independent disconnect/reconnect for both roles.
