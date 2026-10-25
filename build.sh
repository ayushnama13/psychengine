#!/usr/bin/env bash
# One-command rebuild: books -> content -> signed APK.
#   ./build.sh 2,3,4        # book ids from the psychengine DB
# Adding a book later = run this with the extra id. User data lives on the phone and is untouched.
set -euo pipefail
cd "$(dirname "$0")"
BOOKS="${1:?usage: ./build.sh <comma-separated book ids>}"
export PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH"
export JAVA_HOME="$HOME/android-sdk/jdk" ANDROID_HOME="$HOME/android-sdk" ANDROID_SDK_ROOT="$HOME/android-sdk"
export PATH="$JAVA_HOME/bin:$PATH"
PY=/home/ayush/projects/psychengine/psychengine-web/.venv/bin/python
KEY="$HOME/.psychengine-keys/release.jks"
BT="$ANDROID_HOME/build-tools/34.0.0"

$PY tools/export_content.py --books "$BOOKS" --out build/content.db
python3 tools/build_www.py build/content.db --www www
python3 tools/build_topics.py --www www
npx cap sync android >/dev/null

VC=$(( $(date +%s) / 60 ))            # always increases -> installs as an update
VN="1.$(date +%Y%m%d.%H%M)"
(cd android && GRADLE_BIN="$ANDROID_HOME/gradle-8.2.1/bin/gradle"; [ -x "$GRADLE_BIN" ] || GRADLE_BIN=./gradlew; "$GRADLE_BIN" -q assembleRelease -Pvc="$VC" -Pvn="$VN")

mkdir -p dist
UNSIGNED=android/app/build/outputs/apk/release/app-release-unsigned.apk
"$BT/zipalign" -f -p 4 "$UNSIGNED" build/aligned.apk
"$BT/apksigner" sign --ks "$KEY" --ks-pass file:"$HOME/.psychengine-keys/pass.txt" --out "dist/PsychEngine-$VN.apk" build/aligned.apk
"$BT/apksigner" verify "dist/PsychEngine-$VN.apk"
ls -la "dist/PsychEngine-$VN.apk"
