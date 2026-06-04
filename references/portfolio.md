# Portfolio Operation Instructions

This is the main flow for SAP. It produces a full portfolio report for a Pharos wallet, including
native balance, all known ERC20s, optional user-supplied tokens and NFTs, risk metrics, and
exportable artifacts.

> **Network Configuration**: Read the target network's `rpcUrl`, `chainId`, `explorerUrl`, and
> `nativeToken` from `pharos-skill-engine`'s `assets/networks.json`. Default to `mainnet`.
>
> **Token List**: Read the per-network token array from
> `pharos-skill-engine`'s `assets/tokens.json`. Use each entry's `address`, `decimals`, and
> `symbol` directly — do **not** make on-chain `decimals()` or `symbol()` calls for known tokens.

---

## CLI: scripts/portfolio.py

The Agent runs the orchestrator script from the user's current working directory. The script
shells out to `cast` and assembles a Markdown report.

### Synopsis

```bash
python3 scripts/portfolio.py \
  --address <wallet> \
  --network <mainnet|atlantic-testnet> \
  [--custom-erc20 0xToken1,0xToken2,...] \
  [--custom-erc721 0xNFT1,0xNFT2,...] \
  [--watchlist assets/watchlist.json] \
  [--out-dir reports] \
  [--formats md,csv,json]
```

### Flags

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--address` | yes | — | Wallet to scan, `0x` + 40 hex |
| `--network` | no | `mainnet` | Network key from `networks.json` |
| `--custom-erc20` | no | — | Comma-separated ERC20 contract addresses |
| `--custom-erc721` | no | — | Comma-separated ERC721 contract addresses |
| `--watchlist` | no | — | Path to a watchlist JSON (see `references/watchlist.md`) |
| `--out-dir` | no | `reports` | Output directory, created if missing |
| `--formats` | no | `md,csv,json` | Comma-separated output formats |

### Output Schema (JSON)

```json
{
  "network": "mainnet",
  "address": "0x1234...",
  "generated_at": "2026-06-04T16:30:00Z",
  "native": {
    "symbol": "PHRS",
    "wei": "1234500000000000000",
    "ether": "1.2345"
  },
  "erc20": [
    {
      "address": "0xE0BE...",
      "symbol": "USDC",
      "decimals": 6,
      "raw_balance": "1000000000",
      "balance": "1000.000000",
      "source": "known"
    }
  ],
  "erc721": [
    {
      "address": "0xNFT...",
      "name": "Pharos Genesis",
      "balance": 3
    }
  ],
  "risk": {
    "hhi": 1842,
    "top1_share_pct": 62.5,
    "top3_share_pct": 91.0,
    "diversification_score": 38,
    "band": "concentrated"
  },
  "watchlist_diff": {
    "in": ["0xUSDC..."],
    "out": ["0xOLD..."],
    "moved": []
  },
  "suspicious": [
    {
      "address": "0xWEIRD...",
      "reason": "decimals() reverted"
    }
  ],
  "explorer_links": {
    "wallet": "https://atlantic.pharosscan.xyz/address/0x1234...",
    "holdings": ["https://.../address/0xUSDC..."]
  }
}
```

### HHI & Diversification

- **HHI** is the Herfindahl-Hirschman Index over the ERC20 share-of-weight (native excluded by
  default). For a single asset, HHI = 10000. For N equal assets, HHI ≈ 10000 / N.
- **diversification_score** is a 0–100 score: `max(0, 100 - (HHI / 100))`, clamped. Higher = more
  diversified.
- **band** comes from `assets/risk-bands.json`.

### Agent Output Behavior

1. Always run the script even if the user only asked for "balances" — the report is the product.
2. After the script exits 0, print the full Markdown report inline in chat. Do not truncate.
3. Offer to also write the artifacts to disk (the script already does this if `--out-dir` is
   set; the Agent should confirm the directory).
4. If `--watchlist` is provided, surface the diff as a separate short summary above the table.
5. If any token is flagged suspicious, surface them in a dedicated callout with the reason.

---

## Custom Contracts

If the user provides extra contract addresses:

- For ERC20s, the script calls `decimals()`, `symbol()`, and `balanceOf(address)` in sequence.
  - If `decimals()` reverts, mark suspicious with reason `"decimals() reverted"`.
  - If `symbol()` reverts, fall back to a truncated address label.
  - If `balanceOf` returns 0, still include it but show `0`.
- For ERC721s, the script calls `balanceOf(address)` and `name()`. The report lists the
  collection name and the count. (It does **not** enumerate individual token IDs — that's a
  follow-up skill.)

The Agent should validate each address format (`0x` + 40 hex) before passing it in. Duplicate
addresses (across known + custom) are de-duplicated; the first occurrence wins.

---

## Gas Preview (Optional Read)

If the user says "estimate the gas to do X with my portfolio" — for example, "how much gas to
rebalance into USDC" — the Agent should:

1. Build a hypothetical `cast send` or `cast estimate` command for the action.
2. Read `references/transaction.md` from `pharos-skill-engine` for the Gas estimation flow.
3. Run `cast estimate` and `cast gas-price` and report the cost in `<nativeToken>`.
4. Do **not** execute the actual transaction — SAP is read-only.

This is a thin layer on top of the engine skill; SAP does not re-implement gas logic.

---

## Agent Failure Modes

| Scenario | Behavior |
|----------|----------|
| User address missing | Prompt for address before running the script |
| User passes a non-Pharos address (e.g., wrong checksum) | `cast` will likely return 0 / empty; treat as a fresh wallet and continue |
| `cast` binary missing | Stop, prompt to install Foundry (the engine skill handles this) |
| `python3` missing | Stop, prompt to install Python 3.10+. Offer a fallback that only queries native + known tokens via direct `cast` calls (no report file) |
| `--out-dir` not writable | Script falls back to writing nothing and prints a warning; the Agent then offers the inline report only |
| Network unreachable for 1+ token | Mark that token as `unreachable` in the report, do not abort |

---

## Cross-Skill Coordination

- For native balance and known ERC20s, prefer **batch reads via `cast call`**. Avoid
  `cast block` / `cast nonce` style RPC noise; SAP only needs view calls.
- For transaction-related follow-ups (transfer, approve, airdrop), refer the user back to
  `pharos-skill-engine` after the portfolio report is delivered.
- For verifying a token contract referenced in the report, refer the user to
  `pharos-skill-engine`'s `references/contract.md#verify-contract`.
