#!/usr/bin/env python3
"""Dò kênh mà tài khoản được xem và phục vụ danh sách qua HTTP cho service web.

Chạy cạnh mediamtx trong container stream. Lúc khởi động (và mỗi REFRESH_SECONDS) login đầu ghi một lần,
thử start_preview từng kênh: kênh không có quyền trả lỗi mã 2 (NET_DVR_NOENOUGHPRI) ngay, kênh được phép thì
dừng preview luôn. Tên kênh lấy bằng NET_DVR_GET_PICCFG_V40, không lấy được thì "Cam N".

Việc dò chạy trong tiến trình con và thoát bằng os._exit vì NET_DVR_Logout của SDK crash (SIGBUS).

GET /channels  -> {"channels": [{"channel": 2, "name": "Camera 02"}, ...], "updated_at": <epoch>, "probing": bool}
POST /refresh  -> dò lại ngay
GET /health
"""

import ctypes
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NET_DVR_GET_PICCFG_V40 = 6179
NET_DVR_PICCFG_V40_SIZE = 77140  # sizeof(NET_DVR_PICCFG_V40) trong HCNetSDK.h V6.1.9.48, linux64
NET_DVR_NOENOUGHPRI = 2
CHANNEL_NAME_LEN = 32


def log(msg: str) -> None:
    print(f"[discover] {msg}", file=sys.stderr, flush=True)


class NET_DVR_PICCFG_V40(ctypes.Structure):
    # Chỉ cần dwSize và sChanName ở đầu struct, phần còn lại giữ đúng kích thước
    _fields_ = [
        ("dwSize", ctypes.c_uint32),
        ("sChanName", ctypes.c_ubyte * CHANNEL_NAME_LEN),
        ("byRes", ctypes.c_ubyte * (NET_DVR_PICCFG_V40_SIZE - 4 - CHANNEL_NAME_LEN)),
    ]


def channel_name(device, channel: int) -> str | None:
    cfg = NET_DVR_PICCFG_V40()
    cfg.dwSize = NET_DVR_PICCFG_V40_SIZE
    returned = ctypes.c_uint32(0)
    ok = device._sdk._sdk.NET_DVR_GetDVRConfig(
        device.user_id, NET_DVR_GET_PICCFG_V40, channel,
        ctypes.byref(cfg), NET_DVR_PICCFG_V40_SIZE, ctypes.byref(returned),
    )
    if not ok:
        return None
    raw = bytes(cfg.sChanName).split(b"\x00", 1)[0]
    name = raw.decode("utf-8", errors="ignore").strip()
    return name or None


def probe() -> list[dict]:
    """Chạy trong tiến trình con: login, thử từng kênh, in JSON ra stdout rồi thoát thẳng."""
    from hikvision_sdk import HCNetSDK
    from hikvision_sdk.constants import LINK_MODE_TCP, STREAM_TYPE_SUB
    from hikvision_sdk.exceptions import PreviewError

    host = os.environ.get("HIK_HOST") or os.environ["HIK_DOMAIN"]
    port = int(os.environ.get("HIK_SDK_PORT", "8000"))
    user = os.environ["HIK_USER"]
    password = os.environ["HIK_PASS"]

    sdk = HCNetSDK()
    sdk.init()
    device = sdk.login(host, port, user, password)
    first = device.start_channel or 1
    total = device.channel_count + device.ip_channel_count
    log(f"login OK, thử kênh {first}..{first + total - 1}")

    def on_data(handle, data_type, data):
        pass

    available = []
    for channel in range(first, first + total):
        try:
            handle = device.start_preview(channel=channel, stream_type=STREAM_TYPE_SUB,
                                          link_mode=LINK_MODE_TCP, callback=on_data, blocked=True)
        except PreviewError as err:
            if err.error_code != NET_DVR_NOENOUGHPRI:
                log(f"kênh {channel}: bỏ qua ({err})")
            continue
        device.stop_preview(handle)
        name = channel_name(device, channel) or f"Cam {channel:02d}"
        available.append({"channel": channel, "name": name})
        log(f"kênh {channel}: OK ({name})")
    return available


class State:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.channels: list[dict] = []
        self.updated_at: float | None = None
        self.probing = False
        self.wake = threading.Event()

    def snapshot(self) -> dict:
        with self.lock:
            return {"channels": self.channels, "updated_at": self.updated_at, "probing": self.probing}


def run_probe_subprocess(state: State) -> None:
    with state.lock:
        state.probing = True
    try:
        result = subprocess.run([sys.executable, __file__, "--probe"], capture_output=True, text=True, timeout=600)
        sys.stderr.write(result.stderr)
        if result.returncode != 0:
            log(f"dò kênh thất bại, mã {result.returncode}")
            return
        channels = json.loads(result.stdout.strip().splitlines()[-1])
        with state.lock:
            state.channels = channels
            state.updated_at = time.time()
        log(f"có {len(channels)} kênh: {[c['channel'] for c in channels]}")
    except subprocess.TimeoutExpired:
        log("dò kênh quá 10 phút, bỏ")
    finally:
        with state.lock:
            state.probing = False


def refresh_loop(state: State, interval: int) -> None:
    while True:
        run_probe_subprocess(state)
        # Thất bại (vd đầu ghi offline) thì thử lại sau 1 phút thay vì chờ cả chu kỳ
        wait = interval if state.snapshot()["updated_at"] else 60
        state.wake.wait(timeout=wait)
        state.wake.clear()


def make_handler(state: State):
    class Handler(BaseHTTPRequestHandler):
        def _json(self, code: int, payload: dict) -> None:
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path == "/channels":
                self._json(200, state.snapshot())
            elif self.path == "/health":
                self._json(200, {"ok": True})
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self) -> None:
            if self.path == "/refresh":
                state.wake.set()
                self._json(202, {"ok": True})
            else:
                self._json(404, {"error": "not found"})

        def log_message(self, format, *args) -> None:
            pass  # không log từng request health/channels

    return Handler


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--probe":
        try:
            print(json.dumps(probe()), flush=True)
            os._exit(0)  # không logout/cleanup: SDK crash ở NET_DVR_Logout
        except Exception as err:
            log(f"lỗi dò kênh: {type(err).__name__}: {err}")
            os._exit(1)

    state = State()
    interval = int(os.environ.get("DISCOVER_REFRESH_SECONDS", "21600"))
    threading.Thread(target=refresh_loop, args=(state, interval), daemon=True).start()
    port = int(os.environ.get("DISCOVER_PORT", "9000"))
    log(f"phục vụ /channels trên cổng {port}, dò lại mỗi {interval}s")
    ThreadingHTTPServer(("0.0.0.0", port), make_handler(state)).serve_forever()


if __name__ == "__main__":
    main()
