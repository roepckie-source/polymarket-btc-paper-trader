# Historical BTC 5-minute backtest (paper-only)

This is an offline CSV backtest. It places no orders and does not connect to any exchange.
It applies the current `strategy.py` filters to each historical snapshot, then compares accepted signals with the **resolved** UP/DOWN outcome supplied in the CSV.

## Required input CSV columns

- `timestamp`: snapshot time in ISO format or another stable identifier
- `btc_open`: BTC price at the market window open
- `btc_current`: BTC price at the snapshot time
- `seconds_remaining`: seconds until the market resolves
- `up_price`: UP contract price from that same snapshot, between 0 and 1
- `outcome`: final resolved outcome, exactly `UP` or `DOWN`

Optional columns: `down_price`, `fee_rate`, `slippage_per_contract` (the command-line flags are used for costs; these optional row columns are not currently applied).

## Run

The GitHub Actions workflow now has a `historical-backtest` mode. It expects a real file named `historical_btc_5m.csv` in the repository and uploads `historical_backtest_results.csv` as an artifact. `historical_btc_5m_TEMPLATE.csv` only documents the header; it is not data and cannot produce performance results.

```bash
python historical_backtest.py historical_btc_5m.csv --output historical_backtest_results.csv --fee-rate 0.01 --slippage-per-contract 0.001
python -m unittest test_historical_backtest.py
```

Use fees and slippage matching the intended venue. Defaults are zero and therefore optimistic. Use only snapshots recorded before the resolution time to avoid look-ahead bias. Do not infer outcomes from the same snapshot price: `outcome` must come from the final market resolution.

## Important limitations

The repository upload did not include a genuine historical dataset with both pre-resolution snapshots and final outcomes. Existing `test_*.csv` files are small synthetic test fixtures, not evidence of strategy performance. The backtest therefore cannot honestly report profitability until a suitable dataset is supplied. This version evaluates the existing Polymarket strategy; it does not yet simulate Coinbase/KuCoin spot/futures order books or cross-market execution. The backtest now correctly supplies the UP or DOWN token price matching the direction selected by the strategy.
