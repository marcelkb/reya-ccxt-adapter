import sys
import types

def patch_sdk_version():
    # patch sdk since pyproject.toml file is not beeing imported if sdk is used as a lib in version 2.0.6.1
    # Later SDKs ship a working sdk._version; faking it there would misreport
    # the version in the X-SDK-Version header, so only patch when it's missing.
    try:
        import sdk._version  # noqa: F401
        return
    except ImportError:
        pass
    mock_version_module = types.ModuleType('sdk._version')
    mock_version_module.SDK_VERSION = "2.0.6.1"
    sys.modules['sdk._version'] = mock_version_module

    print("✅ SDK Version patched: 2.0.6.1")

patch_sdk_version()