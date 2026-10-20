# Paper settlement fix

This update keeps the existing project paper-only. It adds unit tests for win/loss settlement arithmetic, fixes the diagnostic BTC close value to use `btc_current`, and uploads `paper_trades.csv` / `paper_state.csv` as a GitHub Actions artifact for audit and recovery.

## Install
Replace `paper_live.py`, `.github/workflows/paper-test.yml`, and add `test_paper_live_settlement.py` from this package. The workflow runs the new settlement tests and uploads any generated state CSVs.

## Important persistence limitation
GitHub Actions artifacts are not automatically restored into a later workflow run by this change. Downloading the artifact is a backup/recovery step, not automatic persistent storage. Until automated restore is configured, separate workflow runs may start with a fresh filesystem and the $100 default bankroll.

## Test
Run `python -m unittest -v test_paper_live_settlement.py`. The tests cover winning and losing settlement, fee deduction, and invalid outcomes.

No live orders, wallet, private keys, or real-money trading are enabled.
