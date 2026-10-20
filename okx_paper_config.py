"""Safe defaults for the OKX BTC spot paper trader. No order/API-key code exists here."""
STARTING_EQUITY_EUR = 100.0
MAX_RISK_EUR = 2.0
MAX_POSITION_EUR = 20.0
FEE_RATE = 0.001  # conservative placeholder: 0.10% per side; verify actual account fee tier
INSTRUMENT = "BTC-USDT"
BAR = "5m"
CANDLE_LIMIT = 100
POLL_SECONDS = 60
