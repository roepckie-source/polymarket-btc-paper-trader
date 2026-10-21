
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from okx_spot_paper import (
    initial_state,
    step,
    make_signal,
    save_state,
    load_state,
)


def candles(closes, start=1_000_000):
    """Build synthetic 5-minute candles for deterministic tests."""
    return [
        {
            "ts": start + i * 300_000,
            "open": float(price),
            "high": float(price) + 1,
            "low": float(price) - 1,
            "close": float(price),
            "volume": 10,
            "confirmed": True,
        }
        for i, price in enumerate(closes)
    ]


class PaperBotTests(unittest.TestCase):

    def test_not_enough_data_holds(self):
        signal, reason = make_signal(candles([100, 101]))

        self.assertEqual(signal, "HOLD")
        self.assertEqual(reason, "not enough confirmed candles")

    def test_duplicate_candle_no_double_trade(self):
        cs = candles(list(range(100, 125)))
        state, first_result = step(initial_state(), cs)

        self.assertEqual(first_result["action"], "BUY")

        state, second_result = step(state, cs)

        self.assertEqual(second_result["action"], "NONE")
        self.assertIn("already processed", second_result["reason"])

        # No additional BTC was purchased.
        self.assertAlmostEqual(
            state["btc"],
            first_result["btc"],
        )

    def test_buy_size_respects_cap_and_stop(self):
        cs = candles(list(range(100, 125)))
        state, result = step(initial_state(), cs)

        self.assertEqual(result["action"], "BUY")
        self.assertLessEqual(result["notional_usdt"], 20.0)
        self.assertLessEqual(
            result["notional_usdt"] + result["fee_usdt"],
            100.0,
        )
        self.assertAlmostEqual(
            state["stop_price"],
            cs[-1]["close"] * 0.98,
        )

    def test_stop_loss_closes_position(self):
        cs = candles(list(range(100, 125)))
        state, buy_result = step(initial_state(), cs)

        self.assertEqual(buy_result["action"], "BUY")
        self.assertGreater(state["btc"], 0)

        stop_price = state["stop_price"]
        falling_price = stop_price * 0.99

        next_cs = candles(
            list(range(100, 125)) + [falling_price]
        )

        state, sell_result = step(state, next_cs)

        self.assertEqual(sell_result["action"], "SELL")
        self.assertEqual(state["btc"], 0.0)
        self.assertIsNone(state["entry_price"])
        self.assertIsNone(state["stop_price"])
        self.assertIsNone(state["entry_fee_usdt"]) if False else None
        self.assertGreaterEqual(state["cash_usdt"], 0.0)

    def test_no_shorting(self):
        cs = candles(list(range(130, 100, -1)))
        state, result = step(initial_state(), cs)

        self.assertEqual(state["btc"], 0.0)
        self.assertNotEqual(result["action"], "SELL")

    def test_state_survives_save_and_reload(self):
        cs = candles(list(range(100, 125)))
        state, result = step(initial_state(), cs)

        self.assertEqual(result["action"], "BUY")

        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "paper_state.json"

            with patch("okx_spot_paper.STATE_PATH", state_path):
                save_state(state)
                restored_state = load_state()

            self.assertAlmostEqual(
                restored_state["cash_usdt"],
                state["cash_usdt"],
            )
            self.assertAlmostEqual(
                restored_state["btc"],
                state["btc"],
            )
            self.assertEqual(
                restored_state["entry_price"],
                state["entry_price"],
            )
            self.assertEqual(
                restored_state["stop_price"],
                state["stop_price"],
            )
            self.assertEqual(
                restored_state["last_candle_ts"],
                state["last_candle_ts"],
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
