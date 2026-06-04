# Portfolio Report — {address}

- **Network:** {network_label} (`{network_key}`)
- **Generated:** {generated_at}
- **Scan scope:** {scan_scope}

> {network_warning}

---

## Summary

| Metric | Value |
|--------|-------|
| Native balance | {native_ether} {native_symbol} ({native_wei} wei) |
| ERC20 holdings (non-zero) | {erc20_count} |
| ERC721 holdings (non-zero) | {erc721_count} |
| Diversification score | **{diversification_score} / 100** ({risk_band}) |
| Top-1 share | {top1_share}% |
| Top-3 share | {top3_share}% |
| HHI | {hhi} |

---

## Watchlist Diff

{in_block}

---

## Suspicious Tokens

{suspicious_block}

---

## Native

| Token | Balance | Wei |
|-------|---------|-----|
| {native_symbol} | {native_ether} | {native_wei} |

Explorer: {wallet_link}

---

## ERC20 Holdings

| Source | Symbol | Balance | Raw | Address | Notes |
|--------|--------|---------|-----|---------|-------|
{erc20_rows}

---

## ERC721 Holdings

| Collection | Items | Address |
|------------|-------|---------|
{erc721_rows}

---

## Risk Notes

{risk_block}

---

## Footer

- Tool: SPN Architect Pro (SAP) v0.1.0
- Engine: pharos-skill-engine
- This report is informational and read-only. No transactions were sent.
