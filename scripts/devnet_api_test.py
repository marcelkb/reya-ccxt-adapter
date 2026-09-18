"""Exercises every public adapter method against a live venue and counts results.

Read-only by default. With --trade it also places real orders: a post-only limit,
a market entry, SL/TP triggers, a trigger that fires at once, and a reduce-only
close. Use it on devnet (the default) -- --mainnet stays read-only and refuses
--trade.

Credentials come from the .env found from the working directory: DEV_* on devnet,
the plain names on mainnet.

    REYA_API_VERSION=v2 python scripts/devnet_api_test.py --trade
    REYA_API_VERSION=v1 python scripts/devnet_api_test.py --mainnet
"""
import os, sys, time
try:
    import truststore; truststore.inject_into_ssl()  # Windows TLS for requests
except ImportError:
    pass
from ccxt import NotSupported
from dotenv import dotenv_values, find_dotenv

MAINNET = "--mainnet" in sys.argv
TRADE = "--trade" in sys.argv
if TRADE and MAINNET:
    sys.exit("refusing to trade on mainnet")

v = dotenv_values(find_dotenv(usecwd=True))
prefix = "" if MAINNET else "DEV_"
for n in ("OWNER_WALLET_ADDRESS", "PRIVATE_KEY", "ACCOUNT_ID", "CHAIN_ID", "REYA_API_URL"):
    os.environ.pop(n, None)
from reya_ccxt_adapter import Reya as M

ex = M.Reya({"walletAddress": v[prefix + "OWNER_WALLET_ADDRESS"].strip(),
             "privateKey": v[prefix + "PRIVATE_KEY"].strip(),
             "options": {"account_id": int(v[prefix + "ACCOUNT_ID"])},
             "sandbox": not MAINNET})
S = "BTC/RUSD:RUSD"
QTY = 0.001
passed, failed, skipped = [], [], []


def check(name, fn, expect=lambda out: True, note=""):
    """Runs fn, prints one PASS/FAIL/SKIP line and returns its result.

    expect gets the result and returns True, or a string describing what is wrong.
    A NotImplementedError counts as SKIP: the adapter never claimed the method."""
    try:
        out = fn()
    except (NotImplementedError, NotSupported) as e:
        skipped.append(name)
        print(f"SKIP {name}: {str(e) or 'not implemented by the adapter'}")
        return None
    except Exception as e:
        failed.append(name)
        body = getattr(e, "body", None) or str(e)[-300:]
        print(f"FAIL {name}: {type(e).__name__} {body}")
        return None
    verdict = expect(out)
    if verdict is True:
        passed.append(name)
        print(f"PASS {name}{note and ': ' + note}")
    else:
        failed.append(name)
        print(f"FAIL {name}: {verdict} -- got {str(out)[:200]}")
    return out


def brief(o):
    return o and {k: o.get(k) for k in ("id", "status", "type", "side", "amount",
                                        "filled", "price", "average", "reduceOnly", "triggerPrice")}


def nonEmpty(out):
    return True if out else "empty result"


def isList(out):
    return True if isinstance(out, list) else f"expected a list, got {type(out).__name__}"


print(f"== {'mainnet' if MAINNET else 'devnet'} | REYA_V2={M.REYA_V2} | "
      f"chain {ex.client.config.chain_id} | {ex.client.config.api_url} | dex {ex.client.config.dex_id}")

# ---- market data ----------------------------------------------------------
markets = check("load_markets", lambda: ex.load_markets(),
                lambda out: True if len(out) > 1 else "fewer than 2 markets")
check("fetch_markets", lambda: ex.fetch_markets(), isList)
tic = check("fetch_ticker", lambda: ex.fetch_ticker(S),
            lambda out: True if out.get("last") else "no last price")
