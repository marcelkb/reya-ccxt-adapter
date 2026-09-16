"""Offline tests for the Reya adapter under both SDK lines.

Run once with the v1 SDK (reya-python-sdk 2.2.x) and once with the v2 /
perpOB SDK (3.5.x) installed; the adapter picks its protocol mode from the
installed SDK. No test touches the network.
"""
import os

import pytest

from reya_ccxt_adapter import Reya as ReyaModule
from reya_ccxt_adapter.Reya import Reya

DUMMY_KEY = "0x" + "11" * 32
WALLET = "0x" + "ab" * 20
ACCOUNT_ID = 4242


@pytest.fixture(autouse=True)
def cleanEnv(monkeypatch):
    for name in ("CHAIN_ID", "REYA_API_URL", "OWNER_WALLET_ADDRESS", "PRIVATE_KEY", "ACCOUNT_ID",
                 "PERP_WALLET_ADDRESS_1", "PERP_PRIVATE_KEY_1", "PERP_ACCOUNT_ID_1"):
        monkeypatch.delenv(name, raising=False)


def makeExchange(**extra):
    config = {"walletAddress": WALLET, "privateKey": DUMMY_KEY, "options": {"account_id": ACCOUNT_ID}}
    config.update(extra)
    return Reya(config)


def test_client_config_comes_from_ccxt_credentials():
    ex = makeExchange()
    cfg = ex.client.config
    assert cfg.owner_wallet_address == WALLET
    assert cfg.private_key == DUMMY_KEY
    assert cfg.account_id == ACCOUNT_ID
    assert cfg.chain_id == 1729
    assert cfg.api_url == "https://api.reya.xyz/v2"
    assert ex.urls["api"]["public"] == "https://api.reya.xyz"


def test_testnet_option_targets_devnet():
    ex = makeExchange(sandbox=True)
    cfg = ex.client.config
    assert cfg.chain_id == 89346162
    if ReyaModule.REYA_V2:
        assert cfg.api_url == "https://api-devnet.reya-cronos.network/v2"
    else:
        assert cfg.api_url == "https://api-cronos.reya.xyz/v2"
    assert ex.urls["api"]["public"] + "/v2" == cfg.api_url
