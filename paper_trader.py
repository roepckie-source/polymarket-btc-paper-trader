"""
Polymarket BTC Paper Trader
===========================

PAPER TRADING ENGINE

IMPORTANT:
- PAPER ONLY
- NO POLYMARKET API
- NO BINANCE API
- NO REAL ORDERS
- NO PRIVATE KEYS
- NO WALLET

This module receives market observations and simulates trades
using the strategy defined in strategy.py.
"""

import csv
import os
from dataclasses import dataclass
from datetime import datetime, UTC

from strategy import evaluate


# ============================================================
# CONFIGURATION
# ============================================================

STARTING_BANKROLL = 100.00

RESULTS_FILE = "paper_trades.csv"

# Maximum amount of bankroll that may be exposed
# in one paper position.
MAX_TOTAL_EXPOSURE_PCT = 0.25

# Safety: only one position at a time.
ONE_POSITION_AT_A_TIME = True

# Minimum Kelly fraction required before a trade can open.
MIN_KELLY_FRACTION = 0.0001


# ============================================================
# PAPER POSITION
# ============================================================

@dataclass
class PaperPosition:
    side: str
    entry_price: float
    amount_usd: float
    contracts: float

    btc_open: float
    btc_entry: float

    probability: float
    edge: float
    kelly_fraction: float

    entry_time: str


# ============================================================
# PAPER TRADER
# ============================================================