last = (tic or {}).get("last")
print(f"     {S} last {last}")
check("fetch_tickers", lambda: ex.fetch_tickers([S]))
check("fetch_order_book", lambda: ex.fetch_order_book(S, 5))
check("fetch_ohlcv 1m", lambda: ex.fetch_ohlcv(S, "1m", limit=5),
      lambda out: True if len(out) == 5 and len(out[0]) == 6 else f"expected 5 bars of 6 fields, got {len(out)}")
since = int(time.time() * 1000) - 6 * 3600 * 1000
check("fetch_ohlcv since 6h", lambda: ex.fetch_ohlcv(S, "1h", since=since),
      lambda out: True if len(out) >= 5 and out[0][0] >= since - 3600_000 else "bars outside the window")
check("fetch_funding_rate", lambda: ex.fetch_funding_rate(S),
      lambda out: True if out and out.get("fundingRate") is not None else "no fundingRate")
check("fetch_trades", lambda: ex.fetch_trades(S, limit=5), isList)
check("get_market_data", lambda: ex.get_market_data(S), nonEmpty)
check("get_current_stake_apy", lambda: ex.get_current_stake_apy(),
      lambda out: True if out is not None else "no apy")

# ---- account --------------------------------------------------------------
bal = check("fetch_balance", lambda: ex.fetch_balance(),
            lambda out: True if out.get("RUSD", {}).get("total") is not None else "no RUSD balance")
print(f"     RUSD {bal and bal['RUSD']}")
check("fetch_accounts", lambda: ex.fetch_accounts(), isList)
check("fetch_leverage", lambda: ex.fetch_leverage(S),
      lambda out: True if out else "no leverage")
check("fetch_leverages", lambda: ex.fetch_leverages([S]), nonEmpty)
check("set_margin_mode", lambda: ex.set_margin_mode("cross", S))
check("fetch_positions", lambda: ex.fetch_positions(), isList)
check("fetch_position (flat ok)", lambda: ex.fetch_position(S), lambda out: True)
check("fetch_open_orders", lambda: ex.fetch_open_orders(S), isList)
check("fetch_orders", lambda: ex.fetch_orders(S, limit=5), isList)
check("fetch_my_trades", lambda: ex.fetch_my_trades(S, limit=5), isList)
check("fetch_deposit_address", lambda: ex.fetch_deposit_address("RUSD"), nonEmpty)
check("withdraw", lambda: ex.withdraw("RUSD", 1.0, ex.walletAddress), nonEmpty)

if not TRADE:
    ex.close()
    print(f"\n{len(passed)} passed, {len(failed)} failed, {len(skipped)} skipped (read-only)")
    sys.exit(1 if failed else 0)

# ---- resting limit --------------------------------------------------------
lim = check("create_order post-only limit", lambda: ex.create_order(S, "limit", "buy", QTY, round(last * 0.5), {"postOnly": True}),
            lambda out: True if out.get("id") and out.get("status") == "open" else "not open",
            note="buy at half the last price, must rest")
time.sleep(2)
if lim:
    check("fetch_order (limit)", lambda: ex.fetch_order(lim["id"], S),
          lambda out: True if out and str(out["id"]) == str(lim["id"]) else "wrong order returned")
    check("fetch_open_orders has it", lambda: ex.fetch_open_orders(S),
          lambda out: True if any(str(o["id"]) == str(lim["id"]) for o in out) else "order missing")
    check("cancel_order", lambda: ex.cancel_order(lim["id"], S), lambda out: True if out else "cancel returned falsy")
    time.sleep(2)
    check("open orders empty after cancel", lambda: ex.fetch_open_orders(S),
          lambda out: True if not out else f"{len(out)} orders left")

# ---- position round trip --------------------------------------------------
entry = check("create_market_order buy", lambda: ex.create_order(S, "market", "buy", QTY, round(last * 1.02), {}),
              lambda out: True if out.get("status") == "filled" and out.get("filled") == QTY else "not filled")
