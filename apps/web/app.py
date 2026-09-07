#!/usr/bin/env python3
"""Web xem cam (SPA + PWA): login mật khẩu, cookie phiên ký HMAC, danh sách kênh tự dò, proxy HLS về mediamtx.

Env: CAM_PASSWORD (mật khẩu gia đình), SESSION_SECRET (khoá ký cookie),
HLS_ORIGIN (mặc định http://stream:8888), DISCOVERY_ORIGIN (mặc định http://stream:9000), PORT (mặc định 8000).
"""

import asyncio
import hashlib
import hmac
import logging
import os
import re
import time
from pathlib import Path

from aiohttp import ClientError, ClientSession, ClientTimeout, web

log = logging.getLogger("web")

STATIC_DIR = Path(__file__).parent / "static"
COOKIE_NAME = "cam_session"
SESSION_TTL_SECONDS = 30 * 24 * 3600
# App shell, manifest, service worker và icon không cần cookie; dữ liệu (/api, /hls) thì cần
PUBLIC_PATHS = {"/", "/index.html", "/manifest.webmanifest", "/sw.js", "/api/login", "/api/session", "/api/health"}
PUBLIC_PREFIXES = ("/static/",)
HLS_PATH_RE = re.compile(r"^ch\d+/[A-Za-z0-9_.-]+$")


def sign(secret: str, data: str) -> str:
    return hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()


def create_session(secret: str) -> str:
    exp = str(int(time.time()) + SESSION_TTL_SECONDS)
    return f"{exp}.{sign(secret, exp)}"


def verify_session(secret: str, value: str | None) -> bool:
    if not value or "." not in value:
        return False
    exp, sig = value.split(".", 1)
    if not exp.isdigit() or int(exp) < time.time():
        return False
    return hmac.compare_digest(sig, sign(secret, exp))


def is_https(request: web.Request) -> bool:
    return request.headers.get("X-Forwarded-Proto", request.scheme) == "https"


def set_session_cookie(response: web.StreamResponse, request: web.Request, value: str, max_age: int) -> None:
    response.set_cookie(COOKIE_NAME, value, max_age=max_age, path="/", httponly=True,
                        samesite="Lax", secure=is_https(request))


def has_session(request: web.Request) -> bool:
    return verify_session(request.app["session_secret"], request.cookies.get(COOKIE_NAME))


@web.middleware
async def auth_middleware(request: web.Request, handler):
    if request.path in PUBLIC_PATHS or request.path.startswith(PUBLIC_PREFIXES) or has_session(request):
        return await handler(request)
    raise web.HTTPUnauthorized()


async def index_page(request: web.Request) -> web.FileResponse:
    return web.FileResponse(STATIC_DIR / "index.html")


async def manifest(request: web.Request) -> web.FileResponse:
    return web.FileResponse(STATIC_DIR / "manifest.webmanifest",
                            headers={"Content-Type": "application/manifest+json"})


async def service_worker(request: web.Request) -> web.FileResponse:
    # Service-Worker-Allowed cho phép scope "/" dù file nằm ở /sw.js; no-store để bản mới nhận ngay
    return web.FileResponse(STATIC_DIR / "sw.js", headers={"Cache-Control": "no-store"})


async def api_health(request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


async def api_session(request: web.Request) -> web.Response:
    if has_session(request):
        return web.json_response({"authenticated": True})
    return web.json_response({"authenticated": False}, status=401)


async def api_login(request: web.Request) -> web.Response:
    body = await request.json()
    password = str(body.get("password", ""))
    if not hmac.compare_digest(password, request.app["cam_password"]):
        await asyncio.sleep(0.8)  # làm chậm cho khó dò mật khẩu
        return web.json_response({"error": "Sai mật khẩu"}, status=401)
    response = web.json_response({"authenticated": True})
    set_session_cookie(response, request, create_session(request.app["session_secret"]), SESSION_TTL_SECONDS)
    return response


async def api_logout(request: web.Request) -> web.Response:
    response = web.json_response({"authenticated": False})
    set_session_cookie(response, request, "", 0)
    return response


async def api_cameras(request: web.Request) -> web.Response:
    """Danh sách kênh tài khoản xem được, do discover.py trong service stream dò ra."""
    client: ClientSession = request.app["client"]
    try:
        async with client.get(f"{request.app['discovery_origin']}/channels") as upstream:
            if upstream.status != 200:
                raise web.HTTPBadGateway(text=f"discovery trả {upstream.status}")
            return web.json_response(await upstream.json())
    except ClientError as err:
        raise web.HTTPBadGateway(text=f"không gọi được discovery: {err}") from err


async def hls_proxy(request: web.Request) -> web.StreamResponse:
    """Chuyển tiếp playlist và segment HLS từ mediamtx, giữ nguyên path và query (?session=...)."""
    path = request.match_info["path"]
    if not HLS_PATH_RE.match(path):
        raise web.HTTPNotFound()
    upstream_url = f"{request.app['hls_origin']}/{path}"
    if request.query_string:
        upstream_url += f"?{request.query_string}"

    client: ClientSession = request.app["client"]
    async with client.get(upstream_url) as upstream:
        response = web.StreamResponse(status=upstream.status)
        content_type = upstream.headers.get("Content-Type")
        if content_type:
            response.content_type = content_type
        response.headers["Cache-Control"] = "no-store"
        await response.prepare(request)
        async for chunk in upstream.content.iter_chunked(64 * 1024):
            await response.write(chunk)
        await response.write_eof()
        return response


async def on_startup(app: web.Application) -> None:
    app["client"] = ClientSession(timeout=ClientTimeout(total=30))


async def on_cleanup(app: web.Application) -> None:
    await app["client"].close()


def create_app() -> web.Application:
    cam_password = os.environ.get("CAM_PASSWORD")
    session_secret = os.environ.get("SESSION_SECRET")
    if not cam_password or not session_secret:
        raise RuntimeError("Thiếu CAM_PASSWORD hoặc SESSION_SECRET trong env")

    app = web.Application(middlewares=[auth_middleware])
    app["cam_password"] = cam_password
    app["session_secret"] = session_secret
    app["hls_origin"] = os.environ.get("HLS_ORIGIN", "http://stream:8888").rstrip("/")
    app["discovery_origin"] = os.environ.get("DISCOVERY_ORIGIN", "http://stream:9000").rstrip("/")
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    app.router.add_get("/", index_page)
    app.router.add_get("/manifest.webmanifest", manifest)
    app.router.add_get("/sw.js", service_worker)
    app.router.add_get("/api/health", api_health)
    app.router.add_get("/api/session", api_session)
    app.router.add_post("/api/login", api_login)
    app.router.add_post("/api/logout", api_logout)
    app.router.add_get("/api/cameras", api_cameras)
    app.router.add_get("/hls/{path:.*}", hls_proxy)
    app.router.add_static("/static/", STATIC_DIR)
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    web.run_app(create_app(), host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
