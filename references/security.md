# Suspicious-Token Detection

SAP applies a small set of heuristics to flag tokens that may be unsafe, broken, or simply
non-standard. The goal is to **inform**, not to alarm — the user decides what to do.

## Heuristics

| Check | Heuristic | Flag Reason |
|-------|-----------|-------------|
| Contract has no code | `cast call` returns empty / reverts with no data | `no_code` |
| `decimals()` reverts | Return value is empty hex | `decimals_reverted` |
| `symbol()` reverts or returns empty | Return value is empty hex or `0x` | `symbol_missing` |
| `decimals()` returns > 18 | Decimal precision above 18 is suspicious | `decimals_out_of_range` |
| `name()` is the same as `symbol()` and length is short (< 4) | Often a scam pattern | `name_symbol_collision` |
| `totalSupply()` is 0 | A token with zero supply and non-zero holders is unusual | `zero_total_supply` |
| `balanceOf` returns a value the script can't decode | ABI mismatch | `decode_error` |

Any token that triggers one or more heuristics is added to the report's `suspicious` array with
the reason(s). Holdings are still reported, but with a ⚠️ marker in the table.

## Manual Overrides

If a token is in `assets/symbol-overrides.json`, the Agent uses the override for `symbol` and
`decimals` instead of calling on-chain. This is useful for:

- Tokens that revert on `decimals()` but are actually safe (some legitimate tokens).
- Tokens whose `symbol()` returns a long garbage string.

`assets/symbol-overrides.json` format:

```json
{
  "0xWeirdToken0000000000000000000000000000": {
    "symbol": "WPRX",
    "decimals": 18,
    "note": "Verified manually on 2026-05-15"
  }
}
```

The Agent should not auto-populate this file. It only adds entries when the user explicitly
confirms an override.

## What SAP Does NOT Do

- **No honeypot simulation.** SAP does not attempt to simulate a sell to detect a honeypot.
  That requires write operations and is out of scope.
- **No contract-source review.** SAP does not fetch verified source code.
- **No scam-list lookup.** SAP does not call external APIs (no GoPlus, no TokenSniffer). This
  keeps the skill offline and reproducible.
- **No transfer-tax detection.** SAP does not measure actual `transfer` return value vs. balance
  delta. That is a separate skill (`pharos-skill-engine` covers reads; tax detection needs a
  write simulation).

If the user wants stronger checks, the Agent should direct them to dedicated audit tools and
treat SAP's output as a starting point.

## User Communication

When the report contains suspicious tokens, the Agent formats them as a callout box at the top
of the report:

```
⚠️  Suspicious Tokens Detected
  • 0xWEIRD… (decimals_reverted, symbol_missing)
  • 0xHONEYPOT… (decimals_out_of_range, name_symbol_collision)

These tokens are still listed in the holdings table below for completeness, but treat any
on-chain interaction with caution.
```

The Agent does not refuse to display the holdings and does not refuse to do further read-only
work on those contracts. The flag is informational.
