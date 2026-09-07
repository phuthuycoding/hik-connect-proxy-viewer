#!/usr/bin/env python3
"""Xem camera Hikvision qua Hik-Connect DDNS bằng ffplay.

Cách dùng:
    python3 view_cam.py --domain <ten-mien-hik-connect> --user <user> --password <pass> --channel 1
    python3 view_cam.py --host 1.2.3.4 --rtsp-port 554 --user <user> --password <pass> --channel 1 --sub

Thông tin đăng nhập có thể để trong file .env (xem .env.example) thay vì gõ trên dòng lệnh.
"""

import argparse
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

HIK_CONNECT_DDNS_BASE = "https://www.hik-connect.com/"
HIK_CONNECT_LOGIN_MARKER = "/views/login/"
DEFAULT_RTSP_PORT = 554
DEFAULT_SOCKET_TIMEOUT_US = 10_000_000  # 10 giây, đơn vị micro giây theo option -timeout của ffmpeg


def load_dotenv(path: str) -> None:
    """Nạp KEY=VALUE từ file .env vào os.environ, không ghi đè biến đã có."""
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def resolve_hik_connect_domain(domain: str, timeout: float = 15.0) -> tuple[str, int]:
    """Hỏi Hik-Connect DDNS xem tên miền trỏ về IP:port HTTP nào.

    Hik-Connect trả 302 về http://<ip-public>:<http-port> nếu tên miền hợp lệ,
    và 302 về trang login nếu tên miền không tồn tại hoặc chưa bật DDNS.
    """
    url = HIK_CONNECT_DDNS_BASE + urllib.parse.quote(domain, safe="")
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=timeout) as response:
            raise RuntimeError(
                f"Hik-Connect không redirect (HTTP {response.status}); "
                "không xác định được IP của thiết bị"
            )
    except urllib.error.HTTPError as err:
        if err.code not in (301, 302, 303, 307, 308):
            raise
        location = err.headers.get("Location")

    if not location:
        raise RuntimeError("Hik-Connect redirect nhưng không có header Location")
    if HIK_CONNECT_LOGIN_MARKER in location:
        raise RuntimeError(
            f"Tên miền '{domain}' không tồn tại trên Hik-Connect hoặc thiết bị chưa bật DDNS "
            f"(bị chuyển về trang login: {location})"
        )

    parts = urllib.parse.urlsplit(location)
    if not parts.hostname:
        raise RuntimeError(f"Không đọc được host từ Location: {location}")
    http_port = parts.port or (443 if parts.scheme == "https" else 80)
    return parts.hostname, http_port


def build_rtsp_url(host: str, rtsp_port: int, user: str, password: str, channel: int, sub: bool) -> str:
    # Hikvision: ID = <kênh><01 luồng chính | 02 luồng phụ>, ví dụ kênh 3 luồng phụ = 302
    stream_id = channel * 100 + (2 if sub else 1)
    cred = f"{urllib.parse.quote(user, safe='')}:{urllib.parse.quote(password, safe='')}"
    return f"rtsp://{cred}@{host}:{rtsp_port}/Streaming/Channels/{stream_id}"


