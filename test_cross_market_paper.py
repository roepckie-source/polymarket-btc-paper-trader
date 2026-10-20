"""Unit tests for cross-market paper signal logic; no network or orders."""
import pytest
from cross_market_paper import Config, infer_poly_signal, net_pnl_usd


def test_up_signal():
    assert infer_poly_signal({"UP": 0.72, "DOWN": 0.28}) == "UP"


def test_down_signal():
    assert infer_poly_signal({"UP": 0.31, "DOWN": 0.69}) == "DOWN"


def test_no_signal_when_prices_ambiguous():
    assert infer_poly_signal({"UP": 0.52, "DOWN": 0.48}) == "FLAT"
    assert infer_poly_signal({"UP": 0.8}) == "FLAT"


def test_configurable_threshold():
    assert infer_poly_signal({"UP": 0.65, "DOWN": 0.35}, Config(up_threshold=0.66)) == "FLAT"


def test_long_pnl_after_costs():
    pnl = net_pnl_usd(100, 101, "LONG", 100, fee_bps=10, slippage_bps=5)
    assert pnl == pytest.approx(0.85)


def test_short_pnl_after_costs():
    pnl = net_pnl_usd(100, 99, "SHORT", 100, fee_bps=10, slippage_bps=5)
    assert pnl == pytest.approx(0.85)


def test_flat_has_no_pnl():
    assert net_pnl_usd(100, 110, "FLAT", 100, 40, 10) == 0


def test_invalid_prices_rejected():
    with pytest.raises(ValueError):
        net_pnl_usd(0, 100, "LONG", 100, 10, 10)
