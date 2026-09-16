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


EXEC_V1 = {"exchangeId": 1, "symbol": "BTCRUSDPERP", "accountId": ACCOUNT_ID, "qty": "0.01", "side": "B",
           "price": "60000", "fee": "0.24", "type": "ORDER_MATCH", "timestamp": 1747927089946, "sequenceNumber": 7}
EXEC_V2 = {"exchangeId": 2, "symbol": "BTCRUSDPERP", "takerAccountId": 99, "makerAccountId": 98,
           "takerOrderId": "111", "makerOrderId": "222", "qty": "0.01", "side": "B", "price": "60000",
           "takerFee": "0.24", "makerFee": "0.06", "type": "ORDER_MATCH", "timestamp": 1747927089946,
           "sequenceNumber": 7, "fillId": "555"}


def test_parse_trade_v1_execution():
    t = makeExchange().parse_trade(dict(EXEC_V1))
    assert (t["side"], t["amount"], t["price"], t["fee"]["cost"]) == ("buy", 0.01, 60000, 0.24)


def test_parse_trade_v2_as_taker():
    t = makeExchange().parse_trade(dict(EXEC_V2, takerAccountId=ACCOUNT_ID))
    assert (t["side"], t["fee"]["cost"], t["order"], t["id"]) == ("buy", 0.24, "111", "555")


def test_parse_trade_v2_as_maker_flips_side():
    # side is the TAKER's; our resting order took the other side of the fill
    t = makeExchange().parse_trade(dict(EXEC_V2, makerAccountId=ACCOUNT_ID))
    assert (t["side"], t["fee"]["cost"], t["order"], t["id"]) == ("sell", 0.06, "222", "555")


def test_parse_trade_v2_as_maker_without_fee():
    row = dict(EXEC_V2, makerAccountId=ACCOUNT_ID, side="A")
    del row["makerFee"]
    t = makeExchange().parse_trade(row)
    assert (t["side"], t["fee"]["cost"]) == ("buy", 0)


class FakeOrderEntry:
    """Replaces the SDK's OrderEntryApi: keeps the signed request, returns a canned ack."""

    def __init__(self, response):
        self.response = response
        self.requests = []

    async def create_order(self, create_order_request):
        self.requests.append(create_order_request.to_dict())
        return CreateOrderResponse.from_dict(self.response)

    async def cancel_order(self, cancel_order_request):
        self.requests.append(cancel_order_request.to_dict())
        return CancelOrderResponse.from_dict(dict(self.response))


from sdk.open_api import CreateOrderResponse, CancelOrderResponse  # noqa: E402


def makeTradingExchange(response):
    ex, fake = makeLoadedExchange({})
    ex.load_markets()
    ex.client._symbol_to_market_id = {"BTCRUSDPERP": 1}
    orders = FakeOrderEntry(response)
    ex.client._resources.orders = orders
    return ex, orders


def test_stop_loss_trigger_payload():
    ex, orders = makeTradingExchange({"status": "OPEN", "orderId": "77"})
    order = ex.create_order("BTC/RUSD:RUSD", "limit", "sell", 0.01, 60000.0,
                            {"stopLossPrice": 60000.0, "reduceOnly": True})
    sent = orders.requests[0]
    assert order["id"] == "77" and order["status"] == "open"
    assert float(sent["triggerPx"]) == 60000.0
    assert "qty" not in sent or sent["qty"] is None
    if ReyaModule.REYA_V2:
        assert sent["orderType"] == "STOP_LOSS"
        assert sent["timeInForce"] == "GTC"
        assert "reduceOnly" not in sent
        assert float(sent["limitPx"]) == 59700.0  # worst fill 0.5% through the trigger
    else:
        assert sent["orderType"] == "SL"


def test_take_profit_trigger_closing_short_limit_above_trigger():
    ex, orders = makeTradingExchange({"status": "OPEN", "orderId": "78"})
    ex.create_order("BTC/RUSD:RUSD", "limit", "buy", 0.01, 50000.123,
                    {"takeProfitPrice": 50000.123, "reduceOnly": True, "triggerSlippage": 0.01})
    sent = orders.requests[0]
    if ReyaModule.REYA_V2:
        assert sent["orderType"] == "TAKE_PROFIT"
        assert float(sent["limitPx"]) == 50500.13  # 1% above, rounded up to the 0.01 tick
    else:
        assert sent["orderType"] == "TP"


def test_resting_limit_is_open():
    ex, orders = makeTradingExchange({"status": "OPEN", "orderId": "79"})
    order = ex.create_order("BTC/RUSD:RUSD", "limit", "buy", 0.01, 59000.0, {})
    assert (order["id"], order["status"]) == ("79", "open")
    assert orders.requests[0]["timeInForce"] == "GTC"
    assert "reduceOnly" not in orders.requests[0]


@pytest.mark.skipif(not ReyaModule.REYA_V2, reason="v2 acks a no-fill IOC as CANCELLED")
def test_ioc_without_fill_raises_ioc_no_match():
    ex, orders = makeTradingExchange({"status": "CANCELLED", "orderId": "80", "execQty": "0", "cumQty": "0",
                                      "cancelReason": "NO_LIQUIDITY"})
    with pytest.raises(ReyaModule.InvalidOrder) as info:
        ex.create_order("BTC/RUSD:RUSD", "market", "buy", 0.01, 60300.0, {"reduceOnly": True})
    # stat_test's ReyaAdapter.is_ioc_no_match_error keys off these words
    assert "not immediately match" in str(info.value).lower()
    assert orders.requests[0]["reduceOnly"] is True


@pytest.mark.skipif(not ReyaModule.REYA_V2, reason="v2 acks a partial IOC as CANCELLED with cumQty")
def test_partially_filled_ioc_reports_fill():
    ex, orders = makeTradingExchange({"status": "CANCELLED", "orderId": "81", "execQty": "0.004",
                                      "cumQty": "0.004", "cancelReason": "NO_LIQUIDITY"})
    order = ex.create_order("BTC/RUSD:RUSD", "market", "buy", 0.01, 60300.0, {})
    assert (order["id"], order["status"], order["filled"]) == ("81", "canceled", 0.004)


@pytest.mark.skipif(not ReyaModule.REYA_V2, reason="postOnly exists only on v2")
def test_post_only_limit():
    ex, orders = makeTradingExchange({"status": "OPEN", "orderId": "82"})
    ex.create_order("BTC/RUSD:RUSD", "limit", "buy", 0.01, 59000.0, {"postOnly": True})
    assert orders.requests[0]["postOnly"] is True


def test_filled_ioc():
    ex, orders = makeTradingExchange({"status": "FILLED", "orderId": "83", "execQty": "0.01", "cumQty": "0.01"})
    order = ex.create_order("BTC/RUSD:RUSD", "market", "sell", 0.01, 59700.0, {})
    assert (order["id"], order["status"]) == ("83", "filled")
    if ReyaModule.REYA_V2:
        assert order["filled"] == 0.01
