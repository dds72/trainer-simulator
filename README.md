# Trainer Simulator

Trainer Simulator lets TV Trainer discover, connect to, and control a simulated smart trainer and heart-rate monitor over Android Bluetooth. A local browser panel controls both peripherals. The macOS setup uses Bumble and the Android Emulator's Netsim radio.

## Run on macOS

1. Start a dedicated Google TV AVD with Bluetooth enabled. API 36 on Apple Silicon is verified. Use the emulator's standard startup settings first.
2. Install the simulator with Python 3.12 or newer.

   ```sh
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   .venv/bin/python -m trainer_simulator
   ```

3. Open [the local control panel](http://127.0.0.1:8765). Both devices start **Off**. Switch them on and use TV Trainer's normal **Find devices** screen to connect the trainer and heart-rate roles separately.

Use `--netsim-endpoint 127.0.0.1:PORT` to select a specific Netsim instance. Use the Netsim backend gRPC port, which differs from the ADB serial port and Android Emulator's own gRPC port. The simulator logs the selected endpoint and reports connection failures at startup. If your emulator version does not start Netsim by default, launch the AVD with `-packet-streamer-endpoint default`. [Bumble's emulator setup](https://google.github.io/bumble/platforms/android.html)

### Build and install TV Trainer

Point the script at a separate checkout and the exact serial of the dedicated AVD. Use **Continue as guest** for manual rides and keep the AVD free of production accounts, credentials, and workouts.

```sh
adb devices -l
./scripts/install-debug.sh ../tv-trainer emulator-5554
```

The script checks for a running Android emulator, Leanback, and Bluetooth LE. It runs `:app:assembleDebug`, installs the APK, and stages it at `artifacts/tv-trainer-emulator-5554-debug.apk` for the example serial. Set `ANDROID_HOME` or `ADB` if ADB is outside your PATH. Use the JDK and Android SDK required by the TV Trainer checkout.

## Measurements and control

Each peripheral advertises one service on a stable, distinct static random address. Notifications require a GATT subscription. **Send rate** counts notifications issued by the simulator over a rolling five-second window. **Notifications sent** is the running count since the simulator started. Switching a peripheral off closes its GATT link. Its slider and rate settings carry over when it is turned on again.

The trainer advertises power targets from 0 to 1,000 W in 5 W steps and resistance levels from 0 to 20 in whole steps. Resistance range and observed resistance use the current one-byte encoding. Set Target Resistance takes a signed 16-bit value in tenths. [Bluetooth SIG Fitness Machine Service](https://www.bluetooth.com/specifications/specs/fitness-machine-service-1-0-1/)

- Speed is `0.30 × cadence` km/h.
- In ERG, reported power is `round(target watts × min(cadence / 85, 1))`.
- In resistance mode, reported power is `round(cadence × (0.5 + 0.25 × level))`. A running trainer without a target uses level zero.
- Power is zero while stopped, paused, or at zero cadence. Pause retains an accepted target for Resume. Stop or disconnect clears the target, and disconnect also clears control authorization.

## Physical TV

Select two dedicated Bumble-supported USB HCI controllers on a Linux host, one for each role.

```sh
.venv/bin/python -m trainer_simulator \
  --trainer-usb VENDOR:PRODUCT/TRAINER_SERIAL \
  --hrm-usb VENDOR:PRODUCT/HRM_SERIAL
```

Open the control panel on that host. The USB path requires hardware verification of simultaneous advertising, stable addresses, and independent reconnects before it can be counted as supported. [Bumble USB transport](https://google.github.io/bumble/transports/usb.html)

## Verification

```sh
.venv/bin/python -m unittest discover -s tests -v
```

The tests cover byte fixtures, command rejection, scheduler deadlines, and the dual-device GATT lifecycle on Bumble's in-memory radio. The [acceptance checklist](tasks/todo.md) records the separate Google TV AVD results and outstanding hardware checks.
