"""
HCNetSDK C Structure Definitions using ctypes

These structures mirror the C structures defined in HCNetSDK.h
for 64-bit Linux (x86_64).
"""

import ctypes
from ctypes import (
    Structure, Union, c_char, c_byte, c_ubyte, c_short, c_ushort,
    c_int, c_uint, c_long, c_ulong, c_void_p, c_char_p, POINTER, CFUNCTYPE
)

from .constants import (
    NET_DVR_DEV_ADDRESS_MAX_LEN,
    NET_DVR_LOGIN_USERNAME_MAX_LEN,
    NET_DVR_LOGIN_PASSWD_MAX_LEN,
    SERIALNO_LEN,
    STREAM_ID_LEN,
)

# Type aliases for Linux 64-bit
# In HCNetSDK.h for Linux:
# BOOL = int, DWORD = unsigned int, WORD = unsigned short
# LONG = int, BYTE = unsigned char, HWND = unsigned int
BOOL = c_int
DWORD = c_uint
WORD = c_ushort
LONG = c_int
BYTE = c_ubyte
HWND = c_uint
UINT = c_uint
LPVOID = c_void_p


# ============================================================================
# Time Structures
# ============================================================================

class NET_DVR_TIME(Structure):
    """Time structure using DWORD fields."""
    _fields_ = [
        ("dwYear", DWORD),
        ("dwMonth", DWORD),
        ("dwDay", DWORD),
        ("dwHour", DWORD),
        ("dwMinute", DWORD),
        ("dwSecond", DWORD),
    ]

    def __repr__(self):
        return (f"NET_DVR_TIME({self.dwYear}-{self.dwMonth:02d}-{self.dwDay:02d} "
                f"{self.dwHour:02d}:{self.dwMinute:02d}:{self.dwSecond:02d})")


class NET_DVR_TIME_SEARCH(Structure):
    """Time structure for file search results."""
    _fields_ = [
        ("wYear", WORD),
        ("byMonth", BYTE),
        ("byDay", BYTE),
        ("byHour", BYTE),
        ("byMinute", BYTE),
        ("bySecond", BYTE),
        ("cTimeDifferenceH", c_char),
        ("cTimeDifferenceM", c_char),
        ("byLocalOrUTC", BYTE),
        ("wMillisecond", WORD),
    ]

    def __repr__(self):
        return (f"NET_DVR_TIME_SEARCH({self.wYear}-{self.byMonth:02d}-{self.byDay:02d} "
                f"{self.byHour:02d}:{self.byMinute:02d}:{self.bySecond:02d})")


class NET_DVR_TIME_SEARCH_COND(Structure):
    """Time condition structure for file search queries."""
    _fields_ = [
        ("wYear", WORD),
        ("byMonth", BYTE),
        ("byDay", BYTE),
        ("byHour", BYTE),
        ("byMinute", BYTE),
        ("bySecond", BYTE),
        ("byLocalOrUTC", BYTE),
        ("wMillisecond", WORD),
        ("cTimeDifferenceH", c_char),
        ("cTimeDifferenceM", c_char),
    ]

    def __repr__(self):
        return (f"NET_DVR_TIME_SEARCH_COND({self.wYear}-{self.byMonth:02d}-{self.byDay:02d} "
                f"{self.byHour:02d}:{self.byMinute:02d}:{self.bySecond:02d})")


# ============================================================================
# IP Address Structures
# ============================================================================

class NET_DVR_IPADDR(Structure):
    """IP address structure."""
    _fields_ = [
        ("sIpV4", c_char * 16),
        ("byIPv6", BYTE * 128),
    ]


class NET_DVR_IPADDR_UNION(Union):
    """IP address union for IPv4/IPv6."""
    _fields_ = [
        ("szIPv4", c_char * 16),
        ("szIPv6", c_char * 256),
    ]


class NET_DVR_ADDRESS(Structure):
    """Address structure with IP and port."""
    _fields_ = [
        ("struIP", NET_DVR_IPADDR),
        ("wPort", WORD),
        ("byRes", BYTE * 2),
    ]


# ============================================================================
# Device Info Structures
# ============================================================================

