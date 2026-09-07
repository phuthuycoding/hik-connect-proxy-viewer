"""
HCNetSDK Custom Exceptions
"""

from .constants import get_error_message


class HCNetSDKError(Exception):
    """Base exception for HCNetSDK errors."""

    def __init__(self, message: str, error_code: int = None):
        self.error_code = error_code
        if error_code is not None:
            sdk_message = get_error_message(error_code)
            message = f"{message}: {sdk_message} (code: {error_code})"
        super().__init__(message)


class SDKNotInitializedError(HCNetSDKError):
    """SDK has not been initialized."""

    def __init__(self):
        super().__init__("SDK not initialized. Call HCNetSDK.init() first.")


class SDKInitError(HCNetSDKError):
    """Failed to initialize SDK."""
    pass


class LoginError(HCNetSDKError):
    """Failed to login to device."""
    pass


class LogoutError(HCNetSDKError):
    """Failed to logout from device."""
    pass


class PreviewError(HCNetSDKError):
    """Failed to start/stop preview."""
    pass


class FileSearchError(HCNetSDKError):
    """Failed to search for files."""
    pass


class FileDownloadError(HCNetSDKError):
    """Failed to download file."""
    pass


class CaptureError(HCNetSDKError):
    """Failed to capture picture."""
    pass


class LibraryLoadError(HCNetSDKError):
    """Failed to load SDK library."""

    def __init__(self, lib_path: str, details: str = None):
        message = f"Failed to load library: {lib_path}"
        if details:
            message = f"{message}. {details}"
        super().__init__(message)
