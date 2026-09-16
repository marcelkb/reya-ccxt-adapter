"""REYA_API_VERSION picks the SDK. Each case imports the adapter in a fresh
interpreter, because a process can hold only one `sdk` package.

The SDK directories come from REYA_SDK_V1_PATH / REYA_SDK_V2_PATH of the test
run itself, e.g. filled with
    pip install --no-deps --target <dir>/v2 "git+https://github.com/Reya-Labs/reya-python-sdk@37450cc"
The tests skip when either is unset.
"""
import os
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SDK_DIRS = {v: os.environ.get(f"REYA_SDK_{v.upper()}_PATH") for v in ("v1", "v2")}
PROBE = ("import reya_ccxt_adapter.Reya as m, sdk, sdk._version as v; "
         "print(m.API_VERSION, m.REYA_V2, v.SDK_VERSION, os.path.dirname(os.path.dirname(sdk.__file__)))")

pytestmark = pytest.mark.skipif(not all(SDK_DIRS.values()), reason="REYA_SDK_V1_PATH / REYA_SDK_V2_PATH not set")


def runProbe(cwd, **env):
    fullEnv = {k: v for k, v in os.environ.items()
               if not k.startswith("REYA_") and k != "PYTHONPATH"}
    fullEnv["PYTHONPATH"] = REPO
    fullEnv.update(env)
    return subprocess.run([sys.executable, "-c", "import os; " + PROBE], cwd=cwd, env=fullEnv,
                          capture_output=True, text=True, timeout=120)


def sdkEnv():
    return {"REYA_SDK_V1_PATH": SDK_DIRS["v1"], "REYA_SDK_V2_PATH": SDK_DIRS["v2"]}


@pytest.mark.parametrize("version, isV2, sdkVersion", [("v1", "False", "2.2.1.0"), ("v2", "True", "3.5.2.0")])
def test_flag_selects_sdk(tmp_path, version, isV2, sdkVersion):
    out = runProbe(tmp_path, REYA_API_VERSION=version, **sdkEnv())
    assert out.returncode == 0, out.stderr
    *flags, sdkDir = out.stdout.split()
    assert flags == [version, isV2, sdkVersion]
    assert os.path.normpath(sdkDir) == os.path.normpath(SDK_DIRS[version])


def test_flag_is_read_from_dotenv(tmp_path):
    (tmp_path / ".env").write_text("REYA_API_VERSION=v2\n")
    out = runProbe(tmp_path, **sdkEnv())
    assert out.returncode == 0, out.stderr
    assert out.stdout.split()[:2] == ["v2", "True"]


def test_process_env_beats_dotenv(tmp_path):
    (tmp_path / ".env").write_text("REYA_API_VERSION=v2\n")
    out = runProbe(tmp_path, REYA_API_VERSION="v1", **sdkEnv())
    assert out.returncode == 0, out.stderr
    assert out.stdout.split()[:2] == ["v1", "False"]


def test_default_is_v1(tmp_path):
    out = runProbe(tmp_path, **sdkEnv())
    assert out.returncode == 0, out.stderr
    assert out.stdout.split()[:2] == ["v1", "False"]


def test_wrong_sdk_fails_with_install_hint(tmp_path):
    # the v2 flag pointed at the v1 SDK directory
    out = runProbe(tmp_path, REYA_API_VERSION="v2", REYA_SDK_V2_PATH=SDK_DIRS["v1"])
    assert out.returncode != 0
    assert "REYA_API_VERSION=v2" in out.stderr and "speaks v1" in out.stderr
    assert "pip install --no-deps --target" in out.stderr


def test_unknown_version_fails(tmp_path):
    out = runProbe(tmp_path, REYA_API_VERSION="v3", **sdkEnv())
    assert out.returncode != 0
    assert "REYA_API_VERSION must be one of" in out.stderr
