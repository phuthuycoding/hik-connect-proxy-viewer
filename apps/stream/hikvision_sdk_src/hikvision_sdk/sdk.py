"""
HCNetSDK Python Wrapper

Main SDK class for interacting with Hikvision cameras.
"""

import os
import sys
import ctypes
from ctypes import c_int, c_char_p, c_void_p, byref, POINTER
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable, Iterator, List, Any
from dataclasses import dataclass
import time

from .types import (
    BOOL, DWORD, LONG, BYTE, WORD, HWND,
    NET_DVR_USER_LOGIN_INFO,
    NET_DVR_DEVICEINFO_V40,
    NET_DVR_DEVICEINFO_V30,
    NET_DVR_PREVIEWINFO,
    NET_DVR_FILECOND_V50,
    NET_DVR_FINDDATA_V50,
    NET_DVR_STREAM_INFO,
    NET_DVR_TIME_SEARCH_COND,
    NET_DVR_JPEGPARA,
    NET_DVR_TIME,
    NET_DVR_SETUPALARM_PARAM,
    NET_DVR_ALARMER,
    NET_DVR_DEVICECFG_V40,
    REALDATACALLBACK,
    MSGNOTESSTREAMCALLBACK,
    LPNET_DVR_USER_LOGIN_INFO,
    LPNET_DVR_DEVICEINFO_V40,
    LPNET_DVR_PREVIEWINFO,
    LPNET_DVR_FILECOND_V50,
    LPNET_DVR_FINDDATA_V50,
    LPNET_DVR_JPEGPARA,
    LPNET_DVR_TIME,
    LPNET_DVR_SETUPALARM_PARAM,
)
from .constants import (
    NET_DVR_FILE_SUCCESS,
    NET_DVR_NOMOREFILE,
    NET_DVR_ISFINDING,
    NET_DVR_FILE_NOFIND,
    STREAM_TYPE_MAIN,
    LINK_MODE_TCP,
    FILE_TYPE_ALL,
    LOCK_STATUS_ALL,
    NET_DVR_SYSHEAD,
    NET_DVR_STREAMDATA,
)
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


@dataclass
class DeviceConfig:
    """Parsed device configuration information."""
    device_name: str
    device_id: int
    serial_number: str
    software_version: str
    software_build_date: str
    hardware_version: str
    dsp_version: str
    dsp_build_date: str
    panel_version: str
    device_type: int
    device_type_name: str
    channel_count: int
    start_channel: int
    ip_channel_count: int
    alarm_in_count: int
    alarm_out_count: int
    disk_count: int
    audio_count: int
    recycle_record: bool

    def __str__(self) -> str:
        return (
            f"Device: {self.device_name}\n"
            f"  Serial: {self.serial_number}\n"
            f"  Type: {self.device_type_name} ({self.device_type})\n"
            f"  Software: {self.software_version} ({self.software_build_date})\n"
            f"  Hardware: {self.hardware_version}\n"
            f"  Channels: {self.channel_count} (start: {self.start_channel})\n"
            f"  IP Channels: {self.ip_channel_count}\n"
            f"  Disks: {self.disk_count}\n"
            f"  Alarm In/Out: {self.alarm_in_count}/{self.alarm_out_count}"
        )


def _parse_version(version: int) -> str:
    """Parse packed version number to string."""
    if version == 0:
        return "N/A"
    major = (version >> 24) & 0xFF
    minor = (version >> 16) & 0xFF
    revision = version & 0xFFFF
    return f"{major}.{minor}.{revision}"


def _parse_build_date(date: int) -> str:
    """Parse packed build date to string."""
    if date == 0:
        return "N/A"
    year = (date >> 16) & 0xFFFF
    month = (date >> 8) & 0xFF
    day = date & 0xFF
    return f"{year}-{month:02d}-{day:02d}"


def _find_lib_path() -> Path:
    """
    Find the SDK library path.

    Search order:
    1. HIKVISION_SDK_PATH environment variable
    2. User-local: ~/.local/lib/hikvision
    3. System-wide: /usr/local/lib/hikvision
    4. System: /usr/lib/hikvision

    Returns:
        Path to directory containing libhcnetsdk.so

    Raises:
        LibraryLoadError: If library not found
    """
    search_paths = []

    # Check environment variable first
    env_path = os.environ.get("HIKVISION_SDK_PATH")
    if env_path:
        search_paths.append(Path(env_path))

    # Standard locations
    search_paths.extend([
        Path.home() / ".local/lib/hikvision",
        Path("/usr/local/lib/hikvision"),
        Path("/usr/lib/hikvision"),
    ])

    for path in search_paths:
        if (path / "libhcnetsdk.so").exists():
            return path

    searched = "\n  - ".join(str(p) for p in search_paths)
    raise LibraryLoadError(
        "libhcnetsdk.so",
        f"Library not found. Please install the Hikvision SDK libraries.\n\n"
        f"Download the SDK from Hikvision and copy the libraries to one of:\n  - {searched}\n\n"
        f"Or set HIKVISION_SDK_PATH environment variable to the library directory.\n\n"
        f"Example:\n"
        f"  mkdir -p ~/.local/lib/hikvision\n"
        f"  cp -r /path/to/sdk/lib/* ~/.local/lib/hikvision/"
    )


