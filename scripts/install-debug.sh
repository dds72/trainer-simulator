#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
    printf 'Usage: %s TV_TRAINER_CHECKOUT emulator-SERIAL\n' "$0" >&2
    exit 2
fi

checkout=$(cd -- "$1" && pwd)
serial=$2
if [[ ! "$serial" =~ ^emulator-[0-9]+$ ]]; then
    printf 'An explicit emulator serial is required.\n' >&2
    exit 2
fi
if [[ ! -x "$checkout/gradlew" || ! -f "$checkout/app/build.gradle.kts" ]]; then
    printf 'TV Trainer checkout must contain gradlew and app/build.gradle.kts.\n' >&2
    exit 2
fi

adb=${ADB:-adb}
if [[ -z ${ADB:-} && -n ${ANDROID_HOME:-} ]]; then
    adb="$ANDROID_HOME/platform-tools/adb"
fi
if [[ $("$adb" -s "$serial" get-state) != device ||
      $("$adb" -s "$serial" shell getprop ro.kernel.qemu | tr -d '\r') != 1 ]]; then
    printf 'The selected device must be a running Android emulator.\n' >&2
    exit 2
fi
features=$("$adb" -s "$serial" shell pm list features | tr -d '\r')
for feature in android.software.leanback android.hardware.bluetooth_le; do
    if ! grep -Fxq "feature:$feature" <<< "$features"; then
        printf 'The selected emulator is missing %s.\n' "$feature" >&2
        exit 2
    fi
done

avd=$("$adb" -s "$serial" emu avd name | sed -n '1s/\r$//p')
printf 'Building debug APK for %s (%s). Use a dedicated AVD and a local guest profile.\n' "$avd" "$serial"
(cd -- "$checkout" && ./gradlew :app:assembleDebug)
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
mkdir -p "$repo/artifacts"
artifact="$repo/artifacts/tv-trainer-$serial-debug.apk"
staging=$(mktemp -d "$repo/artifacts/.tv-trainer-$serial.XXXXXX")
trap 'rm -f -- "$staging/app-debug.apk"; rmdir -- "$staging"' EXIT
cp -- "$checkout/app/build/outputs/apk/debug/app-debug.apk" "$staging/app-debug.apk"
if [[ $("$adb" -s "$serial" emu avd name | sed -n '1s/\r$//p') != "$avd" ]]; then
    printf 'The selected AVD changed during the build.\n' >&2
    exit 2
fi
"$adb" -s "$serial" install -r "$staging/app-debug.apk"
mv -f -- "$staging/app-debug.apk" "$artifact"
printf 'Installed and staged %s\n' "$artifact"
