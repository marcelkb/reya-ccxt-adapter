"""Whichever reya-python-sdk is installed decides the API version.

Each case imports the adapter in a fresh interpreter, because a process can hold
only one `sdk` package. The two SDKs come from REYA_SDK_V1_PATH /
REYA_SDK_V2_PATH of the test run itself, e.g. filled with
    pip install --no-deps --target <dir>/v2 "git+https://github.com/Reya-Labs/reya-python-sdk@v3.6.1.0"
and put on the probe's PYTHONPATH -- exactly what installing that SDK into the
venv does in production. The tests skip when either is unset.
"""
import os
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SDK_DIRS = {v: os.environ.get(f"REYA_SDK_{v.upper()}_PATH") for v in ("v1", "v2")}
PROBE = ("import reya_ccxt_adapter.Reya as m, sdk; "
         "print(m.API_VERSION, m.REYA_V2, os.path.dirname(os.path.dirname(sdk.__file__)))")

pytestmark = pytest.mark.skipif(not all(SDK_DIRS.values()), reason="REYA_SDK_V1_PATH / REYA_SDK_V2_PATH not set")


def runProbe(cwd, sdkDir, probe=PROBE, **env):
    fullEnv = {k: v for k, v in os.environ.items()
               if not k.startswith("REYA_") and k != "PYTHONPATH"}
    fullEnv["PYTHONPATH"] = os.pathsep.join([REPO, sdkDir])
    fullEnv.update(env)
    return subprocess.run([sys.executable, "-c", "import os; " + probe], cwd=cwd, env=fullEnv,
                          capture_output=True, text=True, timeout=120)


@pytest.mark.parametrize("version, isV2", [("v1", "False"), ("v2", "True")])
def test_installed_sdk_decides_the_api_version(tmp_path, version, isV2):
    out = runProbe(tmp_path, SDK_DIRS[version])
    assert out.returncode == 0, out.stderr
    *flags, sdkDir = out.stdout.split()
    assert flags == [version, isV2]
    assert os.path.normpath(sdkDir) == os.path.normpath(SDK_DIRS[version])


def test_dotenv_is_loaded_before_the_sdk_reads_it(tmp_path):
    # the loader's one remaining job: the SDK takes its own settings from the
    # environment while it is imported, so the .env has to be in place first
    (tmp_path / ".env").write_text("REYA_DEX_ID=4321" + chr(10))
    probe = ("import reya_ccxt_adapter.Reya as m; print(os.environ['REYA_DEX_ID'])")
    out = runProbe(tmp_path, SDK_DIRS["v2"], probe=probe)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "4321"
