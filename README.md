# SPN Architect Pro (SAP)

A portfolio-analysis skill for AI agents. SAP takes a wallet address and returns a single, professional report covering:
- native balance
- ERC20 holdings (known + user-supplied)
- ERC721 holdings (user-supplied)
- concentration risk (HHI, top-1 / top-3 share, 0–100 diversification score)
- watchlist diff (in / out / moved)
- suspicious-token flags (no-code, broken decimals, missing symbol, etc.)

Outputs are written to Markdown, CSV, and JSON. The skill is read-only end to end and never requires a private key.

## How it works

SAP shells out to `cast` to read on-chain state, then assembles the report from a small set of pure-Python helpers. There is one entry point: `scripts/portfolio.py`. Everything else is reference documentation that an agent reads to decide which CLI flags to use and how to interpret the output.

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
| Required binaries | `cast` (Foundry), `python3` |
| Token list source | Bundled in `assets/tokens.json` (overridable via Pharos Skill Engine) |
| Network config source | Bundled in `assets/networks.json` (overridable via Pharos Skill Engine) |
| Output formats | Markdown, CSV, JSON |
| Private key required | No |
| External HTTP calls (script) | None — uses local `cast` CLI only |
| Web scraping | None |
| Third-party APIs (script) | None |

## Installation

> **Tested on:** macOS, Linux, Windows (WSL), **Termux on Android**.

### 1. Install Foundry (provides `cast`)

```bash
curl -L https://foundry.paradigm.xyz | bash
```

This prints a short message ending with "Detected your preferred shell is bash and added foundryup to PATH." You must then reload your shell OR run the `source` line manually:

```bash
# Pick ONE of the two:
source ~/.bashrc          # bash
source ~/.zshrc           # zsh
# OR just open a new terminal session
```

Then install Foundry itself:

```bash
foundryup
```

Verify:

```bash
cast --version
```

> **Termux note:** `foundryup` compiles a Rust toolchain and takes 30–90 seconds on Android. This is normal. Wait for it to finish.

### 2. Install Python 3.10+

```bash
# macOS (Homebrew)
brew install python

# Debian / Ubuntu / WSL
sudo apt update && sudo apt install -y python3 python3-pip

# Termux on Android
pkg install python -y
```

> **Termux note:** `pkg install python` exposes the binary as `python` and (in recent Termux versions) also as `python3`. The script's shebang is `#!/usr/bin/env python3`. If `python3` is missing on your system, run `ln -s $(which python) ~/../usr/bin/python3` (Termux fix) or just call the script with `python scripts/portfolio.py ...` instead of `python3 scripts/portfolio.py ...`.

Verify:

```bash
python --version     # should print 3.10 or higher
```

### 3. Clone and verify

```bash
git clone https://github.com/govvy732/SAP.git
cd SAP
python scripts/portfolio.py --help
```

If `--help` prints the usage, the skill is installed. No additional Python packages are required — the orchestrator uses only the standard library.

### 4. (Optional) Install the Pharos Skill Engine

If you want SAP to use the upstream Pharos token list and network registry instead of the bundled `assets/*.json` files:

```bash
# See: https://github.com/PharosNetwork/pharos-skill-engine
# OpenClaw:  ~/.openclaw/skills/pharos-skill-engine/
# Claude:    ~/.claude/skills/pharos-skill-engine/
# Codex:     ~/.codex/skills/pharos-skill-engine/
```

If the engine is not installed, SAP falls back to the bundled files in `assets/`. The skill runs either way.

### 5. (Optional) Drop into a framework skills directory

```bash
# OpenClaw
mkdir -p ~/.openclaw/skills
ln -s "$(pwd)" ~/.openclaw/skills/spn-architect-pro

# Claude Code
mkdir -p ~/.claude/skills
ln -s "$(pwd)" ~/.claude/skills/spn-architect-pro

# Codex
mkdir -p ~/.codex/skills
ln -s "$(pwd)" ~/.codex/skills/spn-architect-pro
```

## Usage

The agent loads `SKILL.md` and follows the Quick Start flow. The shortest invocation is:

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
  "native": {
    "symbol": "PROS",
    "wei": "...",
    "ether": "..."
  },
  "erc20": [
    {
      "address": "0x...",
      "symbol": "...",
      "decimals": 18,
      "raw_balance": "...",
      "balance": "...",
      "source": "known"
    }
  ],
  "erc721": [
    {
      "address": "0x...",
      "name": "...",
      "balance": 3
    }
  ],
  "risk": {
    "hhi": 5000,
    "top1_share_pct": 70.0,
    "top3_share_pct": 100.0,
    "diversification_score": 50,
    "band": "highly_concentrated"
  },
  "watchlist_diff": {
    "in": [],
    "out": [],
    "moved": []
  },
  "suspicious": [],
  "explorer_links": {
    "wallet": "...",
    "holdings": []
  }
}
```

## Risk bands

The diversification score is computed as:

```
diversification_score = clamp(100 - (HHI / 100), 0, 100)
```

| HHI | Band | Score | Recommended action |
|---|---|---|---|
| 0 – 1500 | `diversified` | 85 – 100 | Hold |
| 1500 – 2500 | `balanced` | 75 – 85 | Monitor |
| 2500 – 4999 | `concentrated` | 50 – 75 | Consider trimming top |
| 5000 – 7500 | `highly_concentrated` | 25 – 50 | Strong rebalance |
| 7500 – 10000 | `single_asset` | 0 – 25 | Immediate rebalance |

> Note: at the band boundaries the score may sit at either end of the listed range. The band is the primary signal; the score is the secondary one.

## Layout

```
SAP/
├── SKILL.md                       # Entry point with frontmatter
├── README.md                      # This file
├── LICENSE                        # MIT-0
├── references/
│   ├── portfolio.md               # Main flow
│   ├── watchlist.md               # Watchlist format & diff semantics
│   ├── risk.md                    # HHI formula, score, bands
│   └── security.md                # Suspicious-token heuristics
├── assets/
│   ├── watchlist.example.json
│   ├── risk-bands.json
│   ├── symbol-overrides.json
│   ├── networks.json              # Bundled network config
│   ├── tokens.json                # Bundled known token list
│   └── templates/portfolio.md.tpl # Markdown report template
├── scripts/
│   └── portfolio.py               # Orchestrator
└── tests/
    └── test_risk.py               # Offline tests for the risk math
```

## Development

```bash
# Run the offline test suite (no `cast`, no RPC)
python3 tests/test_risk.py
```

Expected: all tests pass.

## License

MIT-0. See `LICENSE`.
