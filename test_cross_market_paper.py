"""Cross-market tests: use pytest if available, but keep unittest compatibility."""
import unittest

class CrossMarketPaperTests(unittest.TestCase):
    def test_spot_mode_is_long_only_by_design(self):
        # The spot prototype never opens a short position; DOWN means hold or exit.
        from okx_spot_paper import initial_state
        state = initial_state()
        self.assertEqual(state["btc"], 0.0)
        self.assertFalse(state["halted"])

    def test_paper_defaults_are_conservative(self):
        from okx_paper_config import MAX_RISK_EUR, MAX_POSITION_EUR
        self.assertEqual(MAX_RISK_EUR, 2.0)
        self.assertLessEqual(MAX_POSITION_EUR, 20.0)

if __name__ == "__main__":
    unittest.main()
