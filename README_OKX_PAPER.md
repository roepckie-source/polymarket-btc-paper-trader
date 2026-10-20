# OKX BTC 5-minute Spot Paper Bot

## Safety
- Paper only: public candle API, local virtual portfolio, no authenticated endpoints, no order submission functions, no API keys.
- Spot only, no leverage, no short selling. A DOWN signal means exit a BTC holding or remain in cash.
- Starting paper equity is 100 quote units, intended as a €100-sized simulation. BTC-USDT is quoted in USDT; without an actual USDT/EUR conversion feed, results are not exact EUR accounting.
- Planned risk per trade: €2 equivalent; maximum notional: 20 quote units. A 2% stop is only a target. Gaps, slippage, conversion and fees can exceed the target loss.
- EMA21 plus three rising closes is a simple baseline for validating data flow, not a demonstrated profitable strategy.
- GitHub Actions scheduled runs are isolated workers; this workflow does not preserve portfolio state across runs unless a persistent store is added.

## Run locally
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m unittest -v
pytest -q
python okx_spot_paper.py
```
Stop with Ctrl+C. Files `okx_paper_state.json` and `okx_paper_trades.csv` are written in the current directory.

## GitHub Actions
Copy `.github/workflows/okx-paper.yml` into your repository. Run manually from Actions. This workflow runs unit tests and one paper evaluation. It does not place live orders.

## Next validation steps
Run for at least 7 days with persistent trade/state storage, realistic spread/fee assumptions, and exact USDT/EUR conversion. Review net P&L, drawdown, stop overruns and trade count. Do not enable live trading based on a few paper trades.