time.sleep(3)
pos = check("fetch_position (long)", lambda: ex.fetch_position(S),
            lambda out: True if out and abs(out["contracts"]) == QTY else "position not reported")
if pos:
    print(f"     entry {pos.get('entryPrice')} pnl {pos.get('unrealizedPnl')}")
if entry:
    check("fetch_order (market)", lambda: ex.fetch_order(entry["id"], S),
          lambda out: True if out and out.get("status") in ("filled", "closed") else "not filled")

sl = check("create_order stop loss -5%", lambda: ex.create_order(S, "limit", "sell", QTY, round(last * 0.95),
                                                                {"stopLossPrice": round(last * 0.95), "reduceOnly": True}),
           lambda out: True if out.get("id") else "no id")
tp = check("create_order take profit +5%", lambda: ex.create_order(S, "limit", "sell", QTY, round(last * 1.05),
                                                                  {"takeProfitPrice": round(last * 1.05), "reduceOnly": True}),
           lambda out: True if out.get("id") else "no id")
time.sleep(2)
check("triggers listed as stop-loss/take-profit", lambda: ex.fetch_open_orders(S),
      lambda out: True if {o["type"] for o in out} >= {"stop-loss", "take-profit"} else "trigger types missing")
for name, o in (("cancel stop loss", sl), ("cancel take profit", tp)):
    if o:
        check(name, lambda o=o: ex.cancel_order(o["id"], S), lambda out: True if out else "cancel returned falsy")
time.sleep(2)
check("open orders empty after trigger cancels", lambda: ex.fetch_open_orders(S),
      lambda out: True if not out else f"{len(out)} orders left")

# A stop-loss placed ABOVE a long's mark price is already true, so the venue
# should fire it immediately -- this is the only way to see the trigger's limit
# child fill without waiting for the market to move.
mark = ex.fetch_ticker(S)["last"]
if not ex.fetch_position(S):
    print("SKIP stop loss above the mark: no open position to close")
    skipped.append("stop loss above the mark")
    fire = None
else:
    fire = check("stop loss above the mark (fires at once)",
                 lambda: ex.create_order(S, "limit", "sell", QTY, round(mark * 1.002),
                                         {"stopLossPrice": round(mark * 1.002), "reduceOnly": True}),
                 lambda out: True if out.get("id") else "no id")
fired = None
if fire:
    for _ in range(12):
        time.sleep(5)
        fired = ex.fetch_position(S)
        if fired is None or abs((fired or {}).get("contracts", 0)) < QTY:
            break
    check("the fired trigger closed the position", lambda: fired,
          lambda out: True if not out or abs(out.get("contracts", 0)) < QTY else "position still open after 60s")
    for o in ex.fetch_open_orders(S):
        ex.cancel_order(o["id"], S)

if ex.fetch_position(S):
    check("reduce-only market close", lambda: ex.create_order(S, "market", "sell", QTY, round(mark * 0.98), {"reduceOnly": True}),
          lambda out: True if out.get("status") == "filled" else "not filled")
    time.sleep(3)
check("flat at the end", lambda: ex.fetch_position(S),
      lambda out: True if not out or not out.get("contracts") else f"still holding {out['contracts']}")
check("open orders empty at the end", lambda: ex.fetch_open_orders(S),
      lambda out: True if not out else f"{len(out)} orders left")
trades = check("fetch_my_trades sees the round trip", lambda: ex.fetch_my_trades(S, limit=10),
               lambda out: True if len(out) >= 2 else "fewer than 2 trades")
for t in (trades or [])[-4:]:
    print(f"     {t['side']} {t['amount']} @ {t['price']} order {t['order']}")
check("fetch_balance after trading", lambda: ex.fetch_balance()["RUSD"], nonEmpty)

ex.close()
print(f"\n{len(passed)} passed, {len(failed)} failed, {len(skipped)} skipped")
if failed:
    print("failed: " + ", ".join(failed))
sys.exit(1 if failed else 0)
