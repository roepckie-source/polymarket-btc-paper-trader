import unittest
from okx_paper_config import MAX_RISK_QUOTE, MAX_POSITION_QUOTE
from okx_spot_paper import initial_state

class CrossMarketPaperTests(unittest.TestCase):
    def test_paper_defaults_are_conservative(self):
        self.assertEqual(MAX_RISK_QUOTE,2.0)
        self.assertLessEqual(MAX_POSITION_QUOTE,20.0)
    def test_spot_is_long_only(self):
        self.assertEqual(initial_state()["btc"],0.0)

if __name__ == "__main__": unittest.main()