class NET_DVR_DEVICEINFO_V30(Structure):
    """Device information structure V30."""
    _fields_ = [
        ("sSerialNumber", BYTE * SERIALNO_LEN),
        ("byAlarmInPortNum", BYTE),
        ("byAlarmOutPortNum", BYTE),
        ("byDiskNum", BYTE),
        ("byDVRType", BYTE),
        ("byChanNum", BYTE),
        ("byStartChan", BYTE),
        ("byAudioChanNum", BYTE),
        ("byIPChanNum", BYTE),
        ("byZeroChanNum", BYTE),
        ("byMainProto", BYTE),
        ("bySubProto", BYTE),
        ("bySupport", BYTE),
        ("bySupport1", BYTE),
        ("bySupport2", BYTE),
        ("wDevType", WORD),
        ("bySupport3", BYTE),
        ("byMultiStreamProto", BYTE),
        ("byStartDChan", BYTE),
        ("byStartDTalkChan", BYTE),
        ("byHighDChanNum", BYTE),
        ("bySupport4", BYTE),
        ("byLanguageType", BYTE),
        ("byVoiceInChanNum", BYTE),
        ("byStartVoiceInChanNo", BYTE),
        ("bySupport5", BYTE),
        ("bySupport6", BYTE),
        ("byMirrorChanNum", BYTE),
        ("wStartMirrorChanNo", WORD),
        ("bySupport7", BYTE),
        ("byRes2", BYTE),
    ]


class NET_DVR_DEVICEINFO_V40(Structure):
    """Device information structure V40."""
    _fields_ = [
        ("struDeviceV30", NET_DVR_DEVICEINFO_V30),
        ("bySupportLock", BYTE),
        ("byRetryLoginTime", BYTE),
        ("byPasswordLevel", BYTE),
        ("byProxyType", BYTE),
        ("dwSurplusLockTime", DWORD),
        ("byCharEncodeType", BYTE),
        ("bySupportDev5", BYTE),
        ("bySupport", BYTE),
        ("byLoginMode", BYTE),
        ("dwOEMCode", DWORD),
        ("iResidualValidity", c_int),
        ("byResidualValidity", BYTE),
        ("bySingleStartDTalkChan", BYTE),
        ("bySingleDTalkChanNums", BYTE),
        ("byPassWordResetLevel", BYTE),
        ("bySupportStreamEncrypt", BYTE),
        ("byMarketType", BYTE),
        ("byTLSCap", BYTE),
        ("byRes2", BYTE * 237),
    ]


# ============================================================================
# Login Structures
# ============================================================================

# Forward declaration for callback
LPNET_DVR_DEVICEINFO_V30 = POINTER(NET_DVR_DEVICEINFO_V30)

# Login result callback type
fLoginResultCallBack = CFUNCTYPE(None, LONG, DWORD, LPNET_DVR_DEVICEINFO_V30, c_void_p)


class NET_DVR_USER_LOGIN_INFO(Structure):
    """User login information structure."""
    _fields_ = [
        ("sDeviceAddress", c_char * NET_DVR_DEV_ADDRESS_MAX_LEN),
        ("byUseTransport", BYTE),
        ("wPort", WORD),
        ("sUserName", c_char * NET_DVR_LOGIN_USERNAME_MAX_LEN),
        ("sPassword", c_char * NET_DVR_LOGIN_PASSWD_MAX_LEN),
        ("cbLoginResult", fLoginResultCallBack),
        ("pUser", c_void_p),
        ("bUseAsynLogin", BOOL),
        ("byProxyType", BYTE),
        ("byUseUTCTime", BYTE),
        ("byLoginMode", BYTE),
        ("byHttps", BYTE),
        ("iProxyID", LONG),
        ("byVerifyMode", BYTE),
        ("byRes3", BYTE * 119),
    ]


# ============================================================================
# Preview Structures
# ============================================================================

class NET_DVR_PREVIEWINFO(Structure):
    """Preview configuration structure."""
    _fields_ = [
        ("lChannel", LONG),
        ("dwStreamType", DWORD),
        ("dwLinkMode", DWORD),
        ("hPlayWnd", HWND),
        ("bBlocked", DWORD),
        ("bPassbackRecord", DWORD),
        ("byPreviewMode", BYTE),
        ("byStreamID", BYTE * STREAM_ID_LEN),
        ("byProtoType", BYTE),
        ("byRes1", BYTE),
        ("byVideoCodingType", BYTE),
        ("dwDisplayBufNum", DWORD),
        ("byNPQMode", BYTE),
        ("byRecvMetaData", BYTE),
        ("byDataType", BYTE),
        ("byRes", BYTE * 213),
    ]


# ============================================================================
# Stream Info Structure
# ============================================================================

class NET_DVR_STREAM_INFO(Structure):
    """Stream information structure."""
    _fields_ = [
        ("dwSize", DWORD),
        ("byID", BYTE * STREAM_ID_LEN),
        ("dwChannel", DWORD),
        ("byRes", BYTE * 32),
    ]


# ============================================================================
# File Search Structures
# ============================================================================

