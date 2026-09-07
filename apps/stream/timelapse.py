#!/usr/bin/env python3
"""Dòng thời gian ảnh trong ngày + time-lapse gửi Telegram.

Trong khung giờ học (TIMELAPSE_DAYS, TIMELAPSE_START..END) cứ TIMELAPSE_INTERVAL_MINUTES một lần mở luồng từng kênh
qua RTSP nội bộ của mediamtx (on-demand), chụp một khung JPEG có in giờ, rồi đóng. Tới TIMELAPSE_SEND_AT ghép ảnh
mỗi kênh thành MP4 bằng ffmpeg, gửi Telegram (sendVideo); gửi thành công thì xoá dữ liệu ngày đó, thất bại thì giữ
lại và thử lại mỗi 30 phút. Ngày nào không chụp được khung nào thì chỉ nhắn text báo.

HTTP (cổng TIMELAPSE_PORT, mặc định 9001) cho service web:
  GET /today                          -> {"enabled": bool, "date": "YYYY-MM-DD", "window": {...}, "channels": {"7": ["08-00", ...]}}
  GET /frames/<date>/<ch>/<slot>.jpg  -> ảnh
  GET /health
"""

import datetime as dt
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import zoneinfo
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ENABLED = os.environ.get("TIMELAPSE_ENABLED", "0") == "1"
TZ = zoneinfo.ZoneInfo(os.environ.get("TIMELAPSE_TZ", "Asia/Ho_Chi_Minh"))
DAYS = {int(d) for d in os.environ.get("TIMELAPSE_DAYS", "1,2,3,4,5").split(",") if d.strip()}  # ISO: 1=Thứ Hai
START = dt.time.fromisoformat(os.environ.get("TIMELAPSE_START", "08:00"))
END = dt.time.fromisoformat(os.environ.get("TIMELAPSE_END", "17:00"))
SEND_AT = dt.time.fromisoformat(os.environ.get("TIMELAPSE_SEND_AT", "17:10"))
INTERVAL_MIN = int(os.environ.get("TIMELAPSE_INTERVAL_MINUTES", "5"))
FPS = int(os.environ.get("TIMELAPSE_FPS", "4"))
CHANNELS_ENV = os.environ.get("TIMELAPSE_CHANNELS", "")  # "2,7"; rỗng = lấy từ discover.py
DATA_DIR = Path(os.environ.get("TIMELAPSE_DATA_DIR", "/data/timelapse"))
RTSP_BASE = os.environ.get("TIMELAPSE_RTSP_BASE", "rtsp://127.0.0.1:8554")
DISCOVERY_URL = os.environ.get("TIMELAPSE_DISCOVERY_URL", "http://127.0.0.1:9000/channels")
PORT = int(os.environ.get("TIMELAPSE_PORT", "9001"))
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_API = os.environ.get("TELEGRAM_API_BASE", "https://api.telegram.org").rstrip("/")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
CAPTURE_TIMEOUT = 60
RETRY_SEND_SECONDS = 30 * 60
KEEP_PENDING_DAYS = 3
FAIL_ALERT_AFTER = 3

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SLOT_RE = re.compile(r"^\d{2}-\d{2}$")


def log(msg: str) -> None:
    print(f"[timelapse] {msg}", file=sys.stderr, flush=True)


def now_local() -> dt.datetime:
    return dt.datetime.now(TZ)


def in_window(now: dt.datetime) -> bool:
    return now.isoweekday() in DAYS and START <= now.time() < END


def slot_of(now: dt.datetime) -> str:
    minute = (now.minute // INTERVAL_MIN) * INTERVAL_MIN
    return f"{now.hour:02d}-{minute:02d}"


def channels() -> list[int]:
    if CHANNELS_ENV.strip():
        return [int(c) for c in CHANNELS_ENV.split(",") if c.strip()]
    with urllib.request.urlopen(DISCOVERY_URL, timeout=5) as res:
        return [c["channel"] for c in json.load(res)["channels"]]


# ---------- chụp ----------
def capture(channel: int, day: str, slot: str, now: dt.datetime) -> bool:
    out_dir = DATA_DIR / day / f"ch{channel}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{slot}.jpg"
    stamp = now.strftime("%d/%m %H\\:%M")  # drawtext cần escape dấu hai chấm
    vf = (f"drawtext=fontfile={FONT}:text='{stamp}':x=16:y=16:fontsize=h/22:fontcolor=white:"
          f"box=1:boxcolor=black@0.5:boxborderw=8")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-rtsp_transport", "tcp", "-i", f"{RTSP_BASE}/ch{channel}",
           "-frames:v", "1", "-vf", vf, "-q:v", "3", str(out)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=CAPTURE_TIMEOUT)
    except subprocess.TimeoutExpired:
        log(f"ch{channel} {slot}: quá {CAPTURE_TIMEOUT}s không có khung hình")
        out.unlink(missing_ok=True)
        return False
    if result.returncode != 0 or not out.exists():
        log(f"ch{channel} {slot}: ffmpeg lỗi: {result.stderr.strip()[-200:]}")
        out.unlink(missing_ok=True)
        return False
    return True


