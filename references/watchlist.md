# Watchlist Operation Instructions

SAP can maintain a watchlist of token contracts the user cares about. After a portfolio scan, the
diff between the watchlist and the current holdings is reported.

## Watchlist File Format

The watchlist lives at `assets/watchlist.json` (relative to the SAP skill root) or anywhere the user
points with `--watchlist`. Format:

```json
{
  "label": "Govvy's main wallet watchlist",
  "updated_at": "2026-05-30T10:00:00Z",
  "items": [
    {
      "address": "0xE0BE08c77f415F577A1B3A9aD7a1Df1479564ec8",
      "symbol_hint": "USDC",
      "kind": "erc20",
      "notes": "Stablecoin allocation"
    },
    {
      "address": "0xNftContract0000000000000000000000000000",
      "symbol_hint": "Pharos Genesis",
      "kind": "erc721",
      "notes": "Genesis mint"
    }
  ]
}
```

### Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `label` | no | Human-readable name for the watchlist |
| `updated_at` | no | ISO-8601 timestamp; the Agent may update this on edits |
| `items[].address` | yes | Contract address, `0x` + 40 hex |
| `items[].symbol_hint` | no | What the user calls it; falls back to on-chain `symbol()` |
| `items[].kind` | yes | `erc20` or `erc721` |
| `items[].notes` | no | Free-form note shown next to the row in the report |

## Diff Semantics

After a scan, the Agent computes:

| Bucket | Definition |
|--------|------------|
| `in` | Item is in the watchlist AND currently has a non-zero balance |
| `out` | Item is in the watchlist but currently has a zero balance (or no code at the address) |
| `moved` | Item's balance changed by > 5% (informational only; SAP does not track historical balances beyond the current scan) |
| `untracked` | Token the user actually holds but did NOT include in the watchlist — surfaced as a "you might want to add this" hint, not as an alert |

> **Note**: `moved` only makes sense across multiple scans. A single scan reports the current
> balance; the Agent can call out "compared to your last reported balance of X, this is now Y"
> if the user provides the prior number.

## Editing the Watchlist

The Agent must never silently rewrite the watchlist. When the user adds or removes an item, the
Agent:

1. Shows the proposed diff to the watchlist in chat.
2. Asks for explicit confirmation.
3. Writes the new file in place (preserves indentation, only touches the `items` array and
   `updated_at`).
4. Re-runs the scan to verify the new state.

## Validation

- All addresses must match `^0x[a-fA-F0-9]{40}$`. Reject otherwise.
- `kind` must be `erc20` or `erc721`.
- Duplicate addresses (same `address` + `kind`) within `items` are a hard error. Tell the user.

## Example Interaction

```
User: Add 0xE0BE08c77f415F577A1B3A9aD7a1Df1479564ec8 to my watchlist as USDC, erc20.

Agent: I'll add it. Current watchlist will become:
  • USDC (erc20) — Stablecoin allocation        [existing]
  • USDC (erc20) — Stablecoin allocation        [new]
  • Pharos Genesis (erc20) — Genesis mint        [existing]

Confirm? (yes/no)

User: yes

Agent: Updated. Re-running scan…
[portfolio report with watchlist diff]
```