class NET_DVR_SPECIAL_FINDINFO_UNION(Union):
    """Special find info union (placeholder)."""
    _fields_ = [
        ("byLen", BYTE * 400),
    ]


class NET_DVR_FILECOND_V50(Structure):
    """File search condition structure V50."""
    _fields_ = [
        ("struStreamID", NET_DVR_STREAM_INFO),
        ("struStartTime", NET_DVR_TIME_SEARCH_COND),
        ("struStopTime", NET_DVR_TIME_SEARCH_COND),
        ("byFindType", BYTE),
        ("byDrawFrame", BYTE),
        ("byQuickSearch", BYTE),
        ("byStreamType", BYTE),
        ("dwFileType", DWORD),
        ("dwVolumeNum", DWORD),
        ("byIsLocked", BYTE),
        ("byNeedCard", BYTE),
        ("byOnlyAudioFile", BYTE),
        ("bySpecialFindInfoType", BYTE),
        ("szCardNum", c_char * 32),
        ("szWorkingDeviceGUID", c_char * 16),
        ("uSpecialFindInfo", NET_DVR_SPECIAL_FINDINFO_UNION),
        ("dwTimeout", DWORD),
        ("byRes", BYTE * 252),
    ]


class NET_DVR_FINDDATA_V50(Structure):
    """File search result structure V50."""
    _fields_ = [
        ("sFileName", c_char * 100),
        ("struStartTime", NET_DVR_TIME_SEARCH),
        ("struStopTime", NET_DVR_TIME_SEARCH),
        ("struAddr", NET_DVR_ADDRESS),
        ("dwFileSize", DWORD),
        ("byLocked", BYTE),
        ("byFileType", BYTE),
        ("byQuickSearch", BYTE),
        ("byStreamType", BYTE),
        ("dwFileIndex", DWORD),
        ("sCardNum", c_char * 32),
        ("dwTotalLenH", DWORD),
        ("dwTotalLenL", DWORD),
        ("byBigFileType", BYTE),
        ("byRes", BYTE * 247),
    ]


# ============================================================================
# JPEG Capture Structure
# ============================================================================

class NET_DVR_JPEGPARA(Structure):
    """JPEG capture parameters."""
    _fields_ = [
        ("wPicQuality", WORD),  # 0-best, 1-better, 2-normal
        ("wPicSize", WORD),     # 0-CIF, 1-QCIF, 2-D1, etc.
    ]


# ============================================================================
# Alarm Structures
# ============================================================================

class NET_DVR_SETUPALARM_PARAM(Structure):
    """Alarm setup parameters."""
    _fields_ = [
        ("dwSize", DWORD),
        ("byLevel", BYTE),              # Alarm priority: 0-all, 1-high, 2-medium
        ("byAlarmInfoType", BYTE),      # Alarm info type
        ("byRetAlarmTypeV40", BYTE),    # Return V40 alarm type
        ("byRetDevInfoVersion", BYTE),  # Return device info version
        ("byRetVQDAlarmType", BYTE),    # Return VQD alarm type
        ("byFaceAlarmDetection", BYTE), # Face alarm detection
        ("bySupport", BYTE),
        ("byBrokenNetHttp", BYTE),
        ("wTaskNo", WORD),
        ("byDeployType", BYTE),
        ("byRes1", BYTE * 3),
        ("byAlarmTypeURL", BYTE),
        ("byCustomCtrl", BYTE),
        ("byRes2", BYTE * 128),
    ]


class NET_DVR_ALARMER(Structure):
    """Alarm device info."""
    _fields_ = [
        ("byUserIDValid", BYTE),
        ("bySerialValid", BYTE),
        ("byVersionValid", BYTE),
        ("byDeviceNameValid", BYTE),
        ("byMacAddrValid", BYTE),
        ("byLinkPortValid", BYTE),
        ("byDeviceIPValid", BYTE),
        ("bySocketIPValid", BYTE),
        ("lUserID", LONG),
        ("sSerialNumber", BYTE * SERIALNO_LEN),
        ("dwDeviceVersion", DWORD),
        ("sDeviceName", c_char * 32),
        ("byMacAddr", BYTE * 6),
        ("wLinkPort", WORD),
        ("sDeviceIP", c_char * 128),
        ("sSocketIP", c_char * 128),
        ("byIpProtocol", BYTE),
        ("byRes1", BYTE * 2),
        ("bJSONBr498", BYTE),
        ("wSocketPort", WORD),
        ("byRes2", BYTE * 6),
    ]


