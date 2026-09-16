# Reya CCXT Adapter 
A CCXT-compatible adapter/wrapper for the Reya Python SDK. It maps Reya SDK methods onto familiar CCXT interfaces.

- CCXT: https://github.com/ccxt/ccxt
- Reya SDK (Python): https://github.com/Reya-Labs/reya-python-sdk

# Features
- CCXT-style API backed by the Reya SDK
- Simple environment-based configuration
- Python 3.11+ support, aiohttp till 3.9.3

Right now not all methods functions are implemented.
 - fetchOHLCV delegates to Binance since Reya only support candles up to 1D-Timeframe and no easy management for calling last X Candles. Start und End Time is needed every time. Additonally the api is not as fast for complicated calculations based on a lot of candles.
 - The Signer for Private calls is not finished, so it relays on the SDK functions.
 - fetchBalance only recognized RUSD. Different Tokens for Collateral are not supported right now (wrtETH f.e.)
 - fetch_canceled_and_closed_orders not supported right now
 - setLeverage not supported right now (no reya api endpoint)
 - short orders can be placed but are not fully considered by profit calculation
   
# Reya Python SDK

For installation and inclusion in another projects use

```
pip install {localpath}\reya-ccxt-adapter
or
pip install git+https://github.com/marcelkb/reya-ccxt-adapter
```

For installation and inclusion of reya SDK use

```
pip install {localpath}\reya-python-sdk
or
pip install git+https://github.com/Reya-Labs/reya-python-sdk
```


## API version (v1 / v2)

Reya's current API (v1) needs reya-python-sdk 2.2.x; the v2 order book ("perpOB",
mainnet from 2026-09-28) needs 3.5.x. Both install as the package `sdk`, so the v2 SDK
lives in its own directory and `REYA_API_VERSION` picks one at import time:

```
REYA_API_VERSION=v1   # default; v2 for the perpOB API
```

It is read from the process environment or the first `.env` found from the working
directory upwards. Install the v2 SDK next to the regular one (Python 3.12+):

```
pip install --no-deps --target <venv>/reya_sdk/v2 "git+https://github.com/Reya-Labs/reya-python-sdk@37450ccb2babc99398d1ac1290d48860a9a2e2fa"
```

`<venv>/reya_sdk/v1` works the same way for the v1 SDK; without it v1 imports `sdk` from
site-packages. `REYA_SDK_V1_PATH` / `REYA_SDK_V2_PATH` override the directories. Importing the
adapter fails with the install command when the selected SDK is not the one found.
Credentials may use either SDK's env names (`OWNER_WALLET_ADDRESS` / `PRIVATE_KEY` /
`ACCOUNT_ID` or `PERP_WALLET_ADDRESS_1` / `PERP_PRIVATE_KEY_1` / `PERP_ACCOUNT_ID_1`);
`reya_ccxt_adapter.Reya.tradingConfigFromEnv()` reads them for both. For the devnet pass
`{"sandbox": True}`; v2 also reads `REYA_DEX_ID` and `REYA_ORDERS_GATEWAY`.

Tests: `REYA_API_VERSION=v1 pytest tests` and `REYA_API_VERSION=v2 pytest tests`; the loader
tests need `REYA_SDK_V1_PATH` and `REYA_SDK_V2_PATH`.

## Environment Setup

Create a `.env` file in the project root with the following variables:

```
ACCOUNT_ID=your_account_id
PRIVATE_KEY=your_private_key
CHAIN_ID=1729                   # Use 89346162 for testnet
REYA_WS_URL=wss://ws.reya.xyz/  # Use wss://websocket-testnet.reya.xyz/ for testnet
REYA_API_BASE_URL=https://api.reya.xyz/v2  # Use https://api-test.reya.xyz/v2 for testnet
OWNER_WALLET_ADDRESS=your_wallet_address    # Required: wallet address for data queries
```

## Usage

```
from reya_ccxt_adapter.Reya import Reya
from reya_ccxt_adapter.const import EOrderSide, EOrderType
from sdk.reya_rest_api import TradingConfig

    load_dotenv()
    config = TradingConfig.from_env()

    exchange = Reya({
        'walletAddress': config.owner_wallet_address,
        'privateKey': config.private_key,
        'options':{'account_id': config.account_id},
        'verbose': True,
    })
    
    symbol = 'SOL/RUSD:RUSD'  # market symbol
    ticker = exchange.fetch_ticker(symbol)
    print(f"{symbol} price: {ticker['last']}")
    
    position = exchange.fetch_position(symbol)
    print(f"{position['info']['unrealisedPnl']} {position['info']['curRealisedPnl']} {position['info']['size']}")
    
    print(f"Creating LIMIT BUY order for {symbol}")
    print(exchange.create_order(symbol, EOrderType.LIMIT.value, EOrderSide.BUY.value, AMOUNT, ticker['last'] * 0.5))
  
    print(f"Creating TAKE PROFIT MARKET SELL order for {symbol}")
    print(exchange.create_order(
        symbol,
        EOrderType.MARKET.value,
        EOrderSide.SELL.value,
        AMOUNT,
        ticker['last'] * 1.01,
        params={'takeProfitPrice': '250', 'reduceOnly': True}
    ))
    
    print(f"Creating STOP LOSS MARKET SELL order for {symbol}")
    print(exchange.create_order(
        symbol,
        EOrderType.MARKET.value,
        EOrderSide.SELL.value,
        AMOUNT,
        ticker['last'] * 1.01,
        params={'stopLossPrice': '100', 'reduceOnly': True}
    ))
```

# Restriction in Version 2.0.6.1
As of now (09.11.2025) the reya sdk version 2.0.6.1 trys to read the "pyproject.toml" which is not beeing exported and not
on the right location.
To make it work you need to import

```
import reya_ccxt_adapter.sdk_patch 
```

which patches the _version.py to set the version manually to 2.0.6.1