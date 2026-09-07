"""
Hikvision SDK - Python wrapper for Hikvision HCNetSDK

A Python library for interacting with Hikvision cameras and NVRs.

Requirements:
    The Hikvision SDK libraries (.so files) must be installed separately.
    Download from Hikvision and install to one of:
    - ~/.local/lib/hikvision (recommended)
    - /usr/local/lib/hikvision
    - /usr/lib/hikvision
    Or set HIKVISION_SDK_PATH environment variable.

Example usage:
    from hikvision_sdk import HCNetSDK

    with HCNetSDK() as sdk:
        with sdk.login("192.168.1.100", 8000, "admin", "password") as device:
            # Search for files
            from datetime import datetime, timedelta
            end = datetime.now()
            start = end - timedelta(days=1)

            for f in device.find_files(device.start_channel, start, end):
                print(f.filename, f.start_time, f.file_size)

            # Download a file
            device.download_file(f.filename, "/tmp/video.mp4")

            # Capture JPEG
            device.capture_jpeg(device.start_channel, "/tmp/capture.jpg")
"""

from .sdk import HCNetSDK, Device, FileInfo, DeviceConfig
from .exceptions import (
    HCNetSDKError,
    SDKNotInitializedError,
    SDKInitError,
    LoginError,
    LogoutError,
    PreviewError,
    FileSearchError,
    FileDownloadError,
    CaptureError,
    LibraryLoadError,
)
from .constants import (
    # Stream types
    STREAM_TYPE_MAIN,
    STREAM_TYPE_SUB,
    STREAM_TYPE_THIRD,
    STREAM_TYPE_ALL,
    # Link modes
    LINK_MODE_TCP,
    LINK_MODE_UDP,
    LINK_MODE_MULTICAST,
    LINK_MODE_RTP,
    LINK_MODE_RTP_RTSP,
    LINK_MODE_RTSP_HTTP,
    # File types
    FILE_TYPE_ALL,
    FILE_TYPE_TIMING,
    FILE_TYPE_MOTION,
    FILE_TYPE_ALARM,
    FILE_TYPE_MANUAL,
    FILE_TYPE_VCA,
    # Lock status
    LOCK_STATUS_ALL,
    LOCK_STATUS_UNLOCKED,
    LOCK_STATUS_LOCKED,
    # Data types
    NET_DVR_SYSHEAD,
    NET_DVR_STREAMDATA,
    NET_DVR_AUDIOSTREAMDATA,
    # PTZ commands
    PTZ_UP,
    PTZ_DOWN,
    PTZ_LEFT,
    PTZ_RIGHT,
    PTZ_UP_LEFT,
    PTZ_UP_RIGHT,
    PTZ_DOWN_LEFT,
    PTZ_DOWN_RIGHT,
    PTZ_ZOOM_IN,
    PTZ_ZOOM_OUT,
    PTZ_FOCUS_NEAR,
    PTZ_FOCUS_FAR,
    PTZ_IRIS_OPEN,
    PTZ_IRIS_CLOSE,
    PTZ_AUTO_PAN,
    # PTZ preset commands
    PTZ_PRESET_SET,
    PTZ_PRESET_CLEAR,
    PTZ_PRESET_GOTO,
    # PTZ cruise commands
    PTZ_CRUISE_RUN,
    PTZ_CRUISE_STOP,
    PTZ_CRUISE_FILL_PRESET,
    PTZ_CRUISE_SET_SPEED,
    PTZ_CRUISE_SET_DWELL,
    PTZ_CRUISE_CLEAR,
    # PTZ track commands
    PTZ_TRACK_START_RECORD,
    PTZ_TRACK_STOP_RECORD,
    PTZ_TRACK_RUN,
    # Alarm message types
    COMM_ALARM,
    COMM_ALARM_V30,
    COMM_ALARM_V40,
    COMM_ALARM_RULE,
    COMM_VCA_ALARM,
    # Utility
    get_error_message,
)

__version__ = "0.1.0"
__all__ = [
    # Main classes
    "HCNetSDK",
    "Device",
    "FileInfo",
    "DeviceConfig",
    # Exceptions
    "HCNetSDKError",
    "SDKNotInitializedError",
    "SDKInitError",
    "LoginError",
    "LogoutError",
    "PreviewError",
    "FileSearchError",
    "FileDownloadError",
    "CaptureError",
    "LibraryLoadError",
    # Stream constants
    "STREAM_TYPE_MAIN",
    "STREAM_TYPE_SUB",
    "STREAM_TYPE_THIRD",
    "STREAM_TYPE_ALL",
    "LINK_MODE_TCP",
    "LINK_MODE_UDP",
    "LINK_MODE_MULTICAST",
    "LINK_MODE_RTP",
    "LINK_MODE_RTP_RTSP",
    "LINK_MODE_RTSP_HTTP",
    # File constants
    "FILE_TYPE_ALL",
    "FILE_TYPE_TIMING",
    "FILE_TYPE_MOTION",
    "FILE_TYPE_ALARM",
    "FILE_TYPE_MANUAL",
    "FILE_TYPE_VCA",
    "LOCK_STATUS_ALL",
    "LOCK_STATUS_UNLOCKED",
    "LOCK_STATUS_LOCKED",
    # Data types
    "NET_DVR_SYSHEAD",
    "NET_DVR_STREAMDATA",
    "NET_DVR_AUDIOSTREAMDATA",
    # PTZ constants
    "PTZ_UP",
    "PTZ_DOWN",
    "PTZ_LEFT",
    "PTZ_RIGHT",
    "PTZ_UP_LEFT",
    "PTZ_UP_RIGHT",
    "PTZ_DOWN_LEFT",
    "PTZ_DOWN_RIGHT",
    "PTZ_ZOOM_IN",
    "PTZ_ZOOM_OUT",
    "PTZ_FOCUS_NEAR",
    "PTZ_FOCUS_FAR",
    "PTZ_IRIS_OPEN",
    "PTZ_IRIS_CLOSE",
    "PTZ_AUTO_PAN",
    "PTZ_PRESET_SET",
    "PTZ_PRESET_CLEAR",
    "PTZ_PRESET_GOTO",
    "PTZ_CRUISE_RUN",
    "PTZ_CRUISE_STOP",
    "PTZ_CRUISE_FILL_PRESET",
    "PTZ_CRUISE_SET_SPEED",
    "PTZ_CRUISE_SET_DWELL",
    "PTZ_CRUISE_CLEAR",
    "PTZ_TRACK_START_RECORD",
    "PTZ_TRACK_STOP_RECORD",
    "PTZ_TRACK_RUN",
    # Alarm constants
    "COMM_ALARM",
    "COMM_ALARM_V30",
    "COMM_ALARM_V40",
    "COMM_ALARM_RULE",
    "COMM_VCA_ALARM",
    # Utility
    "get_error_message",
]
