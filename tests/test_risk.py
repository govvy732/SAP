"""
Lightweight offline tests for the SAP risk math.

Run from the repo root:

    python3 -m pytest tests/test_risk.py
    # or, without pytest:
    python3 tests/test_risk.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the script importable as a module
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from portfolio import compute_risk, load_risk_bands, TokenHolding  # noqa: E402

BANDS = load_risk_bands(ROOT)


def _tok(symbol: str, value: float, decimals: int = 18) -> TokenHolding:
    raw = str(int(value * (10 ** decimals)))
    return TokenHolding(
        address="0x" + symbol.lower().encode().hex().ljust(40, "0")[:40],
        symbol=symbol,
        decimals=decimals,
        raw_balance=raw,
        balance=str(value),
        source="known",
    )


def test_single_asset():
    r = compute_risk([_tok("USDC", 1000, 6)], 0.0, False, False, BANDS)
    assert r.hhi == 10000
    assert r.band == "single_asset"
    assert r.diversification_score == 0


def test_fifty_fifty():
    h = [_tok("USDC", 500, 6), _tok("WETH", 500, 18)]
    r = compute_risk(h, 0.0, False, False, BANDS)
    assert r.hhi == 5000
    assert r.band == "highly_concentrated"
    assert r.diversification_score == 50


def test_ten_equal():
    h = [_tok(f"T{i}", 100) for i in range(10)]
    r = compute_risk(h, 0.0, False, False, BANDS)
    assert r.hhi == 1000
    assert r.band == "diversified"


def test_stable_collapse():
    h = [
        _tok("USDC", 250, 6),
        _tok("USDT", 250, 6),
        _tok("DAI", 250, 18),
        _tok("WETH", 250, 18),
    ]
    r = compute_risk(h, 0.0, False, True, BANDS)
    # 3 stables collapse to one bucket at 75%, WETH at 25% -> 75^2 + 25^2 = 6250
    assert r.hhi == 6250
    assert r.band == "highly_concentrated"


def test_empty_portfolio():
    r = compute_risk([], 0.0, False, False, BANDS)
    assert r.diversification_score == 100
    assert r.band == "empty"


def test_include_native():
    r = compute_risk([], 100.0, True, False, BANDS)
    assert r.hhi == 10000
    assert r.band == "single_asset"


def test_top_shares():
    h = [_tok("USDC", 70, 6), _tok("WETH", 20, 18), _tok("WBTC", 10, 18)]
    r = compute_risk(h, 0.0, False, False, BANDS)
    assert r.top1_share_pct == 70.0
    assert r.top3_share_pct == 100.0


if __name__ == "__main__":
    # Minimal harness so this can be run without pytest
    failures = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS  {name}")
            except AssertionError as exc:
                print(f"FAIL  {name}: {exc}")
                failures += 1
            except Exception as exc:  # noqa: BLE001
                print(f"ERROR {name}: {exc}")
                failures += 1
    if failures:
        sys.exit(1)
    print(f"\nAll {sum(1 for n in globals() if n.startswith('test_'))} tests passed.")
