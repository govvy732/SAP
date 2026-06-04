---
name: spn-architect-pro
description: >
  Smart Portfolio Navigator & Architect Pro (SAP). Use this skill whenever the user wants a
  complete, professional-grade portfolio snapshot, NFT holdings audit, risk & diversification score,
  watchlist tracking, PnL baseline, or CSV/JSON export for a Pharos wallet. Primary network is
  Pharos mainnet (PROS, chain id 1672); Pharos Atlantic testnet (PHRS, chain id 688689) is
  supported as a secondary target. Goes beyond raw balance queries: combines native + ERC20 + ERC721
  holdings, computes concentration metrics, flags suspicious or non-standard tokens, and produces
  shareable reports. Invoke when the user mentions "portfolio", "wallet summary", "asset overview",
  "holdings report", "PnL", "watchlist", "diversification", "NFT audit", "risk score",
  "export wallet", or asks for a holistic view of a Pharos address. Do NOT use for single-token
  balance queries, transaction sending, contract deployment, or contract verification — those
  belong to pharos-skill-engine.
version: 0.1.0
license: MIT-0
requires:
  anyBins:
    - cast
    - python3
---
# SPN Architect Pro (SAP) — Smart Portfolio Navigator for Pharos

Build, score, and export a complete portfolio snapshot for any Pharos wallet. SAP layers on top of
`pharos-skill-engine`: it consumes the network config and token list that engine exposes, then adds
NFT holdings, concentration risk metrics, watchlist tracking, baseline PnL (cost basis optional),
suspicious-token detection, and clean CSV / JSON / Markdown export.

## Prerequisites

1. **Pharos Skill Engine installed and read first.** This skill **depends on** `pharos-skill-engine`
   for network config (`assets/networks.json`) and the known token list (`assets/tokens.json`). If
   the user has not loaded `pharos-skill-engine`, load it before doing anything else. SAP also
   depends on `cast` and `python3` being installed.

2. **Foundry installed** (the engine skill handles installation). Verify:
   ```bash
   cast --version
   python3 --version
   ```

3. **No private key required for read-only operations.** SAP is read-only by default — it never
   needs a private key. If the user later wants to add an "import cost basis from a signed message"
   flow, that will be a future extension.

## What SAP Produces

When invoked, SAP generates a single Markdown report containing:

| Section | Source | Notes |
|---------|--------|-------|
| Header & target network | `assets/networks.json` | Network name, RPC, explorer |
| Native balance | `cast balance` | PHRS / PROS depending on network |
| ERC20 holdings (known) | `cast call balanceOf` per token in `assets/tokens.json` | Skips zero balances |
| ERC20 holdings (user-supplied) | `cast call balanceOf` per address | Optional, de-duped |
| ERC721 holdings (optional) | `cast call balanceOf` against a user-provided NFT contract list | Optional |
| Total estimated value | Computed in-script | Sum of native (in PHRS units); ERC20 USD valuation is out of scope by default |
| Concentration risk (HHI) | Computed in-script | Herfindahl-Hirschman Index on known ERC20 weights |
| Top holdings concentration | Computed in-script | Top-1 and Top-3 cumulative share |
| Watchlist diff | `assets/watchlist.json` (user-editable) | Mark IN / OUT / MOVED |
| Suspicious-token flags | Heuristics on contract | Non-standard decimals, empty symbol, no code |
| Export artifacts | `reports/<address>_<timestamp>.{csv,json,md}` | Written to current working directory |

## Capability Index

| User Need | Capability | Detailed Instructions |
|-----------|------------|----------------------|
| Generate a full portfolio report (Markdown + CSV + JSON) | `portfolio` | → `references/portfolio.md` |
| Add custom ERC20 / ERC721 contracts to the scan | `custom-contracts` | → `references/portfolio.md#custom-contracts` |
| Maintain a watchlist and diff it against current holdings | `watchlist` | → `references/watchlist.md` |
| Compute concentration risk and diversification score | `risk` | → `references/risk.md` |
| Detect suspicious / non-standard tokens | `security` | → `references/security.md` |
| Estimate gas for a "rebalance" or batch action preview | `gas-preview` | → `references/portfolio.md#gas-preview` |

## Quick Start (Agent Flow)

1. **Load `pharos-skill-engine` first.** Read `assets/networks.json` and `assets/tokens.json` from
   that skill.