class HCNetSDK:
    """
    Main SDK wrapper class.

    Handles library loading, initialization, and provides access to all SDK functions.

    The SDK libraries must be installed separately from Hikvision. The library
    search order is:
    1. HIKVISION_SDK_PATH environment variable
    2. ~/.local/lib/hikvision (recommended for user install)
    3. /usr/local/lib/hikvision
    4. /usr/lib/hikvision

    Usage:
        sdk = HCNetSDK()
        sdk.init()
        device = sdk.login("192.168.1.100", 8000, "admin", "password")
        # ... use device ...
        device.logout()
        sdk.cleanup()

    Or with context manager:
        with HCNetSDK() as sdk:
            with sdk.login("192.168.1.100", 8000, "admin", "password") as device:
                # ... use device ...
    """

    _instance: Optional['HCNetSDK'] = None
    _initialized: bool = False

    def __init__(self, lib_path: Optional[str] = None):
        """
        Initialize HCNetSDK wrapper.

        Args:
            lib_path: Path to the directory containing libhcnetsdk.so.
                     If not provided, searches standard system locations
                     or uses HIKVISION_SDK_PATH environment variable.
        """
        if lib_path is not None:
            self.lib_path = Path(lib_path)
        else:
            self.lib_path = _find_lib_path()

        self._sdk = None
        self._devices: List['Device'] = []
        self._load_library()

    def _load_library(self):
        """Load the HCNetSDK shared library."""
        sdk_lib = self.lib_path / "libhcnetsdk.so"

        if not sdk_lib.exists():
            raise LibraryLoadError(str(sdk_lib), "File does not exist")

        # Set LD_LIBRARY_PATH to include lib directory and HCNetSDKCom
        lib_dirs = [
            str(self.lib_path),
            str(self.lib_path / "HCNetSDKCom"),
        ]

        current_ld_path = os.environ.get("LD_LIBRARY_PATH", "")
        new_ld_path = ":".join(lib_dirs)
        if current_ld_path:
            new_ld_path = f"{new_ld_path}:{current_ld_path}"
        os.environ["LD_LIBRARY_PATH"] = new_ld_path

        try:
            # Load the main SDK library
            self._sdk = ctypes.CDLL(str(sdk_lib), mode=ctypes.RTLD_GLOBAL)
            self._setup_function_prototypes()
        except OSError as e:
            raise LibraryLoadError(str(sdk_lib), str(e))

    def _setup_function_prototypes(self):
        """Set up ctypes function prototypes for SDK functions."""
        sdk = self._sdk

        # NET_DVR_Init
        sdk.NET_DVR_Init.argtypes = []
        sdk.NET_DVR_Init.restype = BOOL

        # NET_DVR_Cleanup
        sdk.NET_DVR_Cleanup.argtypes = []
        sdk.NET_DVR_Cleanup.restype = BOOL

        # NET_DVR_SetLogToFile
        sdk.NET_DVR_SetLogToFile.argtypes = [c_int, c_char_p, BOOL]
        sdk.NET_DVR_SetLogToFile.restype = BOOL

        # NET_DVR_GetSDKBuildVersion
        sdk.NET_DVR_GetSDKBuildVersion.argtypes = []
        sdk.NET_DVR_GetSDKBuildVersion.restype = ctypes.c_uint

        # NET_DVR_GetLastError
        sdk.NET_DVR_GetLastError.argtypes = []
        sdk.NET_DVR_GetLastError.restype = DWORD

        # NET_DVR_Login_V40
        sdk.NET_DVR_Login_V40.argtypes = [LPNET_DVR_USER_LOGIN_INFO, LPNET_DVR_DEVICEINFO_V40]
        sdk.NET_DVR_Login_V40.restype = LONG

        # NET_DVR_Logout_V30
        sdk.NET_DVR_Logout_V30.argtypes = [LONG]
        sdk.NET_DVR_Logout_V30.restype = BOOL

        # NET_DVR_RealPlay_V40
        sdk.NET_DVR_RealPlay_V40.argtypes = [LONG, LPNET_DVR_PREVIEWINFO, REALDATACALLBACK, c_void_p]
        sdk.NET_DVR_RealPlay_V40.restype = LONG

        # NET_DVR_StopRealPlay
        sdk.NET_DVR_StopRealPlay.argtypes = [LONG]
        sdk.NET_DVR_StopRealPlay.restype = BOOL

        # NET_DVR_SetRealDataCallBack
        sdk.NET_DVR_SetRealDataCallBack.argtypes = [LONG, REALDATACALLBACK, DWORD]
        sdk.NET_DVR_SetRealDataCallBack.restype = BOOL

        # NET_DVR_FindFile_V50
        sdk.NET_DVR_FindFile_V50.argtypes = [LONG, LPNET_DVR_FILECOND_V50]
        sdk.NET_DVR_FindFile_V50.restype = LONG

        # NET_DVR_FindNextFile_V50
        sdk.NET_DVR_FindNextFile_V50.argtypes = [LONG, LPNET_DVR_FINDDATA_V50]
        sdk.NET_DVR_FindNextFile_V50.restype = LONG

        # NET_DVR_FindClose_V30
        sdk.NET_DVR_FindClose_V30.argtypes = [LONG]
        sdk.NET_DVR_FindClose_V30.restype = BOOL

        # NET_DVR_GetFileByName
        sdk.NET_DVR_GetFileByName.argtypes = [LONG, c_char_p, c_char_p]
        sdk.NET_DVR_GetFileByName.restype = LONG

        # NET_DVR_GetFileByTime
        sdk.NET_DVR_GetFileByTime.argtypes = [LONG, LONG, LPNET_DVR_TIME, LPNET_DVR_TIME, c_char_p]
        sdk.NET_DVR_GetFileByTime.restype = LONG

        # NET_DVR_StopGetFile
        sdk.NET_DVR_StopGetFile.argtypes = [LONG]
        sdk.NET_DVR_StopGetFile.restype = BOOL

        # NET_DVR_GetDownloadPos
        sdk.NET_DVR_GetDownloadPos.argtypes = [LONG]
        sdk.NET_DVR_GetDownloadPos.restype = LONG

        # NET_DVR_CaptureJPEGPicture
        sdk.NET_DVR_CaptureJPEGPicture.argtypes = [LONG, LONG, LPNET_DVR_JPEGPARA, c_char_p]
        sdk.NET_DVR_CaptureJPEGPicture.restype = BOOL

        # Playback functions
        # NET_DVR_PlayBackByName
        sdk.NET_DVR_PlayBackByName.argtypes = [LONG, c_char_p, HWND]
        sdk.NET_DVR_PlayBackByName.restype = LONG

        # NET_DVR_StopPlayBack
        sdk.NET_DVR_StopPlayBack.argtypes = [LONG]
        sdk.NET_DVR_StopPlayBack.restype = BOOL

        # NET_DVR_PlayBackControl_V40
        sdk.NET_DVR_PlayBackControl_V40.argtypes = [LONG, DWORD, c_void_p, DWORD, c_void_p, c_void_p]
        sdk.NET_DVR_PlayBackControl_V40.restype = BOOL

        # NET_DVR_PlayBackCaptureFile
        sdk.NET_DVR_PlayBackCaptureFile.argtypes = [LONG, c_char_p]
        sdk.NET_DVR_PlayBackCaptureFile.restype = BOOL

        # NET_DVR_GetPlayBackPos
        sdk.NET_DVR_GetPlayBackPos.argtypes = [LONG]
        sdk.NET_DVR_GetPlayBackPos.restype = LONG

        # NET_DVR_SetPlayDataCallBack_V40
        sdk.NET_DVR_SetPlayDataCallBack_V40.argtypes = [LONG, REALDATACALLBACK, c_void_p]
        sdk.NET_DVR_SetPlayDataCallBack_V40.restype = BOOL

        # ====================================================================
        # PTZ Control Functions
        # ====================================================================

        # NET_DVR_PTZControl_Other - PTZ control with channel
        sdk.NET_DVR_PTZControl_Other.argtypes = [LONG, LONG, DWORD, DWORD]
        sdk.NET_DVR_PTZControl_Other.restype = BOOL

        # NET_DVR_PTZControlWithSpeed_Other - PTZ control with speed
        sdk.NET_DVR_PTZControlWithSpeed_Other.argtypes = [LONG, LONG, DWORD, DWORD, DWORD]
        sdk.NET_DVR_PTZControlWithSpeed_Other.restype = BOOL

        # NET_DVR_PTZPreset_Other - PTZ preset control
        sdk.NET_DVR_PTZPreset_Other.argtypes = [LONG, LONG, DWORD, DWORD]
        sdk.NET_DVR_PTZPreset_Other.restype = BOOL

        # NET_DVR_PTZCruise_Other - PTZ cruise control
        sdk.NET_DVR_PTZCruise_Other.argtypes = [LONG, LONG, DWORD, BYTE, BYTE, WORD]
        sdk.NET_DVR_PTZCruise_Other.restype = BOOL

        # NET_DVR_PTZTrack_Other - PTZ pattern/track control
        sdk.NET_DVR_PTZTrack_Other.argtypes = [LONG, LONG, DWORD]
        sdk.NET_DVR_PTZTrack_Other.restype = BOOL

        # ====================================================================
        # Alarm Functions
        # ====================================================================

        # NET_DVR_SetDVRMessageCallBack_V50 - Set alarm callback
        sdk.NET_DVR_SetDVRMessageCallBack_V50.argtypes = [c_int, MSGNOTESSTREAMCALLBACK, c_void_p]
        sdk.NET_DVR_SetDVRMessageCallBack_V50.restype = BOOL

        # NET_DVR_SetupAlarmChan_V41 - Setup alarm channel
        sdk.NET_DVR_SetupAlarmChan_V41.argtypes = [LONG, LPNET_DVR_SETUPALARM_PARAM]
        sdk.NET_DVR_SetupAlarmChan_V41.restype = LONG

        # NET_DVR_CloseAlarmChan_V30 - Close alarm channel
        sdk.NET_DVR_CloseAlarmChan_V30.argtypes = [LONG]
        sdk.NET_DVR_CloseAlarmChan_V30.restype = BOOL

        # ====================================================================
        # Device Config Functions
        # ====================================================================

        # NET_DVR_GetDeviceConfig - Get device configuration
        sdk.NET_DVR_GetDeviceConfig.argtypes = [LONG, DWORD, DWORD, c_void_p, DWORD, c_void_p, c_void_p, DWORD]
        sdk.NET_DVR_GetDeviceConfig.restype = BOOL

        # NET_DVR_SetDeviceConfig - Set device configuration
        sdk.NET_DVR_SetDeviceConfig.argtypes = [LONG, DWORD, DWORD, c_void_p, DWORD, c_void_p, DWORD]
        sdk.NET_DVR_SetDeviceConfig.restype = BOOL

    def init(self, log_level: int = 3, log_dir: Optional[str] = None) -> bool:
        """
        Initialize the SDK.

        Args:
            log_level: Log level (0-none, 1-error, 2-debug, 3-all)
            log_dir: Directory for log files (optional)

        Returns:
            True if initialization successful

        Raises:
            SDKInitError: If initialization fails
        """
        if self._initialized:
            return True

        result = self._sdk.NET_DVR_Init()
        if not result:
            error = self._sdk.NET_DVR_GetLastError()
            raise SDKInitError("Failed to initialize SDK", error)

        self._initialized = True
        HCNetSDK._instance = self

        # Set up logging if requested
        if log_dir:
            log_dir_bytes = log_dir.encode('utf-8')
            self._sdk.NET_DVR_SetLogToFile(log_level, log_dir_bytes, False)

        return True

    def cleanup(self) -> bool:
        """
        Clean up SDK resources.

        Returns:
            True if cleanup successful
        """
        if not self._initialized:
            return True

        # Logout all devices first
        for device in self._devices[:]:
            try:
                device.logout()
            except Exception:
                pass

        result = self._sdk.NET_DVR_Cleanup()
        self._initialized = False
        HCNetSDK._instance = None
        return bool(result)

    def get_sdk_version(self) -> str:
        """
        Get SDK version string.

        Returns:
            Version string in format "X.X.X.X"
        """
        version = self._sdk.NET_DVR_GetSDKBuildVersion()
        major = (version >> 24) & 0xFF
        minor = (version >> 16) & 0xFF
        revision = (version >> 8) & 0xFF
        build = version & 0xFF
        return f"{major}.{minor}.{revision}.{build}"

    def get_last_error(self) -> int:
        """Get last error code from SDK."""
        return self._sdk.NET_DVR_GetLastError()

    def login(
        self,
        ip: str,
        port: int,
        username: str,
        password: str,
        async_login: bool = False
    ) -> 'Device':
        """
        Login to a device.

        Args:
            ip: Device IP address
            port: Device port (usually 8000)
            username: Login username
            password: Login password
            async_login: Use asynchronous login (default: False)

        Returns:
            Device instance for the logged-in device

        Raises:
            SDKNotInitializedError: If SDK not initialized
            LoginError: If login fails
        """
        if not self._initialized:
            raise SDKNotInitializedError()

        # Prepare login info structure
        login_info = NET_DVR_USER_LOGIN_INFO()
        ctypes.memset(byref(login_info), 0, ctypes.sizeof(login_info))

        login_info.sDeviceAddress = ip.encode('utf-8')
        login_info.wPort = port
        login_info.sUserName = username.encode('utf-8')
        login_info.sPassword = password.encode('utf-8')
        login_info.bUseAsynLogin = 1 if async_login else 0

        # Prepare device info structure
        device_info = NET_DVR_DEVICEINFO_V40()
        ctypes.memset(byref(device_info), 0, ctypes.sizeof(device_info))

        # Perform login
        user_id = self._sdk.NET_DVR_Login_V40(byref(login_info), byref(device_info))

        if user_id < 0:
            error = self._sdk.NET_DVR_GetLastError()
            raise LoginError(f"Failed to login to {ip}:{port}", error)

        # Create device wrapper
        device = Device(self, user_id, device_info, ip, port)
        self._devices.append(device)
        return device

    def __enter__(self):
        """Context manager entry."""
        self.init()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()
        return False


