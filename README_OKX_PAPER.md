# OKX BTC 5-minute Spot Paper Bot (safe first prototype)

## Safety
- **Paper mode only.** Uses public candle data and a local virtual portfolio.
- Contains no OKX order endpoint, no API authentication, no API keys, and no live-order code.
- Spot only; no leverage and no short selling. A DOWN signal means hold cash or exit a BTC holding.
- Starting paper equity: €100. Target risk per trade: €2. Maximum position: €20.
- Uses a provisional 2% stop distance to size the position. Gaps, fees, conversion rates and slippage mean the actual loss can exceed €2.
- BTC-USDT is treated as approximately EUR in the first prototype. That is only a rough placeholder; use an actual USDT/EUR conversion feed before evaluating EUR P&L.
- The EMA21/three-rising-closes signal is only a plumbing baseline, not a proven strategy.

## Run locally
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
python -m unittest -v
python okx_spot_paper.py
```
Stop with Ctrl+C. It stores `okx_paper_state.json` and `okx_paper_trades.csv` in the working directory.

## First test plan
1. Run at least 7 days paper-only with recorded closed candles, simulated fees and no parameter tuning.
2. Verify no duplicate entries on the same candle and confirm every trade is recorded.
3. Evaluate net P&L after fees, max drawdown, win/loss ratio, average win/loss and stop overruns.
4. Compare paper execution assumptions against OKX spread and actual EUR/USDT conversion.
5. Do not enable live trading as part of this package.

## Important limitation
This prototype buys BTC on an UP signal and sells/holds cash on a DOWN signal. Spot trading cannot profit from a falling price without borrowing/shorting, which this bot explicitly does not do.