class NET_DVR_ALARMINFO_V30(Structure):
    """Alarm info V30 structure."""
    _fields_ = [
        ("dwAlarmType", DWORD),
        ("dwAlarmInputNumber", DWORD),
        ("byAlarmOutputNumber", BYTE * 96),
        ("byAlarmRelateChannel", BYTE * 64),
        ("byChannel", BYTE * 64),
        ("byDiskNumber", BYTE * 33),
        ("byRes", BYTE * 3),
    ]


# ============================================================================
# Device Config Structures
# ============================================================================

class NET_DVR_DEVICECFG_V40(Structure):
    """Device configuration V40."""
    _fields_ = [
        ("dwSize", DWORD),
        ("sDVRName", BYTE * 32),
        ("dwDVRID", DWORD),
        ("dwRecycleRecord", DWORD),
        ("sSerialNumber", BYTE * SERIALNO_LEN),
        ("dwSoftwareVersion", DWORD),
        ("dwSoftwareBuildDate", DWORD),
        ("dwDSPSoftwareVersion", DWORD),
        ("dwDSPSoftwareBuildDate", DWORD),
        ("dwPanelVersion", DWORD),
        ("dwHardwareVersion", DWORD),
        ("byAlarmInPortNum", BYTE),
        ("byAlarmOutPortNum", BYTE),
        ("byRS232Num", BYTE),
        ("byRS485Num", BYTE),
        ("byNetworkPortNum", BYTE),
        ("byDiskCtrlNum", BYTE),
        ("byDiskNum", BYTE),
        ("byDVRType", BYTE),
        ("byChanNum", BYTE),
        ("byStartChan", BYTE),
        ("byDecordChans", BYTE),
        ("byVGANum", BYTE),
        ("byUSBNum", BYTE),
        ("byAuxoutNum", BYTE),
        ("byAudioNum", BYTE),
        ("byIPChanNum", BYTE),
        ("byZeroChanNum", BYTE),
        ("bySupport", BYTE),
        ("byEsataUseage", BYTE),
        ("byIPCPlug", BYTE),
        ("byStorageMode", BYTE),
        ("bySupport1", BYTE),
        ("wDevType", WORD),
        ("byDevTypeName", BYTE * 24),
        ("bySupport2", BYTE),
        ("byAnalogAlarmInPortNum", BYTE),
        ("byStartAlarmInNo", BYTE),
        ("byStartAlarmOutNo", BYTE),
        ("byStartIPAlarmInNo", BYTE),
        ("byStartIPAlarmOutNo", BYTE),
        ("byHighIPChanNum", BYTE),
        ("byEnableRemotePowerOn", BYTE),
        ("wDevClass", WORD),
        ("byRes2", BYTE * 6),
    ]


# ============================================================================
# Callback Type Definitions
# ============================================================================

# Real data callback: void (CALLBACK *)(LONG lPlayHandle, DWORD dwDataType, BYTE *pBuffer, DWORD dwBufSize, void* pUser)
REALDATACALLBACK = CFUNCTYPE(None, LONG, DWORD, POINTER(BYTE), DWORD, c_void_p)

# Playback/download data callback
fPlayDataCallBack = CFUNCTYPE(None, LONG, DWORD, POINTER(BYTE), DWORD, DWORD)

# Alarm callback: BOOL (CALLBACK *)(LONG lCommand, NET_DVR_ALARMER *pAlarmer, char *pAlarmInfo, DWORD dwBufLen, void* pUser)
MSGNOTESSTREAMCALLBACK = CFUNCTYPE(BOOL, LONG, POINTER(NET_DVR_ALARMER), c_char_p, DWORD, c_void_p)


# ============================================================================
# Pointer Type Aliases
# ============================================================================

LPNET_DVR_USER_LOGIN_INFO = POINTER(NET_DVR_USER_LOGIN_INFO)
LPNET_DVR_DEVICEINFO_V40 = POINTER(NET_DVR_DEVICEINFO_V40)
LPNET_DVR_PREVIEWINFO = POINTER(NET_DVR_PREVIEWINFO)
LPNET_DVR_FILECOND_V50 = POINTER(NET_DVR_FILECOND_V50)
LPNET_DVR_FINDDATA_V50 = POINTER(NET_DVR_FINDDATA_V50)
LPNET_DVR_JPEGPARA = POINTER(NET_DVR_JPEGPARA)
LPNET_DVR_TIME = POINTER(NET_DVR_TIME)
LPNET_DVR_SETUPALARM_PARAM = POINTER(NET_DVR_SETUPALARM_PARAM)
LPNET_DVR_ALARMER = POINTER(NET_DVR_ALARMER)
LPNET_DVR_DEVICECFG_V40 = POINTER(NET_DVR_DEVICECFG_V40)
