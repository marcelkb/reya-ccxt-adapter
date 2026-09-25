"""Reports which reya-python-sdk the adapter is running on.

Reya's v1 API needs reya-python-sdk 2.2.x, the v2 order book ("perpOB") needs
3.x. Both install as the top-level package `sdk`, so a venv holds exactly one of
them and whichever is installed decides: upgrading to v2 means installing the
3.x SDK over the 2.2.x one and restarting the process. There is no flag to set
and no second copy to keep -- see the README for the install commands.

The .env is loaded here because the SDK reads its own settings (REYA_DEX_ID and
friends) from the environment while it is imported, which happens below.
"""
from dotenv import find_dotenv, load_dotenv


def loadDotenv():
    path = find_dotenv(usecwd=True)
    if path:
        load_dotenv(path)


def loadSdk() -> str:
    """Import the installed SDK and report which API it speaks."""
    loadDotenv()
    import reya_ccxt_adapter.sdk_patch  # noqa: F401  (before anything imports sdk._version)
    from sdk.open_api import OrderType
    # 3.x renamed the trigger kinds TP/SL -> TAKE_PROFIT/STOP_LOSS
    return "v2" if hasattr(OrderType, "STOP_LOSS") else "v1"


API_VERSION = loadSdk()
