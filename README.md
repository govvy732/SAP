# SPN Architect Pro (SAP)

A portfolio-analysis skill for AI agents. SAP takes a wallet address and
returns a single, professional report covering:

- native balance
- ERC20 holdings (known + user-supplied)
- ERC721 holdings (user-supplied)
- concentration risk (HHI, top-1 / top-3 share, 0–100 diversification score)
- watchlist diff (in / out / moved)
- suspicious-token flags (no-code, broken decimals, missing symbol, etc.)

Outputs are written to Markdown, CSV, and JSON. The skill is read-only end
to end and never requires a private key.

## How it works

SAP shells out to `cast` to read on-chain state, then assembles the
report from a small set of pure-Python helpers. There is one entry
point: `scripts/portfolio.py`. Everything else is reference
documentation that an agent reads to decide which CLI flags to use and
how to interpret the output.

## Information

| | |
|---|---|
| Skill name | SPN Architect Pro (SAP) |
| Version | 0.1.0 |
| License | MIT-0 |
| Primary network | Pharos mainnet |
| Other networks | Pharos Atlantic testnet |
| Native token | PROS (mainnet), PHRS (Atlantic testnet) |
| Primary chain id | 1672 (mainnet) |
| Other chain id | 688689 (Atlantic testnet) |
| Frameworks | OpenClaw, Claude Code, Codex |
| Entry point | `SKILL.md` |
| Orchestrator | `scripts/portfolio.py` |
| Language | Python 3.10+ |
| Required binaries | `cast` (Foundry) |
| Token list source | Pharos Agent Center (`pharos-skill-engine`) |
| Network config source | Pharos Agent Center (`pharos-skill-engine`) |
| Output formats | Markdown, CSV, JSON |
| Private key required | No |
| External HTTP calls | None |
| Web scraping | None |
| Third-party APIs | None |

## Installation

```bash
# 1. Install the Pharos Agent Center skill (provides networks.json and tokens.json)
#    See: https://github.com/PharosNetwork/pharos-skill-engine

# 2. Install Foundry (provides `cast`)
curl -L https://foundry.paradigm.xyz | bash
foundryup

# 3. Drop this skill into your framework's skills directory
#    OpenClaw:  ~/.openclaw/skills/spn-architect-pro/
#    Claude:    ~/.claude/skills/spn-architect-pro/
#    Codex:     ~/.codex/skills/spn-architect-pro/

# 4. Verify
python3 scripts/portfolio.py --help
```

## Usage

The agent loads `SKILL.md` and follows the Quick Start flow. The
shortest invocation is:

```bash
python3 scripts/portfolio.py \
  --address 0xYourWallet \
  --network mainnet
```

Common flags:

| Flag | Purpose |
|---|---|
| `--address` | Wallet to scan (required) |
| `--network` | `mainnet` (default) or `atlantic-testnet` |
| `--custom-erc20` | Comma-separated ERC20 contract addresses |
| `--custom-erc721` | Comma-separated ERC721 contract addresses |
| `--watchlist` | Path to a watchlist JSON (see `references/watchlist.md`) |
| `--out-dir` | Output directory (default: `reports/`) |
| `--formats` | Comma-separated output formats (default: `md,csv,json`) |
| `--include-native` | Include native balance in HHI |
| `--collapse-stables` | Treat stablecoins as one bucket in HHI |

## Output schema (JSON)

```json
{
  "network": "mainnet",
  "address": "0x...",
  "generated_at": "2026-06-04T17:00:00Z",
  "native": { "symbol": "PROS", "wei": "...", "ether": "..." },
  "erc20": [ { "address": "0x...", "symbol": "...", "decimals": 18,
               "raw_balance": "...", "balance": "...", "source": "known" } ],
  "erc721": [ { "address": "0x...", "name": "...", "balance": 3 } ],
  "risk": { "hhi": 5000, "top1_share_pct": 70.0, "top3_share_pct": 100.0,
            "diversification_score": 50, "band": "highly_concentrated" },
  "watchlist_diff": { "in": [], "out": [], "moved": [] },
  "suspicious": [],
  "explorer_links": { "wallet": "...", "holdings": [] }
}
```

## Risk bands

| HHI | Band | Score | Recommended action |
|---|---|---|---|
| 0 – 1500 | diversified | 85 – 100 | Hold |
| 1500 – 2500 | balanced | 75 – 85 | Monitor |
| 2500 – 4999 | concentrated | 50 – 75 | Consider trimming top |
| 5000 – 7500 | highly_concentrated | 25 – 50 | Strong rebalance |
| 7500 – 10000 | single_asset | 0 – 25 | Immediate rebalance |

## Layout

```
SAP/
├── SKILL.md                        # Entry point with frontmatter
├── README.md                       # This file
├── LICENSE                         # MIT-0
├── references/
│   ├── portfolio.md                # Main flow
│   ├── watchlist.md                # Watchlist format & diff semantics
│   ├── risk.md                     # HHI formula, score, bands
│   └── security.md                 # Suspicious-token heuristics
├── assets/
│   ├── watchlist.example.json
│   ├── risk-bands.json
│   ├── symbol-overrides.json
│   └── templates/portfolio.md.tpl  # Markdown report template
├── scripts/
│   └── portfolio.py                # Orchestrator
└── tests/
    └── test_risk.py                # Offline tests for the risk math
```

## Development

```bash
# Run the offline test suite (no `cast`, no RPC)
python3 tests/test_risk.py
```

Expected: all tests pass.

## License

MIT-0. See `LICENSE`.
