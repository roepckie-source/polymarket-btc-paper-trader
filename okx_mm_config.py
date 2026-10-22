"""Settings for the public-data-only OKX spot market-making paper simulator."""
import os
INSTRUMENT = "BTC-USDT"
STARTING_EQUITY_USDT = 100.0
INITIAL_CASH_FRACTION = 0.50  # remaining 50% is virtual BTC inventory
TARGET_SPREAD_PCT = 0.0040   # 0.40% target spread, before fees/adverse selection
REPRICE_THRESHOLD_PCT = 0.0010
ORDER_NOTIONAL_USDT = 10.0
MAX_INVENTORY_VALUE_USDT = 65.0
MIN_ORDER_NOTIONAL_USDT = 5.0
MAKER_FEE_RATE = 0.0010      # placeholder 0.10% per fill; verify actual OKX fee tier
PRICE_TICK = 0.1
QTY_DECIMALS = 6
ORDERBOOK_DEPTH = 5
POLL_SECONDS = 10
MAX_DRAWDOWN_PCT = 0.05
STATE_PATH = os.getenv("PAPER_STATE_PATH", "okx_mm_paper_state.json")
TRADES_PATH = os.getenv("PAPER_TRADES_PATH", "okx_mm_paper_trades.csv")
EVENTS_PATH = os.getenv("EVENTS_PATH", "okx_mm_paper_events.csv")
