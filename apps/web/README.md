# hik-connect-proxy-viewer-web

The web app of [hik-connect-proxy-viewer](https://github.com/phuthuycoding/hik-connect-proxy-viewer):
watch Hikvision recorder channels shared through Hik-Connect in any browser or as a home-screen app (PWA).
It sits in front of `phuthuycoding/hik-connect-proxy-viewer-stream`, or install both with one Helm chart:
`oci://ghcr.io/phuthuycoding/charts/hik-connect-proxy-viewer`.

## What it does

- Login screen with one family password; a signed (HMAC) cookie remembers the device for 30 days.
- Camera grid built from `/api/cameras`: whatever channels the account may view (2, 3, ...), with names
  from the recorder. Double-tap a tile for full screen.
- PWA: manifest, service worker and icons, "Add to Home Screen" on iOS and Android.
- Proxies HLS (`/hls/ch<N>/...`) and the channel list from the stream service so only this port needs to be
  exposed (behind your ingress or reverse proxy with TLS).
- Small aiohttp app (~200 lines), runs as non-root with a read-only filesystem.

## Usage

```bash
docker run -d --name hik-web \
  -e CAM_PASSWORD=FAMILY_PASSWORD \
  -e SESSION_SECRET="$(openssl rand -hex 32)" \
  -e HLS_ORIGIN=http://hik-stream:8888 \
  -e DISCOVERY_ORIGIN=http://hik-stream:9000 \
  -p 8000:8000 \
  phuthuycoding/hik-connect-proxy-viewer-web:latest
```

| Env | Default | |
|---|---|---|
| `CAM_PASSWORD` | | required, the password typed on the login screen |
| `SESSION_SECRET` | | required, random string; changing it logs everyone out |
| `HLS_ORIGIN` | `http://stream:8888` | mediamtx HLS of the stream service |
| `DISCOVERY_ORIGIN` | `http://stream:9000` | channel list of the stream service |
| `PORT` | `8000` | listen port |

Endpoints: `/` (SPA), `/api/login`, `/api/session`, `/api/logout`, `/api/cameras`, `/api/health`,
`/hls/*`. Put it behind HTTPS; the session cookie is marked `Secure` when `X-Forwarded-Proto: https`.
Tags: `latest`, `sha-<commit>`, `X.Y.Z`.

## Disclaimer

For personal use with cameras you are authorized to watch. Not affiliated with Hikvision. MIT licensed,
provided as is.