# ---------- ghép + gửi ----------
def build_video(day_dir: Path, channel: int) -> Path | None:
    frames_dir = day_dir / f"ch{channel}"
    frames = sorted(frames_dir.glob("*.jpg"))
    if not frames:
        return None
    out = day_dir / f"ch{channel}.mp4"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-framerate", str(FPS), "-pattern_type", "glob", "-i", str(frames_dir / "*.jpg"),
           "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", str(out)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg ghép ch{channel} lỗi: {result.stderr.strip()[-300:]}")
    return out


def telegram_call(method: str, fields: dict, file_field: str | None = None, file_path: Path | None = None) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError("thiếu TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")
    boundary = f"----{uuid.uuid4().hex}"
    body = bytearray()
    for key, value in {"chat_id": TELEGRAM_CHAT_ID, **fields}.items():
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode()
    if file_field and file_path:
        mime = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; "
                 f"filename=\"{file_path.name}\"\r\nContent-Type: {mime}\r\n\r\n").encode()
        body += file_path.read_bytes() + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"{TELEGRAM_API}/bot{TELEGRAM_TOKEN}/{method}", data=bytes(body), method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=120) as res:
        payload = json.load(res)
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram {method}: {payload}")


def send_text(text: str) -> None:
    try:
        telegram_call("sendMessage", {"text": text})
    except Exception as err:  # cảnh báo phụ, không được làm chết vòng lặp chính
        log(f"không gửi được text Telegram: {err}")


def channel_name(channel: int) -> str:
    try:
        with urllib.request.urlopen(DISCOVERY_URL, timeout=5) as res:
            for c in json.load(res)["channels"]:
                if c["channel"] == channel:
                    return c["name"]
    except Exception:
        pass
    return f"Cam {channel:02d}"


def send_day(day_dir: Path) -> bool:
    """Ghép và gửi từng kênh của một ngày. Trả True khi mọi kênh đã gửi xong (và đã xoá)."""
    day = day_dir.name
    pretty = dt.date.fromisoformat(day).strftime("%d/%m/%Y")
    remaining = False
    for frames_dir in sorted(p for p in day_dir.iterdir() if p.is_dir() and p.name.startswith("ch")):
        channel = int(frames_dir.name[2:])
        count = len(list(frames_dir.glob("*.jpg")))
        if count == 0:
            shutil.rmtree(frames_dir, ignore_errors=True)
            continue
        try:
            video = build_video(day_dir, channel)
            caption = (f"{channel_name(channel)} · {pretty}\n{count} khung, {START:%H:%M} đến {END:%H:%M}, "
                       f"mỗi {INTERVAL_MIN} phút")
            telegram_call("sendVideo", {"caption": caption, "supports_streaming": "true"}, "video", video)
            log(f"{day} ch{channel}: đã gửi Telegram ({count} khung), xoá dữ liệu")
            shutil.rmtree(frames_dir, ignore_errors=True)
            video.unlink(missing_ok=True)
        except Exception as err:
            log(f"{day} ch{channel}: gửi lỗi, giữ lại thử sau: {err}")
            remaining = True
    if remaining:
        (day_dir / ".last_attempt").write_text(str(time.time()))
        return False
    shutil.rmtree(day_dir, ignore_errors=True)
    return True


def days_to_send(now: dt.datetime) -> list[Path]:
    """Ngày cũ còn sót, hoặc hôm nay khi đã tới giờ gửi; tôn trọng nghỉ 30 phút giữa hai lần thử."""
    if not DATA_DIR.exists():
        return []
    today = now.date().isoformat()
    due = []
    for day_dir in sorted(p for p in DATA_DIR.iterdir() if p.is_dir() and DATE_RE.match(p.name)):
        if day_dir.name == today and now.time() < SEND_AT:
            continue
        marker = day_dir / ".last_attempt"
        if marker.exists() and time.time() - float(marker.read_text() or 0) < RETRY_SEND_SECONDS:
            continue
        due.append(day_dir)
    return due


