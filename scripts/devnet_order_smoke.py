"""Devnet order smoke for the v2 API: places and cancels real devnet orders.

Reads DEV_OWNER_WALLET_ADDRESS / DEV_PRIVATE_KEY / DEV_ACCOUNT_ID from the .env found
from the working directory. The key must be a signer authorized for that account.

    REYA_API_VERSION=v2 python scripts/devnet_order_smoke.py              # resting limit + cancel
    REYA_API_VERSION=v2 python scripts/devnet_order_smoke.py --position   # also a 0.001 BTC round trip
                                                                          # with SL/TP (needs collateral)
"""
import os, sys, time
try:
    import truststore; truststore.inject_into_ssl()  # Windows TLS for requests
except ImportError:
    pass
from dotenv import dotenv_values, find_dotenv
v = dotenv_values(find_dotenv(usecwd=True))
for n in ("OWNER_WALLET_ADDRESS", "PRIVATE_KEY", "ACCOUNT_ID", "CHAIN_ID", "REYA_API_URL"):
    os.environ.pop(n, None)
from reya_ccxt_adapter import Reya as M
ex = M.Reya({"walletAddress": v["DEV_OWNER_WALLET_ADDRESS"].strip(), "privateKey": v["DEV_PRIVATE_KEY"].strip(),
             "options": {"account_id": int(v["DEV_ACCOUNT_ID"])}, "sandbox": True})
S = "BTC/RUSD:RUSD"
print("REYA_V2", M.REYA_V2, "chain", ex.client.config.chain_id, "api", ex.client.config.api_url, "dex", ex.client.config.dex_id)
ex.load_markets()

def step(name, fn):
    try:
        out = fn()
        print("OK ", name, "->", out)
        return out
    except Exception as e:
        print("ERR", name, "->", type(e).__name__, getattr(e, "body", None) or str(e)[-400:])
        return None

def brief(o):
    return o and {k: o.get(k) for k in ("id", "status", "type", "side", "amount", "filled", "price", "average", "reduceOnly", "stopPrice", "triggerPrice")}

bal = step("fetch_balance", lambda: ex.fetch_balance()["RUSD"])
last = ex.fetch_ticker(S)["last"]
print("last", last)
lim = step("post-only limit @50%", lambda: brief(ex.create_order(S, "limit", "buy", 0.001, round(last * 0.5, 0), {"postOnly": True})))
time.sleep(2)
step("open orders", lambda: [brief(o) for o in ex.fetch_open_orders(S)])
if lim:
    step("cancel limit", lambda: ex.cancel_order(lim["id"], S))
    time.sleep(2)
    step("open orders after cancel", lambda: [o["id"] for o in ex.fetch_open_orders(S)])
if "--position" not in sys.argv:
    ex.close(); sys.exit()
mkt = step("market buy 0.001", lambda: brief(ex.create_order(S, "market", "buy", 0.001, round(last * 1.01, 0), {})))
time.sleep(3)
pos = step("position", lambda: {k: ex.fetch_position(S).get(k) for k in ("contracts", "side", "entryPrice", "unrealizedPnl")})
sl = step("stop loss -5%", lambda: brief(ex.create_order(S, "limit", "sell", 0.001, round(last * 0.95, 0), {"stopLossPrice": round(last * 0.95, 0), "reduceOnly": True})))
tp = step("take profit +5%", lambda: brief(ex.create_order(S, "limit", "sell", 0.001, round(last * 1.05, 0), {"takeProfitPrice": round(last * 1.05, 0), "reduceOnly": True})))
time.sleep(2)
step("open orders with triggers", lambda: [brief(o) for o in ex.fetch_open_orders(S)])
for name, o in (("cancel SL", sl), ("cancel TP", tp)):
    if o:
        step(name, lambda o=o: ex.cancel_order(o["id"], S))
close = step("reduce-only market sell 0.001", lambda: brief(ex.create_order(S, "market", "sell", 0.001, round(last * 0.99, 0), {"reduceOnly": True})))
time.sleep(3)
step("position after close", lambda: ex.fetch_position(S).get("contracts"))
step("open orders at end", lambda: [o["id"] for o in ex.fetch_open_orders(S)])
step("my trades", lambda: [(t["side"], t["amount"], t["price"], t["order"]) for t in ex.fetch_my_trades(S)[-4:]])
ex.close()
