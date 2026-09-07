#!/bin/sh
# 1) Hikvision SDK is proprietary and not shipped in the image: fetch it into /sdk on first start.
# 2) discover.py (channel list API) and timelapse.py (daily snapshots -> Telegram) run in the background,
#    mediamtx stays PID 1.
set -e

if [ ! -f /sdk/lib/libhcnetsdk.so ]; then
  OUT=/sdk/lib SRC_DIR=/sdk/src sh /app/get_sdk.sh
fi

python3 /app/discover.py &
python3 /app/timelapse.py &
exec /usr/local/bin/mediamtx /mediamtx.yml
