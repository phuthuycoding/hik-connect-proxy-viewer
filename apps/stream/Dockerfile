FROM bluenviron/mediamtx:1.21.0 AS mediamtx

FROM python:3.12-slim

# ffmpeg remuxes the SDK stream; curl/unzip fetch Hikvision's SDK at first start (see sdk/README.md)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates curl unzip \
    && rm -rf /var/lib/apt/lists/*

COPY --from=mediamtx /mediamtx /usr/local/bin/mediamtx

# ctypes wrapper for HCNetSDK (MIT, see hikvision_sdk_src/LICENSE)
COPY hikvision_sdk_src /opt/hikvision-sdk/src
ENV PYTHONPATH=/opt/hikvision-sdk/src
# Filled by entrypoint.sh at runtime; mount a volume here to keep the download across restarts
ENV HIKVISION_SDK_PATH=/sdk/lib
VOLUME ["/sdk"]

WORKDIR /app
COPY get_sdk.sh entrypoint.sh pull_stream.py discover.py /app/
RUN chmod +x /app/entrypoint.sh

EXPOSE 8888 9000
# mediamtx.yml is mounted (compose) or comes from a ConfigMap (k8s)
ENTRYPOINT ["/app/entrypoint.sh"]
