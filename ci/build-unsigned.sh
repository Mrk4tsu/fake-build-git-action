#!/usr/bin/env bash
set -euo pipefail

mkdir -p build output
xcodebuild -version

if ! xcodebuild \
  -project build/iOS/Unity-iPhone.xcodeproj \
  -scheme Unity-iPhone \
  -configuration Release \
  -sdk iphoneos \
  -destination 'generic/platform=iOS' \
  -derivedDataPath "$PWD/build/DerivedData" \
  CODE_SIGNING_ALLOWED=NO \
  CODE_SIGNING_REQUIRED=NO \
  CODE_SIGN_IDENTITY= \
  DEVELOPMENT_TEAM= \
  ENABLE_BITCODE=NO \
  build > build/xcodebuild.log 2>&1; then
  echo '::error::Xcode build failed. The detailed log stays on the temporary runner to avoid publishing source diagnostics.'
  exit 1
fi

products="$PWD/build/DerivedData/Build/Products/Release-iphoneos"
shopt -s nullglob
apps=("$products/"*.app)
if [[ ${#apps[@]} -ne 1 ]]; then
  echo "::error::Expected one iOS .app, found ${#apps[@]}."
  exit 1
fi

app="${apps[0]}"
executable=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "$app/Info.plist")
if [[ ! -f "$app/$executable" ]]; then
  echo '::error::Application executable is missing.'
  exit 1
fi
lipo "$app/$executable" -verify_arch arm64

package=$(mktemp -d "$PWD/build/ipa-package.XXXXXX")
mkdir -p "$package/Payload"
ditto "$app" "$package/Payload/$(basename "$app")"
output="$PWD/output/GaMod-unsigned.ipa"
ditto -c -k --sequesterRsrc --keepParent "$package/Payload" "$output"
unzip -tq "$output"
echo 'Unsigned IPA ready: output/GaMod-unsigned.ipa'
