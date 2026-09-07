# Hikvision Device Network SDK (Linux 64-bit)

The stream image needs Hikvision's proprietary `HCNetSDK` shared libraries. They are **not** in this repo.

At build time `get_sdk.sh` looks for them in this order:

1. `lib/` in this directory (already extracted `lib` folder of the SDK zip)
2. any `*.zip` in this directory (the SDK zip as downloaded)
3. the `HCNETSDK_ZIP_URL` build-arg (a URL you host yourself)
4. Hikvision's official download page (default, requires internet during build)

Download page: https://www.hikvision.com/en/support/tools/hitools/clf4633a00e385d6ea/
Version tested: EN-HCNetSDKV6.1.9.48_build20230410_linux64