class PaperTrader:

    def __init__(
        self,
        starting_bankroll: float = STARTING_BANKROLL,
        results_file: str = RESULTS_FILE,
    ):
        self.starting_bankroll = starting_bankroll
        self.bankroll = starting_bankroll

        self.results_file = results_file

        self.position = None

        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0

        self.total_profit = 0.0
        self.total_loss = 0.0

        self.max_bankroll = starting_bankroll
        self.max_drawdown = 0.0

        self._create_results_file()

    # --------------------------------------------------------
    # CSV
    # --------------------------------------------------------

    def _create_results_file(self):

        if os.path.exists(self.results_file):
            return

        with open(
            self.results_file,
            "w",
            newline="",
            encoding="utf-8",
        ) as file:

            writer = csv.writer(file)

            writer.writerow([
                "timestamp",
                "event",
                "side",
                "btc_open",
                "btc_current",
                "seconds_remaining",
                "market_price",
                "probability",
                "edge",
                "kelly_fraction",
                "position_size",
                "contracts",
                "result",
                "pnl",
                "bankroll",
                "reason",
            ])

    def _write_result(self, row):

        with open(
            self.results_file,
            "a",
            newline="",
            encoding="utf-8",
        ) as file:

            writer = csv.writer(file)
            writer.writerow(row)

    # --------------------------------------------------------
    # STATISTICS
    # --------------------------------------------------------

    def _update_drawdown(self):

        if self.bankroll > self.max_bankroll:
            self.max_bankroll = self.bankroll

        if self.max_bankroll <= 0:
            return

        drawdown = (
            (self.max_bankroll - self.bankroll)
            / self.max_bankroll
        )

        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown

    # --------------------------------------------------------
    # EXPOSURE
    # --------------------------------------------------------

    def _maximum_position_allowed(self):

        return self.bankroll * MAX_TOTAL_EXPOSURE_PCT

    # --------------------------------------------------------
    # OPEN PAPER TRADE
    # --------------------------------------------------------

    def open_trade(
        self,
        btc_open: float,
        btc_current: float,
        seconds_remaining: float,
        market_price: float,
        volatility: float = 0.12,
    ):

        # ----------------------------------------------------
        # SAFETY: ONLY ONE POSITION
        # ----------------------------------------------------

        if ONE_POSITION_AT_A_TIME and self.position is not None:

            print(
                "PAPER: trade rejected - "
                "position already open"
            )

            return False

        # ----------------------------------------------------
        # SAFETY: BANKROLL
        # ----------------------------------------------------

        if self.bankroll <= 0:

            print("PAPER: bankroll exhausted")

            return False

        # ----------------------------------------------------
        # STRATEGY EVALUATION
        # ----------------------------------------------------

        result = evaluate(
            btc_open=btc_open,
            btc_current=btc_current,
            seconds_remaining=seconds_remaining,
            market_price=market_price,
            bankroll=self.bankroll,
            volatility=volatility,
        )

        timestamp = datetime.now(UTC).isoformat()

        # ----------------------------------------------------
        # NO SIGNAL
        # ----------------------------------------------------

        if not result.signal:

            print(
                f"PAPER: NO TRADE | "
                f"reason={result.reason}"
            )

            return False

        # ----------------------------------------------------
        # CRITICAL KELLY SAFETY
        #
        # Never force a minimum position if Kelly says
        # that the mathematically appropriate position is zero.
        # ----------------------------------------------------

        if result.kelly_fraction <= MIN_KELLY_FRACTION:

            print(
                "PAPER: NO TRADE | "
                f"Kelly too small: "
                f"{result.kelly_fraction:.6%}"
            )

            self._write_result([
                timestamp,
                "REJECT",
                result.side,
                btc_open,
                btc_current,
                seconds_remaining,
                market_price,
                result.probability,
                result.edge,
                result.kelly_fraction,
                0.0,
                0.0,
                "",
                "",
                self.bankroll,
                "Kelly too small",
            ])

            return False

        # ----------------------------------------------------
        # KELLY POSITION
        # ----------------------------------------------------

        position_size = result.position_size

        # ----------------------------------------------------
        # EXPOSURE PROTECTION
        # ----------------------------------------------------

        maximum_allowed = self._maximum_position_allowed()

        position_size = min(
            position_size,
            maximum_allowed,
        )

        # ----------------------------------------------------
        # FINAL SAFETY
        # ----------------------------------------------------

        if position_size <= 0:

            print(
                "PAPER: NO TRADE | "
                "position size <= 0"
            )

            return False

        if position_size > self.bankroll:

            position_size = self.bankroll

        # ----------------------------------------------------
        # CONTRACT CALCULATION
        # ----------------------------------------------------

        contracts = position_size / market_price

        # ----------------------------------------------------
        # OPEN POSITION
        # ----------------------------------------------------

        self.position = PaperPosition(
            side=result.side,
            entry_price=market_price,
            amount_usd=position_size,
            contracts=contracts,
            btc_open=btc_open,
            btc_entry=btc_current,
            probability=result.probability,
            edge=result.edge,
            kelly_fraction=result.kelly_fraction,
            entry_time=timestamp,
        )

        # ----------------------------------------------------
        # LOG
        # ----------------------------------------------------

        self._write_result([
            timestamp,
            "OPEN",
            result.side,
            btc_open,
            btc_current,
            seconds_remaining,
            market_price,
            result.probability,
            result.edge,
            result.kelly_fraction,
            position_size,
            contracts,
            "",
            "",
            self.bankroll,
            result.reason,
        ])

        # ----------------------------------------------------
        # CONSOLE
        # ----------------------------------------------------

        print()
        print("=" * 60)
        print("PAPER TRADE OPENED")
        print("=" * 60)

        print(f"Side:          {result.side}")
        print(f"BTC Open:      ${btc_open:,.2f}")
        print(f"BTC Current:   ${btc_current:,.2f}")
        print(f"Market Price:  ${market_price:.4f}")
        print(f"Probability:   {result.probability:.2%}")
        print(f"Edge:          {result.edge:.2%}")
        print(f"Kelly:         {result.kelly_fraction:.4%}")
        print(f"Position:      ${position_size:.2f}")
        print(f"Contracts:     {contracts:.4f}")

        print("=" * 60)
        print()

        return True

    # --------------------------------------------------------
    # RESOLVE PAPER TRADE
    # --------------------------------------------------------

    def resolve_trade(
        self,
        winning_side: str,
    ):

        # ----------------------------------------------------
        # SAFETY
        # ----------------------------------------------------

        if self.position is None:

            print(
                "PAPER: no open position"
            )

            return False

        winning_side = winning_side.upper()

        if winning_side not in ("UP", "DOWN"):

            print(
                "PAPER: invalid winning side"
            )

            return False

        position = self.position

        timestamp = datetime.now(UTC).isoformat()

        # ----------------------------------------------------
        # WIN
        # ----------------------------------------------------

        if position.side == winning_side:

            payout = position.contracts

            pnl = payout - position.amount_usd

            result_text = "WIN"

            self.winning_trades += 1

            self.total_profit += pnl

        # ----------------------------------------------------
        # LOSS
        # ----------------------------------------------------

        else:

            pnl = -position.amount_usd

            result_text = "LOSS"

            self.losing_trades += 1

            self.total_loss += abs(pnl)

        # ----------------------------------------------------
        # UPDATE BANKROLL
        # ----------------------------------------------------

        self.bankroll += pnl

        self.total_trades += 1

        self._update_drawdown()

        # ----------------------------------------------------
        # SAVE RESULT
        # ----------------------------------------------------

        self._write_result([
            timestamp,
            "CLOSE",
            position.side,
            position.btc_open,
            position.btc_entry,
            0,
            position.entry_price,
            position.probability,
            position.edge,
            position.kelly_fraction,
            position.amount_usd,
            position.contracts,
            result_text,
            pnl,
            self.bankroll,
            "MARKET RESOLVED",
        ])

        # ----------------------------------------------------
        # CONSOLE
        # ----------------------------------------------------

        print()
        print("=" * 60)
        print("PAPER TRADE RESOLVED")
        print("=" * 60)

        print(f"Side:          {position.side}")
        print(f"Result:        {result_text}")
        print(f"P&L:           ${pnl:+.2f}")
        print(f"Bankroll:      ${self.bankroll:.2f}")

        print("=" * 60)
        print()

        # ----------------------------------------------------
        # CLEAR POSITION
        # ----------------------------------------------------

        self.position = None

        return True

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    def summary(self):

        winrate = 0.0

        if self.total_trades > 0:

            winrate = (
                self.winning_trades
                / self.total_trades
            )

        return {
            "starting_bankroll":
                self.starting_bankroll,

            "current_bankroll":
                self.bankroll,

            "total_pnl":
                self.bankroll
                - self.starting_bankroll,

            "total_trades":
                self.total_trades,

            "wins":
                self.winning_trades,

            "losses":
                self.losing_trades,

            "winrate":
                winrate,

            "gross_profit":
                self.total_profit,

            "gross_loss":
                self.total_loss,

            "max_drawdown":
                self.max_drawdown,
        }

    # --------------------------------------------------------
    # PRINT SUMMARY
    # --------------------------------------------------------

    def print_summary(self):

        stats = self.summary()

        print()
        print("=" * 60)
        print("PAPER TRADING SUMMARY")
        print("=" * 60)

        print(
            f"Starting bankroll: "
            f"${stats['starting_bankroll']:.2f}"
        )

        print(
            f"Current bankroll:  "
            f"${stats['current_bankroll']:.2f}"
        )

        print(
            f"Total P&L:         "
            f"${stats['total_pnl']:+.2f}"
        )

        print(
            f"Trades:            "
            f"{stats['total_trades']}"
        )

        print(
            f"Wins:              "
            f"{stats['wins']}"
        )

        print(
            f"Losses:            "
            f"{stats['losses']}"
        )

        print(
            f"Winrate:           "
            f"{stats['winrate']:.2%}"
        )

        print(
            f"Gross profit:      "
            f"${stats['gross_profit']:.2f}"
        )

        print(
            f"Gross loss:        "
            f"${stats['gross_loss']:.2f}"
        )

        print(
            f"Max drawdown:      "
            f"{stats['max_drawdown']:.2%}"
        )

        print("=" * 60)
        print()


# ============================================================
# DEMO
# ============================================================

def demo():

    print()
    print("=" * 60)
    print("POLYMARKET BTC PAPER TRADER")
    print("=" * 60)
    print("PAPER ONLY")
    print("NO REAL ORDERS")
    print("NO API")
    print("NO WALLET")
    print("=" * 60)
    print()

    trader = PaperTrader(
        starting_bankroll=100.00,
        results_file="paper_demo.csv",
    )

    # --------------------------------------------------------
    # SOFTWARE TEST DATA ONLY
    #
    # This is NOT real market data.
    # --------------------------------------------------------

    trader.open_trade(
        btc_open=100000.0,
        btc_current=100300.0,
        seconds_remaining=120,
        market_price=0.68,
        volatility=0.12,
    )

    # --------------------------------------------------------
    # Simulate resolution.
    #
    # This is ONLY a software test.
    # --------------------------------------------------------

    if trader.position is not None:

        trader.resolve_trade("UP")

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    trader.print_summary()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    demo()
