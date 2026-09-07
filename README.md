# hik-connect-proxy-viewer

[![Release](https://img.shields.io/github/v/release/phuthuycoding/hik-connect-proxy-viewer?label=release)](https://github.com/phuthuycoding/hik-connect-proxy-viewer/releases)
[![Docker Hub](https://img.shields.io/docker/pulls/phuthuycoding/hik-connect-proxy-viewer-stream?label=docker%20pulls)](https://hub.docker.com/r/phuthuycoding/hik-connect-proxy-viewer-stream)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Watch your kid's classroom cameras in a browser (or as a home-screen app) when the school only hands out a
Hikvision recorder account that works in the Hik-Connect app but is refused on RTSP.

**How it works.** Non-admin Hikvision accounts are often allowed to view through the proprietary **SDK port**
(8000 by default, schools usually map it elsewhere) while RTSP 554 answers `401`. Browsers and ffmpeg cannot
speak that protocol, so a small Linux service uses Hikvision's `HCNetSDK` to pull the stream and re-publish it
as HLS. The SDK output is MPEG-PS with an `IMKH` header that ffmpeg already understands, so it is remuxed,
never re-encoded.

```
[recorder] --SDK port--> apps/stream (mediamtx + pull_stream.py + discover.py) --HLS, internal--> apps/web --HTTPS--> phones
```

- **On demand.** Nobody watching = no login to the recorder. The first viewer makes mediamtx start
  `pull_stream.py` for that channel, later viewers share it, and ~35 s after the last viewer leaves it stops.
- **Auto-discovered channels.** `discover.py` logs in, tries every channel and keeps the ones the account may
  view (a 2-channel account shows 2 tiles, a 3-channel one shows 3). Names come from the recorder.
- **One family password.** Enter it once; a signed (HMAC) cookie keeps you logged in for 30 days.
- **PWA with player controls.** "Add to Home Screen" on iOS/Android opens it like an app. Each tile has
  pause/play, back-to-live, snapshot, picture-in-picture and full screen (or double-tap); a LIVE/behind badge
  shows latency. Coming back from the background re-syncs to live, and a watchdog reconnects stalled streams.
- **Nothing proprietary in git or in the images.** Hikvision's SDK is downloaded from hikvision.com when the
  stream container starts (or from a URL you host).

## Layout

```
apps/stream/   mediamtx + pull_stream.py (SDK -> ffmpeg -> RTSP publish), discover.py (channel list API), get_sdk.sh
apps/web/      app.py (aiohttp): /api/login, /api/session, /api/cameras, /hls/* proxy; static/ SPA + PWA
chart/         ONE Helm chart deploying both (stream Deployment + web Deployment, Services, Ingress, Secret);
               chart/files/mediamtx.yml is also what docker compose mounts
infra/         Caddyfile for docker compose (TLS + reverse proxy); not used on Kubernetes
tools/         view_cam.py: play RTSP directly with ffplay, only useful if your account is allowed on RTSP
.github/       Release workflow: images to Docker Hub, chart to GHCR (OCI) on git tags
```

## Requirements

- A recorder account that works in the Hik-Connect app: its DDNS hostname (or IP), the SDK port the school
  mapped (8000 by default), username and password.
- Somewhere to run two small containers with outbound internet (to reach the recorder and, once, hikvision.com
  for the SDK): Docker, or a Kubernetes cluster with an ingress controller (TLS via cert-manager optional).
- An **x86_64** node for the stream container (the Hikvision SDK is amd64 only). On Apple Silicon, docker
  compose runs it through Rosetta (`platform: linux/amd64`).

Tested with a DS-7216 series NVR, k3s v1.34 on Ubuntu 22.04 (Traefik + cert-manager), Docker Desktop on macOS,
iOS Safari and Android Chrome as viewers.

## Images and chart

| Artifact | Where |
|---|---|
| `phuthuycoding/hik-connect-proxy-viewer-stream` | Docker Hub, public, tags `latest`, `sha-<git>`, `X.Y.Z` |
| `phuthuycoding/hik-connect-proxy-viewer-web` | Docker Hub, public, same tags |
| Helm chart `hik-connect-proxy-viewer` | `oci://ghcr.io/phuthuycoding/charts/hik-connect-proxy-viewer` |

Both containers run as non-root (stream as UID 10001, web as 1001). `helm show values` on the chart lists
every option.

## Run locally (docker compose)

```bash
cp .env.example .env    # HIK_DOMAIN, HIK_SDK_PORT, HIK_USER, HIK_PASS, CAM_PASSWORD, SESSION_SECRET
docker compose up -d --build
open http://localhost:8080
docker compose logs -f stream    # SDK download, channel discovery, on-demand logins
```

First start downloads the SDK (~70 MB) into the `stream_sdk` volume. To use your own copy, put the zip or the
extracted `lib/` folder in `apps/stream/sdk/` (ignored by git) and it is picked up instead; see
`apps/stream/sdk/README.md`.

## Deploy on Kubernetes

This repository only **publishes artifacts** (images on Docker Hub, the chart on GHCR). Nothing in it knows
your cluster, domain or passwords, so it stays public and you install with one command and your own values:

```bash
helm upgrade --install cam oci://ghcr.io/phuthuycoding/charts/hik-connect-proxy-viewer --version 0.1.1 \
  --namespace cam --create-namespace \
  --set hik.domain=recorder.example.net \
  --set hik.sdkPort=8000 \
  --set hik.user=USER \
  --set hik.password=PASS \
  --set web.password=FAMILY_PASSWORD \
  --set web.sessionSecret="$(openssl rand -hex 32)" \
  --set ingress.host=cam.example.com
```

One release gives you the stream proxy Deployment, the web Deployment, their Services, the Ingress
(Traefik + cert-manager `letsencrypt-prod` by default) and one Secret. Every value above is `required`:
forget one and helm refuses to install.

To update, re-run with a newer `--version` and `--reset-then-reuse-values`: it keeps the values you set
(`--set`/`-f`) but takes the new chart defaults. Plain `--reuse-values` freezes the old defaults too, so new
chart fixes would silently not apply.

```bash
helm upgrade cam oci://ghcr.io/phuthuycoding/charts/hik-connect-proxy-viewer --version <newer> \
  --namespace cam --reset-then-reuse-values
```

Then open `https://<ingress.host>`, type the family password, and on a phone use "Add to Home Screen".

| Value | Default | Purpose |
|---|---|---|
| `hik.sub` | `"0"` | `"1"` pulls the sub stream (lighter) |
| `stream.sdkZipUrl` | `""` | fetch the Hikvision SDK from a URL you host instead of hikvision.com |
| `stream.sdkVolume` | `emptyDir: {}` | e.g. `persistentVolumeClaim.claimName` to keep the SDK across restarts |
| `stream.discoverRefreshSeconds` | `"21600"` | how often to re-probe which channels the account may view |
| `ingress.className`, `ingress.annotations`, `ingress.tlsSecretName` | Traefik / cert-manager | adapt to your ingress and TLS |
| `ingress.enabled=false` | | expose the `*-web` Service yourself |
| `stream.image.tag`, `web.image.tag` | chart appVersion | pin or use `latest` |

### Release workflow

| Trigger | Result |
|---|---|
| push to `master` | images `phuthuycoding/hik-connect-proxy-viewer-{stream,web}` tagged `latest` and `sha-<commit>` |
| push tag `vX.Y.Z` | images tagged `X.Y.Z` (+ `latest`), chart `hik-connect-proxy-viewer` version `X.Y.Z` on GHCR |

The only secrets the workflow needs are `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN`; GHCR uses the built-in
`GITHUB_TOKEN`. To publish your own fork, change `DOCKERHUB_NAMESPACE` in `.github/workflows/release.yaml`.

## Configuration reference

| Env (stream) | Default | |
|---|---|---|
| `HIK_DOMAIN` / `HIK_HOST` | | recorder DDNS hostname or IP |
| `HIK_SDK_PORT` | `8000` | SDK port as mapped by the school |
| `HIK_USER`, `HIK_PASS` | | recorder account |
| `HIK_SUB` | `0` | `1` = sub stream |
| `HCNETSDK_ZIP_URL` | | self-hosted SDK zip; empty = hikvision.com |
| `DISCOVER_REFRESH_SECONDS` | `21600` | re-probe channels |

| Env (web) | Default | |
|---|---|---|
| `CAM_PASSWORD`, `SESSION_SECRET` | | required |
| `HLS_ORIGIN` | `http://stream:8888` | mediamtx HLS |
| `DISCOVERY_ORIGIN` | `http://stream:9000` | discover.py |

## Notes and gotchas

- `NET_DVR_Logout` crashes the SDK (SIGBUS), so `pull_stream.py` and the discovery probe exit without
  logging out; the recorder drops the session when the TCP connection closes.
- HLS is fMP4 with 2 s segments (matching the recorder GOP) so iOS Safari plays it; expect 6 to 10 s latency.
- A channel the account is not allowed to view fails with `Not enough privilege (code: 2)` in the stream logs
  and is simply left out of the grid.
- The stream container runs as UID 10001. mediamtx needs one inotify instance to watch its config and Linux
  counts those per UID (`fs.inotify.max_user_instances`, often 128); as root on a busy node it died with
  `couldn't initialize inotify: too many open files`. If you still hit it, raise the sysctl on the node.

## Hướng dẫn nhanh (tiếng Việt)

1. `cp .env.example .env`, điền tài khoản đầu ghi trường cấp (tên miền, cổng SDK, user, pass), mật khẩu cho
   gia đình và `SESSION_SECRET` ngẫu nhiên.
2. `docker compose up -d --build`, mở `http://localhost:8080`, nhập mật khẩu, thêm vào màn hình chính.
3. Lên k3s: một lệnh `helm upgrade --install` ở mục "Deploy on Kubernetes" với giá trị riêng.
   Repo chỉ build image và chart, không chứa gì của cluster nhà mình.
4. Nâng cấp: chạy lại với `--version` mới và `--reset-then-reuse-values` (giữ giá trị đã set, nhận default mới).

## Disclaimer

This project was written for **personal use**: a parent watching the classroom cameras that the school
deliberately shared with them. Use it only with accounts and devices you are explicitly authorized to access,
and follow the school's rules and your local privacy laws. Do not redistribute the video, and do not share the
family password beyond your household.

The software is provided "as is", without warranty of any kind (see LICENSE). The author is not affiliated
with Hikvision. Hikvision's Device Network SDK is proprietary, is not part of this repository or of the
published images, and is downloaded by you from hikvision.com under Hikvision's own terms. Hikvision may
change or remove that download at any time; use `HCNETSDK_ZIP_URL` or `apps/stream/sdk/` if it does.

**Miễn trừ trách nhiệm.** Dự án phục vụ mục đích cá nhân: phụ huynh xem camera lớp học mà nhà trường đã chủ
động cấp quyền. Chỉ dùng với tài khoản và thiết bị mà bạn được phép truy cập, tuân thủ quy định của trường và
pháp luật về quyền riêng tư. Không phát tán video, không chia sẻ mật khẩu ra ngoài gia đình. Phần mềm cung cấp
nguyên trạng, không bảo đảm, tác giả không chịu trách nhiệm cho việc sử dụng sai mục đích. Tác giả không liên
quan tới Hikvision; SDK của Hikvision là phần mềm độc quyền, người dùng tự tải từ hikvision.com theo điều khoản
của Hikvision.

## License

MIT (see LICENSE). Hikvision's Device Network SDK is proprietary and downloaded separately from hikvision.com.
