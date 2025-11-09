import sys
import types

def patch_sdk_version():
    # patch sdk since pyproject.toml file is not beeing imported if sdk is used as a lib in version 2.0.6.1
    mock_version_module = types.ModuleType('sdk._version')
    mock_version_module.SDK_VERSION = "2.0.6.1"
    sys.modules['sdk._version'] = mock_version_module

    print("✅ SDK Version patched: 2.0.6.1")

patch_sdk_version()