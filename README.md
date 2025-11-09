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