2. **Resolve target network.** Default = `mainnet` (Pharos mainnet, native `PROS`). If user says
   "testnet" or "PHRS", switch to `atlantic-testnet`.
3. **Ask the user for the wallet address** if not provided. Validate `0x` + 40 hex.
4. **Ask whether to scan only known tokens, or also user-supplied contracts.** If user-supplied,
   collect the comma-separated addresses; for each, also ask `erc20` or `erc721`.
5. **Ask about a watchlist.** If the user has one (`assets/watchlist.json`), run the diff. If not,
   skip.
6. **Run the portfolio script** (`scripts/portfolio.py`) which orchestrates all `cast` calls and
   produces a Markdown report. See `references/portfolio.md` for details and CLI flags.
7. **Display the report inline** in chat and offer to write the CSV / JSON / MD artifacts to disk.
8. **Provide explorer links** for the wallet and each holding using `<explorerUrl>/address/...`.

## Outputs

- **Inline:** A formatted Markdown table in chat, no truncation.
- **On disk (optional):** Three files in the working directory:
  - `reports/<address>_<timestamp>.md` — full Markdown report
  - `reports/<address>_<timestamp>.csv` — flat tabular export, one row per holding
  - `reports/<address>_<timestamp>.json` — machine-readable report

## Security Reminders

- **Read-only by design.** SAP never asks for or uses a private key. If a user volunteers one,
  refuse for SAP purposes and direct them to `pharos-skill-engine` for write operations.
- **No external HTTP for token prices.** SAP intentionally does not call CoinGecko or any
  third-party API. USD valuation is opt-in and disabled by default. This keeps the skill
  deterministic and safe to run offline.
- **No web scraping of the block explorer.** If a token is not in `assets/tokens.json` AND the
  user has not provided a contract address, direct them to `<explorerUrl>/tokens` to look it up
  themselves — the explorer has bot checks that block automated access.

## Network Confirmation (Read-Only Operations)

Even though SAP is read-only, the Agent must clearly state the target network before running.
**Default network is Pharos mainnet** (`mainnet`, native `PROS`, chain id `1672`). The Atlantic
testnet (`atlantic-testnet`, native `PHRS`, chain id `688689`) is supported as a secondary target.

Format:

```
Target network: Pharos Mainnet (mainnet)
Wallet: 0x1234...abcd
Scan scope: known tokens + 3 user-supplied ERC20s
Proceed?
```

If the user replies "testnet" or "PHRS" at any point, switch the network and re-state it.

## Error Handling (SAP-Specific)

| Error Scenario | CLI Error Signature | Handling |
|----------------|---------------------|----------|
| `pharos-skill-engine` not loaded | Network/token config files missing | Prompt user to load the engine skill first, then re-run |
| User address fails regex | `invalid address` | Prompt for `0x` + 40 hex format |
| Custom contract has no code | empty `cast call` result | Mark contract as "no code" in report, skip its balance |
| Custom contract reverts on `decimals()` | `execution reverted` | Flag as non-standard ERC20, include in suspicious list |
| `python3` not found | `command not found: python3` | Prompt to install Python 3.10+; offer a pure-cast fallback for native + known tokens only |
| `cast` call times out | connection timeout | Retry once; on second failure, mark that token as "unreachable" and continue |
| Same address scanned twice in one run | duplicate in user input | De-duplicate silently, log a note in the report footer |

## When NOT to Use SAP

- The user wants to **send** a transaction, **deploy** a contract, **verify** source, or **run an
  airdrop**. Use `pharos-skill-engine` instead.
- The user wants a **single balance query** for one specific token. Use `pharos-skill-engine`
  directly — it's faster and cheaper.
- The user is on a **non-Pharos chain** (Ethereum mainnet, Base, Arbitrum, etc.). SAP is
  Pharos-specific.

## Reference Files

- `references/portfolio.md` — full portfolio flow, CLI flags, output schema
- `references/watchlist.md` — watchlist format, diff semantics
- `references/risk.md` — HHI formula, diversification score thresholds
- `references/security.md` — suspicious-token heuristics

## Asset Files

- `assets/watchlist.example.json` — example watchlist (copy to `assets/watchlist.json` to use)
- `assets/risk-bands.json` — HHI bands and recommended actions
- `assets/symbol-overrides.json` — manual symbol/decimals overrides for non-standard tokens
- `scripts/portfolio.py` — the orchestrator script
- `assets/templates/portfolio.md.tpl` — Markdown report template
