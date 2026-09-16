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


MARKET_DEFS = [{"symbol": "BTCRUSDPERP", "marketId": 1, "minOrderQty": "0.001", "qtyStepSize": "0.001",
                "tickSize": "0.01", "liquidationMarginParameter": "0.05", "initialMarginParameter": "0.04",
                "maxLeverage": 25, "oiCap": "10000"}]
SUMMARY_V1 = {"symbol": "BTCRUSDPERP", "updatedAt": 1747927089946, "longOiQty": "1", "shortOiQty": "1",
              "oiQty": "1", "fundingRate": "-0.0005", "longFundingValue": "4", "shortFundingValue": "4",
              "fundingRateVelocity": "0", "volume24h": "9", "pxChange24h": "1",
              "throttledOraclePrice": "60000.5", "throttledPoolPrice": "60001.5", "pricesUpdatedAt": 1747927089597}
SUMMARY_V2 = {"symbol": "BTCRUSDPERP", "updatedAt": 1747927089946, "oiQty": "1", "fundingRate": "-0.0005",
              "longFundingValue": "4", "shortFundingValue": "4", "volume24h": "9", "pxChange24h": "1",
              "markPrice": "60000.5", "oraclePrice": "60000.0", "throttledMidPrice": "60001.5",
              "pricesUpdatedAt": 1747927089597}
PRICE_V1 = {"symbol": "BTCRUSDPERP", "oraclePrice": "60000.0", "poolPrice": "60001.5", "updatedAt": 1747927089597}


class FakeRest:
    """Stands in for ccxt's HTTP layer: records each path, answers from a table."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __call__(self, path, api="public", method="GET", params={}, headers=None, body=None, config={}):
        self.calls.append((path, dict(params)))
        if path not in self.responses:
            raise AssertionError("unexpected request " + path)
        return self.responses[path]


def makeLoadedExchange(responses):
    ex = makeExchange()
    ex.client._initialized = True  # skip the SDK's market-definition download
    fake = FakeRest(dict({"v2/perpMarketDefinitions": MARKET_DEFS}, **responses))
    ex.request = fake
    return ex, fake


def test_markets_load_from_perp_market_definitions():
    ex, fake = makeLoadedExchange({})
    markets = ex.load_markets()
    assert "BTC/RUSD:RUSD" in markets
    assert fake.calls[0][0] == "v2/perpMarketDefinitions"


def test_funding_rate_reads_perp_market_summary():
    summary = SUMMARY_V2 if ReyaModule.REYA_V2 else SUMMARY_V1
    ex, fake = makeLoadedExchange({"v2/perpMarket/{symbol}/summary": summary})
    fr = ex.fetch_funding_rate("BTC/RUSD:RUSD")
    assert fr["fundingRate"] == -0.0005
    assert ("v2/perpMarket/{symbol}/summary", {"symbol": "BTCRUSDPERP"}) in fake.calls


def test_fetch_ticker_last_price():
    if ReyaModule.REYA_V2:
        ex, fake = makeLoadedExchange({"v2/perpMarket/{symbol}/summary": SUMMARY_V2})
    else:
        ex, fake = makeLoadedExchange({"v2/prices/{symbol}": PRICE_V1})
    ticker = ex.fetch_ticker("BTC/RUSD:RUSD")
    if ReyaModule.REYA_V2:
        assert ticker["last"] == 60000.5  # mark price: what v2 triggers fire on
    else:
        assert ticker["last"] == 60001.5  # pool price, unchanged v1 behaviour


ORACLE_PRICES_V2 = [{"asset": "ETH", "oraclePrice": "2392.5", "updatedAt": 1},
                    {"asset": "wstETH", "oraclePrice": "2976.25", "updatedAt": 1},
                    {"asset": "SRUSD", "oraclePrice": "1.07", "updatedAt": 1}]


@pytest.mark.parametrize("ticker,expected", [("WETHRUSD", 2392.5), ("WSTETHRUSD", 2976.25)])
def test_collateral_price(ticker, expected):
    if ReyaModule.REYA_V2:
        ex, fake = makeLoadedExchange({"v2/assetOraclePrices": ORACLE_PRICES_V2})
    else:
        ex, fake = makeLoadedExchange({"v2/prices/{symbol}": {"symbol": ticker, "oraclePrice": str(expected)}})
    assert ex._getCollateralPriceUsd(ticker) == expected
