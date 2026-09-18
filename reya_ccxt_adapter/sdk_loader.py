"""Picks the reya-python-sdk the adapter runs on, by REYA_API_VERSION.

Reya's v1 API needs reya-python-sdk 2.2.x, the v2 order book ("perpOB") needs
3.5.x. Both install as the top-level package `sdk`, so they cannot share
site-packages. Each version is imported from its own directory when that
directory exists:
    REYA_SDK_V1_PATH / REYA_SDK_V2_PATH, default <venv>/reya_sdk/v1 and /v2
and from site-packages otherwise. Fill a directory with e.g.
    pip install --no-deps --target <venv>/reya_sdk/v2 "git+https://github.com/Reya-Labs/reya-python-sdk@<commit>"

The settings come from the process environment or from the first .env found
from the working directory upwards (loaded without overriding the process
environment, before the SDK reads its own settings such as REYA_DEX_ID).

REYA_API_VERSION defaults to "auto": v1 until Reya's mainnet cutover to the v2
order book, v2 from then on. The moment is REYA_V2_SWITCH_AT (ISO 8601 UTC,
default below). Setting v1 or v2 explicitly pins that version for good. The
choice is made once, when this module is imported, so a process that was
already running at the cutover keeps its old SDK until it restarts -- ask
switchDue() for that case.
"""
import logging
import os
import sys
from datetime import datetime, timezone

from dotenv import find_dotenv, load_dotenv

API_VERSIONS = ("v1", "v2")
AUTO = "auto"
# Reya's mainnet move to the perpOB order book.
DEFAULT_SWITCH_AT = "2026-09-28T13:00:00Z"
SDK_COMMITS = {
    "v1": "3d4c2f68ec308b8c8696d79900a79e1ce2ac322a",  # 2.2.1.0
    "v2": "37450ccb2babc99398d1ac1290d48860a9a2e2fa",  # 3.5.2.0, branch feat/perpOB
}


def loadDotenv():
    path = find_dotenv(usecwd=True)
    if path:
        load_dotenv(path)


def switchAt() -> datetime:
    """The cutover moment, as an aware UTC datetime."""
    raw = os.environ.get("REYA_V2_SWITCH_AT", DEFAULT_SWITCH_AT).strip()
    try:
        moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"REYA_V2_SWITCH_AT must be an ISO 8601 timestamp such as "
                         f"{DEFAULT_SWITCH_AT}, got {raw!r}") from None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def apiVersion() -> str:
    version = os.environ.get("REYA_API_VERSION", AUTO).strip().lower()
    if version == AUTO:
        return "v2" if datetime.now(timezone.utc) >= switchAt() else "v1"
    if version not in API_VERSIONS:
        raise ValueError(f"REYA_API_VERSION must be {AUTO} or one of {API_VERSIONS}, got {version!r}")
    return version


def switchDue() -> bool:
    """True when this process runs v1 although the cutover has passed.

    The SDK cannot be swapped inside a running interpreter, so the caller has to
    restart. Only "auto" is affected: an explicitly pinned v1 is left alone."""
    if API_VERSION != "v1" or os.environ.get("REYA_API_VERSION", AUTO).strip().lower() != AUTO:
        return False
    return datetime.now(timezone.utc) >= switchAt()


_switchLogged = False


def logIfSwitchDue():
    """Says once, loudly, that the process is stuck on the retired API."""
    global _switchLogged
    if _switchLogged or not switchDue():
        return
    _switchLogged = True
    logging.error("🔀 Reya v2 cutover reached (%s)\n"
                  "this process still runs the v1 SDK it loaded at startup\n"
                  "restart it to pick up v2", switchAt().isoformat())


def sdkPath(version: str) -> str:
    return os.environ.get(f"REYA_SDK_{version.upper()}_PATH") or os.path.join(sys.prefix, "reya_sdk", version)


def loadSdk() -> str:
    """Put the SDK for REYA_API_VERSION first on sys.path and check that `sdk`
    resolves to it. Returns the version."""
    loadDotenv()
    version = apiVersion()
    path = sdkPath(version)
    if "sdk" not in sys.modules and os.path.isdir(path) and path not in sys.path:
        sys.path.insert(0, path)
    import reya_ccxt_adapter.sdk_patch  # noqa: F401  (before anything imports sdk._version)
    import sdk
    from sdk.open_api import OrderType
    # 3.x renamed the trigger kinds TP/SL -> TAKE_PROFIT/STOP_LOSS
    loaded = "v2" if hasattr(OrderType, "STOP_LOSS") else "v1"
    if loaded != version:
        raise ImportError(
            f"REYA_API_VERSION={version}, but the reya-python-sdk at {os.path.dirname(sdk.__file__)} "
            f"speaks {loaded}. Install the {version} SDK with:\n"
            f'pip install --no-deps --target "{path}" '
            f'"git+https://github.com/Reya-Labs/reya-python-sdk@{SDK_COMMITS[version]}"')
    return version


API_VERSION = loadSdk()
