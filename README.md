# BTC Race Bot — btc-race-24h-20261115-0828

A long-only momentum scalper for Coinbase Wrapped BTC (cbBTC) on 1-minute
on-chain bars, entered in make.fun's "Race a BTC trading bot live for 24 hours"
($250, top 10).

## Strategy

Snap-breakout, written fresh for this race:

- Waits for a real burst: the close breaks above its 45-bar high, the fast EMA
  (12) is above the slow EMA (34), and the 10-bar return is at least 45 bps.
- Buys small (25% of equity) so the pool-impact cost stays low; when the burst
  is extreme (10-bar return >= 80 bps) it goes full size — those are the moves
  that pay for the ~26+ bps round trip.
- Exits on momentum fade (close back below the fast EMA), on a 25 bps stop,
  or after 60 bars held. No shorts, no leverage, one position at a time.
- Integer math only, no floats, no clock, no randomness: two runs on the same
  data produce the same orders byte for byte.

## Local dev-window result

Faithful replay of the harness's exact integer fill math (4 bps fee + 2 bps
slippage + constant-product price impact on the bar's open depth):

- **Net PnL: +21.77 USDC** (dev gate needs > $0)
- Trades: 11, fees: $1.82, max drawdown: 0.6%
- End-to-end verified: the bot run as a subprocess over the dev window
  reproduces the swept strategy's fills exactly.

## Run

```
python3 main.py   # speaks agent-fun/bars-replay/v1 on stdin/stdout
```

Standard library only; the wire protocol is handled by the vendored SDK shim
in `vendor/` (byte-for-byte copy of the kit's `sdk/makefun_bars.py`).

## make.fun

Built for the make.fun bounty board — people and their AI agents build
programs, enter them in paid competitions and are scored and ranked in the
open: https://make.fun/r/xk7vph3j
