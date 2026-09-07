#!/bin/sh
# Resolve the Hikvision HCNetSDK `lib` directory into $OUT (default /sdk/lib).
# Sources, in order: extracted lib dir, local zip, HCNETSDK_ZIP_URL, Hikvision's official download.
set -eu

SRC_DIR="${SRC_DIR:-/tmp/sdk}"
OUT="${OUT:-/sdk/lib}"
HCNETSDK_ZIP_URL="${HCNETSDK_ZIP_URL:-}"
OFFICIAL_ZIP="https://assets.hikvision.com/prd/normal/all/files/202605/EN-HCNetSDKV6.1.9.48_build20230410_linux64.zip"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0 Safari/537.36"
WORK="$(mktemp -d)"

fetch() {
  # Hikvision's CDN returns an HTML 403 page unless the request looks like a browser and the URL is signed.
  url="$1"
  echo "Downloading SDK from $url" >&2
  curl -fsSL --retry 3 -A "$UA" -H "Referer: https://www.hikvision.com/" -o "$WORK/sdk.zip" "$url"
}

sign_official_url() {
  encoded="$(printf '%s' "$OFFICIAL_ZIP" | sed 's|:|%3A|g; s|/|%2F|g')"
  curl -fsSL -A "$UA" -H "Referer: https://www.hikvision.com/" \
    "https://assetsign.hikvision.com/asset/assetAuth?originalUrl=$encoded" \
    | sed -n 's/.*"data":"\([^"]*\)".*/\1/p'
}

if [ -f "$SRC_DIR/lib/libhcnetsdk.so" ]; then
  echo "Using extracted SDK from $SRC_DIR/lib" >&2
  mkdir -p "$(dirname "$OUT")" && cp -r "$SRC_DIR/lib" "$OUT"
  exit 0
fi

zip="$(ls "$SRC_DIR"/*.zip 2>/dev/null | head -n 1 || true)"
if [ -n "$zip" ]; then
  echo "Using local SDK zip $zip" >&2
  cp "$zip" "$WORK/sdk.zip"
elif [ -n "$HCNETSDK_ZIP_URL" ]; then
  fetch "$HCNETSDK_ZIP_URL"
else
  signed="$(sign_official_url)"
  [ -n "$signed" ] || { echo "Could not get a signed download URL from Hikvision" >&2; exit 1; }
  fetch "$signed"
fi

unzip -tq "$WORK/sdk.zip" >/dev/null || { echo "Downloaded file is not a valid zip (Hikvision CDN may have rejected the request)" >&2; exit 1; }
unzip -q "$WORK/sdk.zip" -d "$WORK/unzipped"
lib="$(find "$WORK/unzipped" -type f -name libhcnetsdk.so -path '*/lib/*' | head -n 1)"
[ -n "$lib" ] || { echo "libhcnetsdk.so not found inside the zip" >&2; exit 1; }
mkdir -p "$(dirname "$OUT")" && cp -r "$(dirname "$lib")" "$OUT"
echo "SDK installed to $OUT" >&2