def cleanup_stale(now: dt.datetime) -> None:
    if not DATA_DIR.exists():
        return
    for day_dir in DATA_DIR.iterdir():
        if not (day_dir.is_dir() and DATE_RE.match(day_dir.name)):
            continue
        age = (now.date() - dt.date.fromisoformat(day_dir.name)).days
        if age > KEEP_PENDING_DAYS:
            log(f"{day_dir.name}: quá {KEEP_PENDING_DAYS} ngày không gửi được, xoá")
            send_text(f"Time-lapse ngày {day_dir.name} không gửi được sau {KEEP_PENDING_DAYS} ngày, đã xoá.")
            shutil.rmtree(day_dir, ignore_errors=True)


# ---------- vòng lặp ----------
def scheduler() -> None:
    last_slot = None
    failures = 0
    alerted = False
    empty_day_reported = set()
    log(f"bật: {sorted(DAYS)} {START:%H:%M}-{END:%H:%M} mỗi {INTERVAL_MIN} phút, gửi {SEND_AT:%H:%M} ({TZ.key})")
    while True:
        try:
            now = now_local()
            if in_window(now):
                slot = slot_of(now)
                if slot != last_slot:
                    chans = channels()
                    if not chans:
                        # discover.py chưa dò xong (pod vừa khởi động): chưa đánh dấu slot, vòng sau thử lại
                        log(f"{slot}: chưa có danh sách kênh, chờ discover")
                        time.sleep(20)
                        continue
                    last_slot = slot
                    day = now.date().isoformat()
                    ok = 0
                    for ch in chans:
                        if capture(ch, day, slot, now):
                            ok += 1
                    log(f"{day} {slot}: chụp được {ok}/{len(chans)} kênh")
                    if ok == 0:
                        failures += 1
                        if failures >= FAIL_ALERT_AFTER and not alerted:
                            alerted = True
                            send_text(f"Không chụp được camera {failures} lần liên tiếp ({day} {slot}). Đầu ghi offline?")
                    else:
                        failures, alerted = 0, False
            for day_dir in days_to_send(now):
                had_frames = any(day_dir.glob("ch*/*.jpg"))
                if not had_frames:
                    if day_dir.name not in empty_day_reported:
                        empty_day_reported.add(day_dir.name)
                        send_text(f"Ngày {day_dir.name} không chụp được khung hình nào, không có time-lapse.")
                    shutil.rmtree(day_dir, ignore_errors=True)
                    continue
                send_day(day_dir)
            cleanup_stale(now)
        except Exception as err:  # lỗi một vòng không được giết scheduler; log và đi tiếp
            log(f"lỗi vòng lặp: {type(err).__name__}: {err}")
        time.sleep(20)


# ---------- HTTP cho web ----------
class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            return self._json(200, {"ok": True})
        if self.path == "/today":
            now = now_local()
            day = now.date().isoformat()
            chans: dict[str, list[str]] = {}
            day_dir = DATA_DIR / day
            if day_dir.exists():
                for frames_dir in sorted(p for p in day_dir.iterdir() if p.is_dir() and p.name.startswith("ch")):
                    chans[frames_dir.name[2:]] = sorted(f.stem for f in frames_dir.glob("*.jpg"))
            return self._json(200, {
                "enabled": ENABLED, "date": day, "now": now.strftime("%H:%M"), "channels": chans,
                "window": {"days": sorted(DAYS), "start": START.strftime("%H:%M"), "end": END.strftime("%H:%M"),
                           "intervalMinutes": INTERVAL_MIN, "sendAt": SEND_AT.strftime("%H:%M"),
                           "telegram": bool(TELEGRAM_TOKEN and TELEGRAM_CHAT_ID)},
            })
        m = re.match(r"^/frames/(\d{4}-\d{2}-\d{2})/ch(\d+)/(\d{2}-\d{2})\.jpg$", self.path)
        if m:
            path = DATA_DIR / m.group(1) / f"ch{m.group(2)}" / f"{m.group(3)}.jpg"
            if not path.exists():
                return self._json(404, {"error": "not found"})
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "private, max-age=3600")
            self.end_headers()
            self.wfile.write(data)
            return
        self._json(404, {"error": "not found"})

    def log_message(self, format, *args) -> None:
        pass


def main() -> None:
    if ENABLED:
        threading.Thread(target=scheduler, daemon=True).start()
    else:
        log("tắt (TIMELAPSE_ENABLED != 1), chỉ phục vụ /today")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
