import unittest

from paper_live import calculate_fee, calculate_settlement


class SettlementTests(unittest.TestCase):
    def test_winning_trade_deducts_fee(self):
        result, payout, gross, net = calculate_settlement(
            side="DOWN", winning_side="DOWN", position=21.43,
            contracts=32.967, fee_usdc=0.525,
        )
        self.assertEqual(result, "WIN")
        self.assertAlmostEqual(payout, 32.967)
        self.assertAlmostEqual(gross, 11.537)
        self.assertAlmostEqual(net, 11.012)

    def test_losing_trade_loses_position_and_fee(self):
        result, payout, gross, net = calculate_settlement(
            side="DOWN", winning_side="UP", position=21.43,
            contracts=32.967, fee_usdc=0.525,
        )
        self.assertEqual(result, "LOSS")
        self.assertEqual(payout, 0.0)
        self.assertAlmostEqual(gross, -21.43)
        self.assertAlmostEqual(net, -21.955)

    def test_invalid_side_rejected(self):
        with self.assertRaises(ValueError):
            calculate_settlement("SIDEWAYS", "UP", 10, 10, 0.1)

    def test_fee_formula_for_sample_trade(self):
        self.assertAlmostEqual(calculate_fee(32.967, 0.65, 0.07), 0.525, places=3)


if __name__ == "__main__":
    unittest.main()
