# Cross-market Polymarket signal paper test

This extension reads public Polymarket BTC 5-minute outcome prices and public BTC price data from the existing Coinbase/Kraken market-data module. It records a Polymarket-derived directional signal, a spot-long-only interpretation, and a BTC momentum baseline to CSV.

## Safety
- Paper/read-only only. No order endpoints, private keys, wallet, or authenticated trading clients.
- The current module records observations and signals. It does **not** claim profitability or pretend that Polymarket's binary payout can be replicated by spot BTC.
- The derivative-like long/short P&L helper is a simplified research model, not a broker/exchange execution model. Fee and slippage values are assumptions and must be calibrated before interpreting results.
- Coinbase and KuCoin are not yet connected as execution simulators; this version uses existing Coinbase ticker + Kraken candle observations and labels simulated sides only.

## Run
Install existing dependencies (`requests`) and run:

```bash
python cross_market_paper.py --once
python cross_market_paper.py --interval 10 --output cross_market_paper.csv
python -m pytest -q test_cross_market_paper.py
```

CSV observations are appended to `cross_market_paper.csv`. A long-running run can be stopped with Ctrl+C. Avoid committing generated CSVs if they contain data you do not want in the repository.

## Current signal logic
- UP when Polymarket UP price is at least 0.60 and exceeds DOWN.
- DOWN when Polymarket DOWN price is at least 0.60 and exceeds UP.
- Otherwise FLAT.
- A separate baseline labels the current BTC 5-minute move positive/negative/flat.

These thresholds are research defaults, not proven optimal parameters. Next stage: collect a sufficient sample, align entry/exit timestamps to complete windows, add venue-specific fee/slippage assumptions, and report net P&L, drawdown, trade count, and baseline comparison before considering any live execution.
