FROM bluenviron/mediamtx:1.21.0 AS mediamtx

FROM python:3.12-slim

# ffmpeg remuxes the SDK stream; curl/unzip fetch Hikvision's SDK at first start (see sdk/README.md)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates curl unzip fonts-dejavu-core tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY --from=mediamtx /mediamtx /usr/local/bin/mediamtx

# ctypes wrapper for HCNetSDK (MIT, see hikvision_sdk_src/LICENSE)
COPY hikvision_sdk_src /opt/hikvision-sdk/src
ENV PYTHONPATH=/opt/hikvision-sdk/src
# Filled by entrypoint.sh at runtime; mount a volume here to keep the download across restarts.
# World-writable so the container can run as any non-root UID (a fresh named volume copies these perms).
RUN mkdir -p /sdk && chmod 1777 /sdk
ENV HIKVISION_SDK_PATH=/sdk/lib
# /data: daily snapshots for the time-lapse (small; deleted after the Telegram upload)
RUN mkdir -p /data && chmod 1777 /data
VOLUME ["/sdk", "/data"]

WORKDIR /app
COPY get_sdk.sh entrypoint.sh pull_stream.py discover.py timelapse.py /app/
RUN chmod +x /app/entrypoint.sh

EXPOSE 8888 9000 9001
# mediamtx.yml is mounted (compose) or comes from a ConfigMap (k8s)
ENTRYPOINT ["/app/entrypoint.sh"]
