# Risk & Diversification Metrics

SAP computes concentration risk on the ERC20 portion of a wallet (native is excluded by default;
see "Including Native" below).

## HHI (Herfindahl-Hirschman Index)

For a set of ERC20 holdings with weights `w_i` (in percent, summing to 100), HHI is:

```
HHI = Σ w_i²
```

Where each `w_i` is the share of the **ERC20-only** total. Examples:

| Portfolio | HHI | Interpretation |
|-----------|-----|----------------|
| 100% in one token | 10000 | Maximum concentration |
| 50/50 in two tokens | 5000 | High concentration |
| 10 equal tokens | 1000 | Moderate |
| 25 equal tokens | 400 | Well diversified |
| 100 equal tokens | 100 | Theoretically perfect |

## Diversification Score

```
diversification_score = clamp(100 - (HHI / 100), 0, 100)
```

A score of `0` means everything is in one token. A score of `100` would require HHI ≤ 0, which is
not realistic for a finite set of holdings.

## Bands

Bands are stored in `assets/risk-bands.json` and ship with conservative defaults:

| HHI Range | Band | Score Range | Recommended Action |
|-----------|------|-------------|-------------------|
| 0 – 1500 | `diversified` | 85 – 100 | Hold; consider rebalancing only for thesis changes |
| 1500 – 2500 | `balanced` | 75 – 85 | Monitor; small rebalances OK |
| 2500 – 4999 | `concentrated` | 50 – 75 | Consider trimming top holding |
| 5000 – 7500 | `highly_concentrated` | 25 – 50 | Strong rebalance recommended |
| 7500 – 10000 | `single_asset` | 0 – 25 | Critical; immediate rebalance recommended |

The Agent should not push the user to act. It presents the band and the recommended action
verbally and lets the user decide.

## Top-1 / Top-3 Cumulative Share

The report also surfaces the cumulative share of the largest and the top-three ERC20 holdings
(expressed as a percentage of the ERC20 total). These are easier to read at a glance than HHI.

Example:

```
Top-1 share: 62.5%   (USDC)
Top-3 share: 91.0%   (USDC, WETH, WBTC)
```

## Including Native

By default, native is excluded so that low-value wallets in early testnet phases don't dominate
the HHI. To include native, pass `--include-native` to `scripts/portfolio.py`. The script will
treat 1 native unit = 1 weight unit and recompute HHI over (native + ERC20).

This is rarely useful on testnet (where faucet balances dwarf ERC20 holdings) and is mainly a
mainnet tool. The Agent should only enable it if the user asks.

## Stablecoin Adjustment

If the user wants to treat stables as a single "stable bucket" for HHI purposes, the Agent can
collapse all entries whose symbol matches `/USDC|USDT|DAI|FRAX|USD[CT]/` into a single bucket
before computing HHI. This is opt-in via `--collapse-stables` and the report explicitly states
the collapse so the user can audit it.

## Limitations

- HHI is concentration, not volatility. Two perfectly uncorrelated assets at 50/50 still get
  HHI = 5000. The score is a starting point, not a complete risk model.
- SAP does not pull token prices. If a stablecoin is depegged, the score will not flag it.
- The score reflects a single moment in time. It does not track drift; for that, schedule
  repeated scans.
