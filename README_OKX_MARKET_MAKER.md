# OKX BTC-USDT Spot Market Maker — Paper Only

This is a new paper simulator alongside the existing `okx_spot_paper.py`. The existing file is an EMA-based long-only trend strategy, not a two-sided market maker; this new module does not silently overwrite it.

## Safety
- Reads only OKX's public `GET /api/v5/market/books` endpoint.
- No API keys, private account endpoints, wallet, leverage, or real order-placement code.
- All BUY/SELL orders are local simulated objects.
- The virtual portfolio starts at 100 USDT split between 50 USDT cash and 50 USDT of BTC at the first observed midpoint, so both sides can be quoted without borrowing.

## Behavior
- Quotes BUY below midpoint and SELL above midpoint, guarded to remain passive versus the observed best bid/ask.
- Reprices when midpoint moves by at least 0.10%, or after a simulated fill.
- A simulated fill requires a later public snapshot to cross the limit. This does not model queue position, partial fills, or latency, so paper results are approximate.
- Uses a 0.40% target spread and a placeholder 0.10% maker fee per fill. Verify the actual OKX fee tier before assessing profitability.
- Maximum simulated order notional: 10 USDT per side; inventory-value ceiling: 65 USDT; stop quoting at 5% marked-to-market drawdown.
- Writes state JSON, fill CSV and quote/event CSV. Keep runtime state separate from source commits.

## Install/test/run
```bash
python -m pip install requests
python -m unittest -v test_okx_market_maker_paper.py
python okx_market_maker_paper.py --once
python okx_market_maker_paper.py --minutes 30 --poll-seconds 10
```

Output files: `okx_mm_paper_state.json`, `okx_mm_paper_trades.csv`, `okx_mm_paper_events.csv`.
