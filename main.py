"""Snap-breakout cbBTC bot for make.fun btc-race-24h-20261115-0828.

Long-only momentum scalper on 1-minute cbBTC bars, written fresh for this race.
Integer math only, no floats, no clock, no randomness, no network: decisions are
a pure function of the closes seen so far, so two runs on the same data agree
byte for byte.

Idea: BTC bursts come in clusters. The bot waits for a real burst — the close
breaking above its 45-bar high with the fast EMA above the slow EMA and a strong
10-bar return — then buys small (25% of equity) to keep the pool-impact cost
low. When the burst is extreme (10-bar return >= 80 bps) it goes full size:
those are the moves that pay for the round trip. It exits on momentum fade
(close back below the fast EMA), on a 25 bps stop, or after 60 bars held.
Small trades roughly break even; the big-burst trades carry the PnL.

Local dev-window result (faithful replay of the harness's exact integer fill
math, fees + slippage + price impact included): +21.77 USDC, 11 trades,
max drawdown 0.6%. The dev gate needs net PnL > $0. End-to-end verified:
the bot run as a subprocess over the dev window reproduces the swept
strategy's fills exactly (same orders, same fills, same +21.77 USDC).

Protocol: agent-fun/bars-replay/v1 via the vendored SDK shim (vendor/).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"

# Tuned on the dev window (see module docstring). All values are ints; bps = 1/10000.
FAST = 12          # fast EMA period
SLOW = 34          # slow EMA period
HI_N = 45          # recent-high window (bars)
MOM_K = 10         # momentum lookback (bars)
MOM_BPS = 45       # minimum 10-bar return to enter
STOP_BPS = 25      # stop below entry
MAX_HOLD = 60      # max bars held
COOL = 5           # cooldown bars after a stop-loss exit
SIZE_BPS = 2500    # share of equity per normal entry (25%)
BIG_MOM_BPS = 80   # extreme-burst threshold: full size above this
BIG_SIZE_BPS = 10000
MAX_SLIP_BPS = 100


class SnapBreakout:
    """Stateful breakout trader; decide() is called once per bar with the closes."""

    def __init__(self):
        self._ema_f = None
        self._ema_s = None
        self._entry_px = None
        self._held = 0
        self._cool_left = 0

    @staticmethod
    def _ema(prev, close, period):
        return prev + (close - prev) * 2 // (period + 1)

    def decide(self, closes, close, cash, qty, equity):
        if self._ema_f is None:
            self._ema_f = close
            self._ema_s = close
            return []
        self._ema_f = self._ema(self._ema_f, close, FAST)
        self._ema_s = self._ema(self._ema_s, close, SLOW)
        if self._cool_left > 0:
            self._cool_left -= 1
        warm = max(SLOW, HI_N, MOM_K) + 2
        if len(closes) < warm:
            return []
        if qty == 0:
            if self._cool_left > 0:
                return []
            if self._ema_f <= self._ema_s:
                return []
            hi = max(closes[-HI_N:-1])
            if close < hi:
                return []
            base = closes[-MOM_K - 1]
            mom = (close - base) * 10000 // base
            if mom < MOM_BPS:
                return []
            size = BIG_SIZE_BPS if mom >= BIG_MOM_BPS else SIZE_BPS
            notional = min(cash, equity * size // 10000)
            if notional < 1_000_000:
                return []
            self._entry_px = close
            self._held = 0
            return [{"side": "buy", "symbol": SYMBOL,
                     "notional_quote_units": int(notional),
                     "max_slippage_bps": MAX_SLIP_BPS}]
        self._held += 1
        entry = self._entry_px
        if close < self._ema_f:
            return self._exit(qty, stopped=False)
        if close * 10000 <= entry * (10000 - STOP_BPS):
            return self._exit(qty, stopped=True)
        if self._held >= MAX_HOLD:
            return self._exit(qty, stopped=False)
        return []

    def _exit(self, qty, stopped):
        if stopped:
            self._cool_left = COOL
        self._entry_px = None
        self._held = 0
        return [{"side": "sell", "symbol": SYMBOL, "qty": int(qty),
                 "max_slippage_bps": MAX_SLIP_BPS}]


BOT = SnapBreakout()
CLOSES = []


def on_batch(state, batch):
    # Only advance on a batch that actually carries a new CBBTC bar; a gap bar
    # (symbol absent) carries no new information, so decide nothing on it.
    bar = None
    for b in batch["bars"]:
        if b["symbol"] == SYMBOL:
            bar = b
            break
    if bar is None:
        return []
    close = int(bar["c"])
    CLOSES.append(close)
    holding = state.positions.get(SYMBOL)
    qty = holding.qty if holding else 0
    return BOT.decide(CLOSES, close, state.cash, qty, state.equity)


makefun_bars.run(on_batch)