class Device:
    """
    Represents a connected Hikvision device.

    Provides methods for previewing, file search, download, and capture.
    """

    def __init__(
        self,
        sdk: HCNetSDK,
        user_id: int,
        device_info: NET_DVR_DEVICEINFO_V40,
        ip: str,
        port: int
    ):
        self._sdk = sdk
        self._user_id = user_id
        self._device_info = device_info
        self._ip = ip
        self._port = port
        self._preview_handles: List[int] = []
        self._download_handles: List[int] = []
        self._callbacks: List[Any] = []  # Keep references to prevent GC
        self._logged_in = True

    @property
    def user_id(self) -> int:
        """Get device user ID (handle)."""
        return self._user_id

    @property
    def ip(self) -> str:
        """Get device IP address."""
        return self._ip

    @property
    def port(self) -> int:
        """Get device port."""
        return self._port

    @property
    def serial_number(self) -> str:
        """Get device serial number."""
        sn = bytes(self._device_info.struDeviceV30.sSerialNumber)
        return sn.rstrip(b'\x00').decode('utf-8', errors='ignore')

    @property
    def channel_count(self) -> int:
        """Get number of channels."""
        return self._device_info.struDeviceV30.byChanNum

    @property
    def start_channel(self) -> int:
        """Get starting channel number."""
        return self._device_info.struDeviceV30.byStartChan

    @property
    def ip_channel_count(self) -> int:
        """Get number of IP channels."""
        return self._device_info.struDeviceV30.byIPChanNum

    def logout(self) -> bool:
        """
        Logout from device.

        Returns:
            True if logout successful
        """
        if not self._logged_in:
            return True

        # Stop all previews
        for handle in self._preview_handles[:]:
            try:
                self.stop_preview(handle)
            except Exception:
                pass

        # Stop all downloads
        for handle in self._download_handles[:]:
            try:
                self.stop_download(handle)
            except Exception:
                pass

        result = self._sdk._sdk.NET_DVR_Logout_V30(self._user_id)
        if not result:
            error = self._sdk.get_last_error()
            raise LogoutError(f"Failed to logout from {self._ip}", error)

        self._logged_in = False
        if self in self._sdk._devices:
            self._sdk._devices.remove(self)

        return True

    # ========================================================================
    # Preview Methods
    # ========================================================================

    def start_preview(
        self,
        channel: int,
        stream_type: int = STREAM_TYPE_MAIN,
        link_mode: int = LINK_MODE_TCP,
        callback: Optional[Callable[[int, int, bytes], None]] = None,
        blocked: bool = True
    ) -> int:
        """
        Start real-time preview (streaming).

        Args:
            channel: Channel number (1-based for analog, start_channel for IP)
            stream_type: Stream type (0-main, 1-sub, 2-third)
            link_mode: Link mode (0-TCP, 1-UDP, etc.)
            callback: Optional callback function(handle, data_type, data)
            blocked: Block until connected (default: True)

        Returns:
            Preview handle

        Raises:
            PreviewError: If preview fails to start
        """
        preview_info = NET_DVR_PREVIEWINFO()
        ctypes.memset(byref(preview_info), 0, ctypes.sizeof(preview_info))

        preview_info.lChannel = channel
        preview_info.dwStreamType = stream_type
        preview_info.dwLinkMode = link_mode
        preview_info.hPlayWnd = 0  # No window (Linux headless)
        preview_info.bBlocked = 1 if blocked else 0
        preview_info.dwDisplayBufNum = 1

        # Create C callback if Python callback provided
        c_callback = None
        if callback:
            def _callback_wrapper(handle, data_type, buffer, buf_size, user):
                try:
                    data = ctypes.string_at(buffer, buf_size)
                    callback(handle, data_type, data)
                except Exception:
                    pass

            c_callback = REALDATACALLBACK(_callback_wrapper)
            self._callbacks.append(c_callback)  # Prevent GC

        handle = self._sdk._sdk.NET_DVR_RealPlay_V40(
            self._user_id,
            byref(preview_info),
            c_callback,
            None
        )

        if handle < 0:
            error = self._sdk.get_last_error()
            raise PreviewError(f"Failed to start preview on channel {channel}", error)

        self._preview_handles.append(handle)
        return handle

    def stop_preview(self, handle: int) -> bool:
        """
        Stop preview.

        Args:
            handle: Preview handle from start_preview()

        Returns:
            True if stopped successfully
        """
        result = self._sdk._sdk.NET_DVR_StopRealPlay(handle)
        if handle in self._preview_handles:
            self._preview_handles.remove(handle)
        return bool(result)

    def set_preview_callback(
        self,
        handle: int,
        callback: Callable[[int, int, bytes], None]
    ) -> bool:
        """
        Set or change preview callback.

        Args:
            handle: Preview handle
            callback: Callback function(handle, data_type, data)

        Returns:
            True if callback set successfully
        """
        def _callback_wrapper(h, data_type, buffer, buf_size, user):
            try:
                data = ctypes.string_at(buffer, buf_size)
                callback(h, data_type, data)
            except Exception:
                pass

        c_callback = REALDATACALLBACK(_callback_wrapper)
        self._callbacks.append(c_callback)

        return bool(self._sdk._sdk.NET_DVR_SetRealDataCallBack(handle, c_callback, 0))

    # ========================================================================
    # File Search Methods
    # ========================================================================

    def find_files(
        self,
        channel: int,
        start_time: datetime,
        end_time: datetime,
        file_type: int = FILE_TYPE_ALL,
        stream_type: int = 0xFF,
        locked: int = LOCK_STATUS_ALL
    ) -> Iterator['FileInfo']:
        """
        Search for recorded files on the device.

        Args:
            channel: Channel number
            start_time: Start time for search
            end_time: End time for search
            file_type: File type filter (default: all)
            stream_type: Stream type filter (default: all)
            locked: Lock status filter (default: all)

        Yields:
            FileInfo objects for each found file

        Raises:
            FileSearchError: If search fails
        """
        # Prepare search condition
        find_cond = NET_DVR_FILECOND_V50()
        ctypes.memset(byref(find_cond), 0, ctypes.sizeof(find_cond))

        # Set stream/channel info
        find_cond.struStreamID.dwSize = ctypes.sizeof(NET_DVR_STREAM_INFO)
        find_cond.struStreamID.dwChannel = channel

        # Set start time
        find_cond.struStartTime.wYear = start_time.year
        find_cond.struStartTime.byMonth = start_time.month
        find_cond.struStartTime.byDay = start_time.day
        find_cond.struStartTime.byHour = start_time.hour
        find_cond.struStartTime.byMinute = start_time.minute
        find_cond.struStartTime.bySecond = start_time.second

        # Set end time
        find_cond.struStopTime.wYear = end_time.year
        find_cond.struStopTime.byMonth = end_time.month
        find_cond.struStopTime.byDay = end_time.day
        find_cond.struStopTime.byHour = end_time.hour
        find_cond.struStopTime.byMinute = end_time.minute
        find_cond.struStopTime.bySecond = end_time.second

        # Set filters
        find_cond.dwFileType = file_type
        find_cond.byStreamType = stream_type
        find_cond.byIsLocked = locked

        # Start search
        find_handle = self._sdk._sdk.NET_DVR_FindFile_V50(self._user_id, byref(find_cond))

        if find_handle < 0:
            error = self._sdk.get_last_error()
            raise FileSearchError(f"Failed to start file search on channel {channel}", error)

        try:
            # Iterate through results
            while True:
                find_data = NET_DVR_FINDDATA_V50()
                ctypes.memset(byref(find_data), 0, ctypes.sizeof(find_data))
                result = self._sdk._sdk.NET_DVR_FindNextFile_V50(find_handle, byref(find_data))

                if result == NET_DVR_FILE_SUCCESS:
                    # Create a copy of the data for FileInfo
                    file_info = FileInfo._from_struct(find_data)
                    yield file_info
                elif result == NET_DVR_NOMOREFILE:
                    break
                elif result == NET_DVR_ISFINDING:
                    time.sleep(0.01)  # Brief pause while searching
                    continue
                elif result == NET_DVR_FILE_NOFIND:
                    break
                else:
                    error = self._sdk.get_last_error()
                    raise FileSearchError("Error during file search", error)
        finally:
            self._sdk._sdk.NET_DVR_FindClose_V30(find_handle)

    # ========================================================================
    # File Download Methods
    # ========================================================================

    def download_file(
        self,
        filename: str,
        save_path: str,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> bool:
        """
        Download a file by name.

        Args:
            filename: Remote filename (from file search)
            save_path: Local path to save the file
            progress_callback: Optional callback(progress_percent)

        Returns:
            True if download completed successfully

        Raises:
            FileDownloadError: If download fails
        """
        filename_bytes = filename.encode('utf-8')
        save_path_bytes = save_path.encode('utf-8')

        handle = self._sdk._sdk.NET_DVR_GetFileByName(
            self._user_id,
            filename_bytes,
            save_path_bytes
        )

        if handle < 0:
            error = self._sdk.get_last_error()
            raise FileDownloadError(f"Failed to start download: {filename}", error)

        self._download_handles.append(handle)

        try:
            # Start the download (required!)
            NET_DVR_PLAYSTART = 1
            if not self._sdk._sdk.NET_DVR_PlayBackControl_V40(
                handle, NET_DVR_PLAYSTART, None, 0, None, None
            ):
                error = self._sdk.get_last_error()
                raise FileDownloadError(f"Failed to start download playback: {filename}", error)

            # Monitor download progress
            while True:
                pos = self._sdk._sdk.NET_DVR_GetDownloadPos(handle)

                if pos < 0:
                    error = self._sdk.get_last_error()
                    raise FileDownloadError("Download error", error)

                if progress_callback:
                    progress_callback(pos)

                if pos >= 100:
                    break

                time.sleep(0.1)

            return True
        finally:
            self._sdk._sdk.NET_DVR_StopGetFile(handle)
            if handle in self._download_handles:
                self._download_handles.remove(handle)

    def download_by_time(
        self,
        channel: int,
        start_time: datetime,
        end_time: datetime,
        save_path: str,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> bool:
        """
        Download recording by time range.

        Args:
            channel: Channel number
            start_time: Start time
            end_time: End time
            save_path: Local path to save the file
            progress_callback: Optional callback(progress_percent)

        Returns:
            True if download completed successfully

        Raises:
            FileDownloadError: If download fails
        """
        # Prepare time structures
        start = NET_DVR_TIME()
        start.dwYear = start_time.year
        start.dwMonth = start_time.month
        start.dwDay = start_time.day
        start.dwHour = start_time.hour
        start.dwMinute = start_time.minute
        start.dwSecond = start_time.second

        end = NET_DVR_TIME()
        end.dwYear = end_time.year
        end.dwMonth = end_time.month
        end.dwDay = end_time.day
        end.dwHour = end_time.hour
        end.dwMinute = end_time.minute
        end.dwSecond = end_time.second

        save_path_bytes = save_path.encode('utf-8')

        handle = self._sdk._sdk.NET_DVR_GetFileByTime(
            self._user_id,
            channel,
            byref(start),
            byref(end),
            save_path_bytes
        )

        if handle < 0:
            error = self._sdk.get_last_error()
            raise FileDownloadError(
                f"Failed to start time-based download on channel {channel}",
                error
            )

        self._download_handles.append(handle)

        try:
            while True:
                pos = self._sdk._sdk.NET_DVR_GetDownloadPos(handle)

                if pos < 0:
                    error = self._sdk.get_last_error()
                    raise FileDownloadError("Download error", error)

                if progress_callback:
                    progress_callback(pos)

                if pos >= 100:
                    break

                time.sleep(0.1)

            return True
        finally:
            self._sdk._sdk.NET_DVR_StopGetFile(handle)
            if handle in self._download_handles:
                self._download_handles.remove(handle)

    def stop_download(self, handle: int) -> bool:
        """
        Stop an ongoing download.

        Args:
            handle: Download handle

        Returns:
            True if stopped successfully
        """
        result = self._sdk._sdk.NET_DVR_StopGetFile(handle)
        if handle in self._download_handles:
            self._download_handles.remove(handle)
        return bool(result)

    def get_download_progress(self, handle: int) -> int:
        """
        Get download progress.

        Args:
            handle: Download handle

        Returns:
            Progress percentage (0-100)
        """
        return self._sdk._sdk.NET_DVR_GetDownloadPos(handle)

    # ========================================================================
    # Capture Methods
    # ========================================================================

    def capture_jpeg(
        self,
        channel: int,
        save_path: str,
        quality: int = 2,
        size: int = 0
    ) -> bool:
        """
        Capture a JPEG picture from a channel.

        Args:
            channel: Channel number
            save_path: Path to save the JPEG file
            quality: Quality level (0-best, 1-better, 2-normal)
            size: Picture size (0-CIF, 1-QCIF, 2-D1, etc.)

        Returns:
            True if capture successful

        Raises:
            CaptureError: If capture fails
        """
        jpeg_para = NET_DVR_JPEGPARA()
        jpeg_para.wPicQuality = quality
        jpeg_para.wPicSize = size

        save_path_bytes = save_path.encode('utf-8')

        result = self._sdk._sdk.NET_DVR_CaptureJPEGPicture(
            self._user_id,
            channel,
            byref(jpeg_para),
            save_path_bytes
        )

        if not result:
            error = self._sdk.get_last_error()
            raise CaptureError(f"Failed to capture JPEG on channel {channel}", error)

        return True

    # ========================================================================
    # Playback Methods
    # ========================================================================

    def playback_by_name(
        self,
        filename: str,
        callback: Optional[Callable[[int, int, bytes], None]] = None
    ) -> int:
        """
        Start playback of a recorded file by name.

        Args:
            filename: Remote filename (from file search)
            callback: Optional callback for playback data

        Returns:
            Playback handle

        Raises:
            HCNetSDKError: If playback fails to start
        """
        filename_bytes = filename.encode('utf-8')

        # Start playback (hWnd=0 for headless)
        handle = self._sdk._sdk.NET_DVR_PlayBackByName(
            self._user_id,
            filename_bytes,
            0  # No window
        )

        if handle < 0:
            error = self._sdk.get_last_error()
            raise HCNetSDKError(f"Failed to start playback: {filename}", error)

        # Set callback if provided
        if callback:
            def _callback_wrapper(h, data_type, buffer, buf_size, user):
                try:
                    data = ctypes.string_at(buffer, buf_size)
                    callback(h, data_type, data)
                except Exception:
                    pass

            c_callback = REALDATACALLBACK(_callback_wrapper)
            self._callbacks.append(c_callback)
            self._sdk._sdk.NET_DVR_SetPlayDataCallBack_V40(handle, c_callback, None)

        return handle

    def stop_playback(self, handle: int) -> bool:
        """
        Stop playback.

        Args:
            handle: Playback handle

        Returns:
            True if stopped successfully
        """
        return bool(self._sdk._sdk.NET_DVR_StopPlayBack(handle))

    def playback_capture(self, handle: int, save_path: str) -> bool:
        """
        Capture a frame during playback.

        Args:
            handle: Playback handle
            save_path: Path to save the BMP file

        Returns:
            True if capture successful
        """
        save_path_bytes = save_path.encode('utf-8')
        result = self._sdk._sdk.NET_DVR_PlayBackCaptureFile(handle, save_path_bytes)
        return bool(result)

    def playback_control(self, handle: int, command: int) -> bool:
        """
        Control playback (pause, resume, etc.).

        Args:
            handle: Playback handle
            command: Control command (1=pause, 2=resume, 3=fast, 4=slow, etc.)

        Returns:
            True if command successful
        """
        result = self._sdk._sdk.NET_DVR_PlayBackControl_V40(
            handle, command, None, 0, None, None
        )
        return bool(result)

    def get_playback_pos(self, handle: int) -> int:
        """
        Get playback position.

        Args:
            handle: Playback handle

        Returns:
            Position percentage (0-100)
        """
        return self._sdk._sdk.NET_DVR_GetPlayBackPos(handle)

    # ========================================================================
    # PTZ Control Methods
    # ========================================================================

    def ptz_control(
        self,
        channel: int,
        command: int,
        stop: bool = False
    ) -> bool:
        """
        Control PTZ movement.

        Args:
            channel: Channel number
            command: PTZ command (use PTZ_* constants)
            stop: True to stop movement, False to start

        Returns:
            True if command successful

        Example:
            # Pan left
            device.ptz_control(1, PTZ_LEFT)
            time.sleep(1)
            device.ptz_control(1, PTZ_LEFT, stop=True)
        """
        result = self._sdk._sdk.NET_DVR_PTZControl_Other(
            self._user_id,
            channel,
            command,
            1 if stop else 0
        )
        if not result:
            error = self._sdk.get_last_error()
            raise HCNetSDKError(f"PTZ control failed on channel {channel}", error)
        return True

    def ptz_control_with_speed(
        self,
        channel: int,
        command: int,
        speed: int,
        stop: bool = False
    ) -> bool:
        """
        Control PTZ movement with speed.

        Args:
            channel: Channel number
            command: PTZ command (use PTZ_* constants)
            speed: Speed value (1-7)
            stop: True to stop movement, False to start

        Returns:
            True if command successful
        """
        result = self._sdk._sdk.NET_DVR_PTZControlWithSpeed_Other(
            self._user_id,
            channel,
            command,
            1 if stop else 0,
            speed
        )
        if not result:
            error = self._sdk.get_last_error()
            raise HCNetSDKError(f"PTZ control with speed failed on channel {channel}", error)
        return True

    def ptz_preset(
        self,
        channel: int,
        command: int,
        preset_index: int
    ) -> bool:
        """
        Control PTZ presets.

        Args:
            channel: Channel number
            command: Preset command (PTZ_PRESET_SET, PTZ_PRESET_CLEAR, PTZ_PRESET_GOTO)
            preset_index: Preset number (1-255)

        Returns:
            True if command successful

        Example:
            # Save current position as preset 1
            device.ptz_preset(1, PTZ_PRESET_SET, 1)

            # Go to preset 1
            device.ptz_preset(1, PTZ_PRESET_GOTO, 1)
        """
        result = self._sdk._sdk.NET_DVR_PTZPreset_Other(
            self._user_id,
            channel,
            command,
            preset_index
        )
        if not result:
            error = self._sdk.get_last_error()
            raise HCNetSDKError(f"PTZ preset command failed on channel {channel}", error)
        return True

    def ptz_cruise(
        self,
        channel: int,
        command: int,
        cruise_route: int = 0,
        cruise_point: int = 0,
        value: int = 0
    ) -> bool:
        """
        Control PTZ cruise routes.

        Args:
            channel: Channel number
            command: Cruise command (PTZ_CRUISE_RUN, PTZ_CRUISE_STOP, etc.)
            cruise_route: Cruise route number (0-255)
            cruise_point: Cruise point number (for FILL_PRESET)
            value: Preset/speed/dwell value depending on command

        Returns:
            True if command successful

        Example:
            # Run cruise route 1
            device.ptz_cruise(1, PTZ_CRUISE_RUN, cruise_route=1)

            # Stop cruise
            device.ptz_cruise(1, PTZ_CRUISE_STOP, cruise_route=1)
        """
        result = self._sdk._sdk.NET_DVR_PTZCruise_Other(
            self._user_id,
            channel,
            command,
            cruise_route,
            cruise_point,
            value
        )
        if not result:
            error = self._sdk.get_last_error()
            raise HCNetSDKError(f"PTZ cruise command failed on channel {channel}", error)
        return True

    def ptz_track(self, channel: int, command: int) -> bool:
        """
        Control PTZ track/pattern recording and playback.

        Args:
            channel: Channel number
            command: Track command (PTZ_TRACK_START_RECORD, PTZ_TRACK_STOP_RECORD, PTZ_TRACK_RUN)

        Returns:
            True if command successful

        Example:
            # Record a pattern
            device.ptz_track(1, PTZ_TRACK_START_RECORD)
            # ... move camera manually ...
            device.ptz_track(1, PTZ_TRACK_STOP_RECORD)

            # Play the pattern
            device.ptz_track(1, PTZ_TRACK_RUN)
        """
        result = self._sdk._sdk.NET_DVR_PTZTrack_Other(
            self._user_id,
            channel,
            command
        )
        if not result:
            error = self._sdk.get_last_error()
            raise HCNetSDKError(f"PTZ track command failed on channel {channel}", error)
        return True

    # ========================================================================
    # Alarm Methods
    # ========================================================================

    def setup_alarm(
        self,
        callback: Callable[[int, dict, bytes], None],
        level: int = 0
    ) -> int:
        """
        Setup alarm subscription to receive events from the device.

        Args:
            callback: Callback function(command, alarmer_info, alarm_data)
                - command: Alarm type (COMM_ALARM_V30, COMM_ALARM_RULE, etc.)
                - alarmer_info: Dict with device info (ip, serial, etc.)
                - alarm_data: Raw alarm data bytes
            level: Alarm priority level (0=all, 1=high, 2=medium)

        Returns:
            Alarm handle

        Example:
            def on_alarm(cmd, info, data):
                print(f"Alarm from {info['ip']}: command={cmd}")

            handle = device.setup_alarm(on_alarm)
            # ... wait for alarms ...
            device.close_alarm(handle)
        """
        # Setup alarm parameters
        alarm_param = NET_DVR_SETUPALARM_PARAM()
        ctypes.memset(byref(alarm_param), 0, ctypes.sizeof(alarm_param))
        alarm_param.dwSize = ctypes.sizeof(alarm_param)
        alarm_param.byLevel = level
        alarm_param.byAlarmInfoType = 1
        alarm_param.byRetAlarmTypeV40 = 1

        # Create callback wrapper
        def _alarm_callback(command, alarmer, alarm_info, buf_len, user):
            try:
                # Extract alarmer info
                info = {}
                if alarmer:
                    a = alarmer.contents
                    if a.byDeviceIPValid:
                        info['ip'] = a.sDeviceIP.decode('utf-8', errors='ignore').rstrip('\x00')
                    if a.bySerialValid:
                        info['serial'] = bytes(a.sSerialNumber).rstrip(b'\x00').decode('utf-8', errors='ignore')
                    if a.byDeviceNameValid:
                        info['name'] = a.sDeviceName.decode('utf-8', errors='ignore').rstrip('\x00')
                    info['user_id'] = a.lUserID

                # Get alarm data
                data = alarm_info[:buf_len] if alarm_info else b''

                callback(command, info, data)
            except Exception:
                pass
            return True

        c_callback = MSGNOTESSTREAMCALLBACK(_alarm_callback)
        self._callbacks.append(c_callback)

        # Set the callback first
        if not self._sdk._sdk.NET_DVR_SetDVRMessageCallBack_V50(0, c_callback, None):
            error = self._sdk.get_last_error()
            raise HCNetSDKError("Failed to set alarm callback", error)

        # Setup alarm channel
        # Note: Returns -1 on failure, valid handles are >= 0
        handle = self._sdk._sdk.NET_DVR_SetupAlarmChan_V41(self._user_id, byref(alarm_param))
        if handle == -1:
            error = self._sdk.get_last_error()
            raise HCNetSDKError("Failed to setup alarm channel", error)

        return handle

    def close_alarm(self, handle: int) -> bool:
        """
        Close alarm subscription.

        Args:
            handle: Alarm handle from setup_alarm()

        Returns:
            True if closed successfully
        """
        result = self._sdk._sdk.NET_DVR_CloseAlarmChan_V30(handle)
        if not result:
            error = self._sdk.get_last_error()
            raise HCNetSDKError("Failed to close alarm channel", error)
        return True

    # ========================================================================
    # Device Configuration Methods
    # ========================================================================

    def get_device_config(self) -> DeviceConfig:
        """
        Get device configuration.

        Returns:
            DeviceConfig object with parsed device information
        """
        # Use NET_DVR_GET_DEVICECFG_V40 (command 1100) with proper structure
        config = NET_DVR_DEVICECFG_V40()
        config.dwSize = ctypes.sizeof(NET_DVR_DEVICECFG_V40)
        bytes_returned = DWORD(0)

        result = self._sdk._sdk.NET_DVR_GetDVRConfig(
            self._user_id,
            1100,  # NET_DVR_GET_DEVICECFG_V40
            0xFFFFFFFF,  # All channels
            ctypes.byref(config),
            ctypes.sizeof(NET_DVR_DEVICECFG_V40),
            ctypes.byref(bytes_returned)
        )

        if not result:
            error = self._sdk.get_last_error()
            raise HCNetSDKError("Failed to get device config", error)

        # Parse the structure into a DeviceConfig dataclass
        return DeviceConfig(
            device_name=bytes(config.sDVRName).rstrip(b'\x00').decode('utf-8', errors='ignore'),
            device_id=config.dwDVRID,
            serial_number=bytes(config.sSerialNumber).rstrip(b'\x00').decode('utf-8', errors='ignore'),
            software_version=_parse_version(config.dwSoftwareVersion),
            software_build_date=_parse_build_date(config.dwSoftwareBuildDate),
            hardware_version=_parse_version(config.dwHardwareVersion),
            dsp_version=_parse_version(config.dwDSPSoftwareVersion),
            dsp_build_date=_parse_build_date(config.dwDSPSoftwareBuildDate),
            panel_version=_parse_version(config.dwPanelVersion),
            device_type=config.byDVRType,
            device_type_name=bytes(config.byDevTypeName).rstrip(b'\x00').decode('utf-8', errors='ignore'),
            channel_count=config.byChanNum,
            start_channel=config.byStartChan,
            ip_channel_count=config.byIPChanNum + (config.byHighIPChanNum << 8),
            alarm_in_count=config.byAlarmInPortNum,
            alarm_out_count=config.byAlarmOutPortNum,
            disk_count=config.byDiskNum,
            audio_count=config.byAudioNum,
            recycle_record=bool(config.dwRecycleRecord),
        )

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.logout()
        return False

    def __repr__(self):
        return f"Device({self._ip}:{self._port}, user_id={self._user_id})"


class FileInfo:
    """Represents information about a recorded file."""

    def __init__(
        self,
        filename: str,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        file_size: int,
        is_locked: bool,
        file_type: int,
        stream_type: int
    ):
        self._filename = filename
        self._start_time = start_time
        self._end_time = end_time
        self._file_size = file_size
        self._is_locked = is_locked
        self._file_type = file_type
        self._stream_type = stream_type

    @classmethod
    def _from_struct(cls, find_data: NET_DVR_FINDDATA_V50) -> 'FileInfo':
        """Create FileInfo from ctypes structure by copying data."""
        # Extract filename
        filename = find_data.sFileName.decode('utf-8', errors='ignore').rstrip('\x00')

        # Extract start time
        t = find_data.struStartTime
        try:
            if t.wYear == 0 or t.byMonth == 0 or t.byDay == 0:
                start_time = None
            else:
                start_time = datetime(t.wYear, t.byMonth, t.byDay, t.byHour, t.byMinute, t.bySecond)
        except ValueError:
            start_time = None

        # Extract end time
        t = find_data.struStopTime
        try:
            if t.wYear == 0 or t.byMonth == 0 or t.byDay == 0:
                end_time = None
            else:
                end_time = datetime(t.wYear, t.byMonth, t.byDay, t.byHour, t.byMinute, t.bySecond)
        except ValueError:
            end_time = None

        # Extract file size
        if find_data.byBigFileType:
            file_size = (find_data.dwTotalLenH << 32) | find_data.dwTotalLenL
        else:
            file_size = find_data.dwFileSize

        return cls(
            filename=filename,
            start_time=start_time,
            end_time=end_time,
            file_size=file_size,
            is_locked=find_data.byLocked == 1,
            file_type=find_data.byFileType,
            stream_type=find_data.byStreamType
        )

    @property
    def filename(self) -> str:
        """Get the filename."""
        return self._filename

    @property
    def start_time(self) -> Optional[datetime]:
        """Get the recording start time."""
        return self._start_time

    @property
    def end_time(self) -> Optional[datetime]:
        """Get the recording end time."""
        return self._end_time

    @property
    def file_size(self) -> int:
        """Get the file size in bytes."""
        return self._file_size

    @property
    def is_locked(self) -> bool:
        """Check if file is locked."""
        return self._is_locked

    @property
    def file_type(self) -> int:
        """Get the file type."""
        return self._file_type

    @property
    def stream_type(self) -> int:
        """Get the stream type."""
        return self._stream_type

    def __repr__(self):
        start = self.start_time or "N/A"
        end = self.end_time or "N/A"
        return (f"FileInfo('{self.filename}', "
                f"{start} - {end}, "
                f"{self.file_size} bytes)")
