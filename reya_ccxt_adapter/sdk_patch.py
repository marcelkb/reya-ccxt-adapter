import logging
import sys
import types
from importlib.metadata import PackageNotFoundError, version

def patch_sdk_version():
    # patch sdk since pyproject.toml file is not beeing imported if sdk is used as a lib in version 2.0.6.1
    # (2.2.1.0 still raises ValueError for it). Later SDKs ship a working sdk._version; faking it there
    # would misreport the version in the X-SDK-Version header, so only patch when it fails.
    try:
        import sdk._version  # noqa: F401
        return
    except (ImportError, ValueError):
        pass
    try:
        sdkVersion = version("reya-python-sdk")
    except PackageNotFoundError:
        sdkVersion = "2.0.6.1"
    mock_version_module = types.ModuleType('sdk._version')
    mock_version_module.SDK_VERSION = sdkVersion
    sys.modules['sdk._version'] = mock_version_module

    logging.info("✅ SDK Version patched: %s", sdkVersion)

patch_sdk_version()
