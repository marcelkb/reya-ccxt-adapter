from ccxt.base.types import Entry


class ImplicitAPI:
    # Public GET endpoints
    public_get_api_markets = publicGetApiMarkets = Entry('v2/perpMarketDefinitions', 'public', 'GET', {'cost': 1})
    # v1 only: the v2 API removed /prices (use the summary's markPrice instead)
    public_get_api_trading_prices = publicGetApiTradingPrices = Entry('v2/prices/{symbol}', 'public', 'GET', {'cost': 1})
    public_get_api_market_summary = publicGetApiMarketSummary = Entry('v2/perpMarket/{symbol}/summary', 'public', 'GET', {'cost': 1})
    # v2 only: USD oracle price per collateral asset
    public_get_asset_oracle_prices = publicGetAssetOraclePrices = Entry('v2/assetOraclePrices', 'public', 'GET', {'cost': 1})
    public_get_historical_candles = publicGetHistoricalCandles = Entry('v2/candleHistory/{symbol}/{resolution}', 'public', 'GET', {'cost': 1})
    public_get_positions = publicGetPositions = Entry('v2/wallet/{wallet_address}/positions', 'public', 'GET', {'cost': 1})
    public_get_api_accounts_balance = publicGetApiAccountsBalance = Entry('v2/wallet/{wallet_address}/accountBalances', 'public',
                                                                                 'GET', {'cost': 1})

    public_get_wallet_accounts = publicGetApiWalletAccounts = Entry('v2/wallet/{wallet_address}/accounts', 'public',
                                                                    'GET', {'cost': 1})

    public_get_open_orders = publicGetApiOpenOrders = Entry('v2/wallet/{wallet_address}/openOrders', 'public',
                                                                    'GET', {'cost': 1})

    # v2 only: every order state change, newest first. openOrders drops an order
    # the moment it fills or cancels, so this is the only way to read one back.
    public_get_order_history = publicGetApiOrderHistory = Entry('v2/wallet/{wallet_address}/orderHistory', 'public',
                                                                    'GET', {'cost': 1})


    public_get_trades = publicGetApiTrades = Entry('v2/wallet/{wallet_address}/perpExecutions', 'public',
                                                                    'GET', {'cost': 1})

    # old api no new api yet
    public_get_leverages = publicGetLeverages = Entry('api/trading/wallet/{wallet_address}/leverages', 'public', 'GET', {'cost': 1})
    public_apy = publicGetAPY = Entry('api/trading/poolBalance/{pool_id}', 'public', 'GET',
                                                      {'cost': 1})
    public_get_market_data = publicGetMarketData = Entry('api/trading/market/{symbol}/data', 'public', 'GET', {'cost': 1})

    #old api
    public_get_api_accounts_balance_v1 = publicGetApiAccountsBalanceV1 = Entry('api/accounts/balance', 'public',
                                                                                 'GET', {'cost': 1})

    # Private GET endpoints




