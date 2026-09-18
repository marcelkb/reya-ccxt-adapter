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


def test_default_stays_v1_before_the_cutover(tmp_path):
    out = runProbe(tmp_path, REYA_V2_SWITCH_AT="2099-01-01T00:00:00Z", **sdkEnv())
    assert out.returncode == 0, out.stderr
    assert out.stdout.split()[:2] == ["v1", "False"]


def test_default_switches_to_v2_after_the_cutover(tmp_path):
    out = runProbe(tmp_path, REYA_V2_SWITCH_AT="2000-01-01T00:00:00Z", **sdkEnv())
    assert out.returncode == 0, out.stderr
    assert out.stdout.split()[:2] == ["v2", "True"]


def test_explicit_v1_ignores_the_cutover(tmp_path):
    # a pinned version must never move on its own, whatever the clock says
    out = runProbe(tmp_path, REYA_API_VERSION="v1", REYA_V2_SWITCH_AT="2000-01-01T00:00:00Z", **sdkEnv())
    assert out.returncode == 0, out.stderr
    assert out.stdout.split()[:2] == ["v1", "False"]


def test_switch_time_is_read_from_dotenv(tmp_path):
    (tmp_path / ".env").write_text("REYA_V2_SWITCH_AT=2000-01-01T00:00:00Z" + chr(10))
    out = runProbe(tmp_path, **sdkEnv())
    assert out.returncode == 0, out.stderr
    assert out.stdout.split()[:2] == ["v2", "True"]


def test_unparsable_switch_time_fails_loudly(tmp_path):
    out = runProbe(tmp_path, REYA_V2_SWITCH_AT="next tuesday", **sdkEnv())
    assert out.returncode != 0
    assert "REYA_V2_SWITCH_AT" in out.stderr


def test_switch_due_flags_a_process_left_on_v1(tmp_path):
    probe = ("import reya_ccxt_adapter.Reya as m, reya_ccxt_adapter.sdk_loader as l; "
             "print(m.API_VERSION, l.switchDue())")
    env = {k: v for k, v in os.environ.items() if not k.startswith("REYA_") and k != "PYTHONPATH"}
    env["PYTHONPATH"] = REPO
    env.update(sdkEnv())
    # imported before the cutover, then the clock passes it: the SDK in this
    # process stays v1, so the caller has to restart
    env["REYA_V2_SWITCH_AT"] = "2099-01-01T00:00:00Z"
    before = subprocess.run([sys.executable, "-c", probe], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=120)
    assert before.stdout.split() == ["v1", "False"], before.stderr
    late = ("import os, reya_ccxt_adapter.Reya as m, reya_ccxt_adapter.sdk_loader as l; "
            "os.environ['REYA_V2_SWITCH_AT'] = '2000-01-01T00:00:00Z'; "
            "print(m.API_VERSION, l.switchDue())")
    after = subprocess.run([sys.executable, "-c", late], cwd=tmp_path, env=env,
                           capture_output=True, text=True, timeout=120)
    assert after.stdout.split() == ["v1", "True"], after.stderr


def test_wrong_sdk_fails_with_install_hint(tmp_path):
    # the v2 flag pointed at the v1 SDK directory
    out = runProbe(tmp_path, REYA_API_VERSION="v2", REYA_SDK_V2_PATH=SDK_DIRS["v1"])
    assert out.returncode != 0
    assert "REYA_API_VERSION=v2" in out.stderr and "speaks v1" in out.stderr
    assert "pip install --no-deps --target" in out.stderr


def test_unknown_version_fails(tmp_path):
    out = runProbe(tmp_path, REYA_API_VERSION="v3", **sdkEnv())
    assert out.returncode != 0
    assert "REYA_API_VERSION must be auto or one of" in out.stderr