def mask_password(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    netloc = f"{parts.username}:****@{parts.hostname}:{parts.port}"
    return urllib.parse.urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def probe(rtsp_url: str) -> str:
    """Thử kết nối bằng ffprobe trước, vì ffplay trả exit 0 kể cả khi không mở được stream."""
    if shutil.which("ffprobe") is None:
        raise RuntimeError("Không tìm thấy ffprobe. Cài bằng: brew install ffmpeg")
    cmd = [
        "ffprobe",
        "-hide_banner",
        "-v", "error",
        "-rtsp_transport", "tcp",
        "-timeout", str(DEFAULT_SOCKET_TIMEOUT_US),
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height",
        "-of", "default=noprint_wrappers=1",
        rtsp_url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        detail = result.stderr.strip().replace(rtsp_url, mask_password(rtsp_url))
        raise RuntimeError(f"Không kết nối được RTSP (ffprobe exit {result.returncode}):\n{detail}")
    return result.stdout.strip()


def play(rtsp_url: str, title: str) -> int:
    if shutil.which("ffplay") is None:
        raise RuntimeError("Không tìm thấy ffplay. Cài bằng: brew install ffmpeg")
    cmd = [
        "ffplay",
        "-hide_banner",
        "-loglevel", "warning",
        "-rtsp_transport", "tcp",
        "-timeout", str(DEFAULT_SOCKET_TIMEOUT_US),
        "-fflags", "nobuffer",
        "-flags", "low_delay",
        "-framedrop",
        "-window_title", title,
        rtsp_url,
    ]
    return subprocess.call(cmd)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Xem camera Hikvision qua Hik-Connect DDNS")
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--domain", default=os.environ.get("HIK_DOMAIN"),
                        help="Tên miền Hik-Connect DDNS (mặc định: env HIK_DOMAIN)")
    target.add_argument("--host", default=os.environ.get("HIK_HOST"),
                        help="IP/hostname của đầu ghi, bỏ qua bước hỏi Hik-Connect (mặc định: env HIK_HOST)")
    parser.add_argument("--rtsp-port", type=int, default=int(os.environ.get("HIK_RTSP_PORT", DEFAULT_RTSP_PORT)),
                        help=f"Port RTSP đã mở ở trường (mặc định: env HIK_RTSP_PORT hoặc {DEFAULT_RTSP_PORT})")
    parser.add_argument("--user", default=os.environ.get("HIK_USER"), help="User đầu ghi (mặc định: env HIK_USER)")
    parser.add_argument("--password", default=os.environ.get("HIK_PASS"), help="Mật khẩu (mặc định: env HIK_PASS)")
    parser.add_argument("--channel", type=int, default=int(os.environ.get("HIK_CHANNEL", 1)),
                        help="Số kênh camera trên đầu ghi (mặc định: env HIK_CHANNEL hoặc 1)")
    parser.add_argument("--sub", action="store_true", help="Dùng luồng phụ (nhẹ hơn, hợp mạng yếu)")
    parser.add_argument("--print-url", action="store_true",
                        help="Chỉ in RTSP URL (dùng cho VLC) rồi thoát, không mở ffplay")
    args = parser.parse_args()

    missing = [name for name, value in (("--user", args.user), ("--password", args.password)) if not value]
    if not args.domain and not args.host:
        missing.append("--domain hoặc --host")
    if missing:
        parser.error("thiếu: " + ", ".join(missing))
    return args


def main() -> int:
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    args = parse_args()

    if args.host:
        host = args.host
    elif "." in args.domain:
        # Bí danh Hik-Connect DDNS chỉ gồm chữ thường, số, gạch ngang.
        # Có dấu chấm nghĩa là hostname DNS thường (dịch vụ DDNS bất kỳ), kết nối thẳng.
        host = args.domain
        print(f"'{args.domain}' là hostname DNS thường, kết nối trực tiếp")
    else:
        host, http_port = resolve_hik_connect_domain(args.domain)
        print(f"Hik-Connect DDNS: {args.domain} -> {host} (HTTP port {http_port})")

    rtsp_url = build_rtsp_url(host, args.rtsp_port, args.user, args.password, args.channel, args.sub)

    if args.print_url:
        print(rtsp_url)
        return 0

    print(f"Đang kiểm tra: {mask_password(rtsp_url)}")
    print(probe(rtsp_url))
    print("Đang mở ffplay. Đóng cửa sổ hoặc bấm q để thoát.")
    return play(rtsp_url, title=f"Camera kênh {args.channel}{' (sub)' if args.sub else ''}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as err:
        print(f"Lỗi: {err}", file=sys.stderr)
        sys.exit(1)
