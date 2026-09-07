#!/usr/bin/env python3
"""Kéo stream thô (MPEG-PS, header IMKH) từ đầu ghi Hikvision qua cổng SDK, bơm vào ffmpeg,
ffmpeg remux (không encode lại) rồi đẩy RTSP vào mediamtx.

Được mediamtx gọi qua runOnDemand khi có người xem đầu tiên; mediamtx gửi SIGINT khi hết người xem.
Không gọi logout/cleanup của SDK vì nó crash (SIGBUS) ở NET_DVR_Logout; thoát thẳng bằng os._exit,
đầu ghi tự dọn phiên khi TCP đóng. Stream đứng quá STALL_SECONDS thì thoát mã 1 để mediamtx chạy lại.
"""

import os
import signal
import subprocess
import sys
import threading
import time

from hikvision_sdk import HCNetSDK
from hikvision_sdk.constants import LINK_MODE_TCP, STREAM_TYPE_MAIN, STREAM_TYPE_SUB

NET_DVR_SYSHEAD = 1
NET_DVR_STREAMDATA = 2


def log(msg: str) -> None:
    print(f"[pull_stream] {msg}", file=sys.stderr, flush=True)


def main() -> None:
    host = os.environ.get("HIK_HOST") or os.environ["HIK_DOMAIN"]
    port = int(os.environ.get("HIK_SDK_PORT", "8000"))
    user = os.environ["HIK_USER"]
    password = os.environ["HIK_PASS"]
    # mediamtx truyền MTX_PATH (vd "ch5") cho lệnh runOnDemand; số kênh lấy từ tên path
    mtx_path = os.environ["MTX_PATH"]
    channel = int(mtx_path.removeprefix("ch"))
    sub = os.environ.get("HIK_SUB", "0") == "1"
    stall_seconds = int(os.environ.get("STALL_SECONDS", "15"))
    publish_url = f"{os.environ['MTX_PUBLISH_BASE'].rstrip('/')}/{mtx_path}"

    ffmpeg = subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-loglevel", "warning",
         "-f", "mpeg", "-i", "pipe:0",
         "-c", "copy", "-f", "rtsp", "-rtsp_transport", "tcp", publish_url],
        stdin=subprocess.PIPE,
    )
    out = ffmpeg.stdin

    state = {"last_data": time.monotonic(), "total": 0, "stopping": False}
    lock = threading.Lock()

    def shutdown(exit_code: int, reason: str) -> None:
        with lock:
            state["stopping"] = True
        log(f"dừng: {reason}")
        ffmpeg.terminate()
        try:
            ffmpeg.wait(timeout=5)
        except subprocess.TimeoutExpired:
            ffmpeg.kill()
        os._exit(exit_code)

    def on_signal(signum, _frame) -> None:
        shutdown(0, f"nhận tín hiệu {signal.Signals(signum).name} (hết người xem)")

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    def on_data(handle: int, data_type: int, data: bytes) -> None:
        if data_type not in (NET_DVR_SYSHEAD, NET_DVR_STREAMDATA):
            return
        with lock:
            if state["stopping"]:
                return
            state["last_data"] = time.monotonic()
            state["total"] += len(data)
        try:
            out.write(data)
            out.flush()
        except (BrokenPipeError, ValueError):
            with lock:
                if state["stopping"]:
                    return
            log("ffmpeg đóng stdin, thoát để chạy lại")
            os._exit(1)

    sdk = HCNetSDK()
    sdk.init()
    log(f"login {host}:{port} as {user} channel={channel} {'sub' if sub else 'main'}")
    device = sdk.login(host, port, user, password)
    log(f"login OK serial={device.serial_number} channels={device.channel_count}+{device.ip_channel_count} ip")

    handle = device.start_preview(
        channel=channel,
        stream_type=STREAM_TYPE_SUB if sub else STREAM_TYPE_MAIN,
        link_mode=LINK_MODE_TCP,
        callback=on_data,
        blocked=True,
    )
    log(f"preview started handle={handle}, đẩy vào {publish_url.split('@')[-1]}")

    report_every = 60
    next_report = time.monotonic() + report_every
    while True:
        time.sleep(1)
        if ffmpeg.poll() is not None:
            shutdown(1, f"ffmpeg thoát mã {ffmpeg.returncode}")
        with lock:
            idle = time.monotonic() - state["last_data"]
            total = state["total"]
        if idle > stall_seconds:
            shutdown(1, f"không có dữ liệu {idle:.0f}s")
        if time.monotonic() >= next_report:
            log(f"đang chạy, tổng {total / 1e6:.1f} MB")
            next_report += report_every


if __name__ == "__main__":
    try:
        main()
    except Exception as err:  # log rồi thoát mã 1 để mediamtx chạy lại; không logout vì SDK crash ở đó
        log(f"lỗi: {type(err).__name__}: {err}")
        os._exit(1)
