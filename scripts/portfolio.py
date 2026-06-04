#!/usr/bin/env python3
"""
SPN Architect Pro (SAP) — portfolio orchestrator.

Reads Pharos network config and known token list from the installed
`pharos-skill-engine` skill, queries a wallet for native + ERC20 + (optional)
ERC721 holdings, computes concentration risk, optionally diffs against a
watchlist, flags suspicious tokens, and writes Markdown / CSV / JSON reports.

The script shells out to `cast` for all RPC calls. It is read-only and never
touches a private key.

Usage:
    python3 scripts/portfolio.py \
        --address 0xYourWallet \
        --network mainnet \
        [--custom-erc20 0xToken1,0xToken2] \
        [--custom-erc721 0xNFT1] \
        [--watchlist assets/watchlist.json] \
        [--out-dir reports] \
        [--formats md,csv,json] \
        [--include-native] \
        [--collapse-stables]

Exit codes:
    0  success
    1  invalid CLI args
    2  cast missing
    3  network config missing
    4  fatal on-chain error (one or more critical reads failed)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")

# Paths to pharos-skill-engine assets. The user can override SAP_ENGINE_DIR
# to point at a non-default install location.
DEFAULT_ENGINE_DIR = Path(
    os.environ.get(
        "SAP_ENGINE_DIR",
        str(Path.home() / ".pharos" / "skills" / "pharos-skill-engine"),
    )
)

# Path to the SAP skill itself, used to load its own asset files.
DEFAULT_SAP_DIR = Path(os.environ.get("SAP_DIR", str(Path(__file__).resolve().parent.parent)))


# --------------------------------------------------------------------------- #
# Data classes                                                                #
# --------------------------------------------------------------------------- #


@dataclass
class TokenHolding:
    address: str
    symbol: str
    decimals: int
    raw_balance: str
    balance: str
    source: str  # "known" or "custom"
    suspicious: list[str] = field(default_factory=list)


@dataclass
class NFTHolding:
    address: str
    name: str
    balance: int


@dataclass
class RiskReport:
    hhi: int
    top1_share_pct: float
    top3_share_pct: float
    diversification_score: int
    band: str


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def die(msg: str, code: int = 1) -> None:
    print(f"SAP error: {msg}", file=sys.stderr)
    sys.exit(code)


def run_cast(args: list[str], timeout: int = 15) -> tuple[int, str, str]:
    """Run a cast command, returning (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            ["cast", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        die("`cast` binary not found in PATH. Install Foundry first.", code=2)
    except subprocess.TimeoutExpired:
        return 124, "", "cast timeout"
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def load_json(path: Path) -> Any:
    if not path.exists():
        die(f"Required file missing: {path}", code=3)
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        die(f"Invalid JSON in {path}: {exc}", code=3)


def validate_address(addr: str) -> str:
    if not ADDRESS_RE.match(addr):
        die(f"Invalid address format: {addr!r}. Expected 0x + 40 hex.", code=1)
    return addr


# --------------------------------------------------------------------------- #
# Engine integration                                                          #
# --------------------------------------------------------------------------- #


def resolve_network(engine_dir: Path, network_key: str) -> dict[str, Any]:
    nets_path = engine_dir / "assets" / "networks.json"
    data = load_json(nets_path)
    for net in data.get("networks", []):
        if net.get("name") == network_key:
            return net
    die(
        f"Network {network_key!r} not found in {nets_path}. "
        f"Available: {[n['name'] for n in data.get('networks', [])]}",
        code=3,
    )


def load_known_tokens(engine_dir: Path, network_key: str) -> list[dict[str, Any]]:
    tokens_path = engine_dir / "assets" / "tokens.json"
    data = load_json(tokens_path)
    return data.get(network_key, [])


# --------------------------------------------------------------------------- #
# On-chain reads                                                              #
# --------------------------------------------------------------------------- #


def read_native(rpc_url: str) -> tuple[str, str]:
    rc, wei, _ = run_cast(["balance", "--rpc-url", rpc_url])
    if rc != 0:
        die(f"cast balance failed: rc={rc}", code=4)
    rc2, ether, _ = run_cast(["balance", "--rpc-url", rpc_url, "--ether"])
    if rc2 != 0:
        die(f"cast balance --ether failed: rc={rc2}", code=4)
    return wei, ether


def ierc20_balance_of(rpc_url: str, token: str, holder: str) -> str:
    rc, out, _ = run_cast([
        "call", token, "balanceOf(address)(uint256)", holder, "--rpc-url", rpc_url,
    ])
    if rc != 0:
        return ""
    return out.strip()


def ierc20_decimals(rpc_url: str, token: str) -> tuple[int, str | None]:
    rc, out, _ = run_cast([
        "call", token, "decimals()(uint8)", "--rpc-url", rpc_url,
    ])
    if rc != 0 or not out.strip():
        return 18, "decimals_reverted"
    try:
        return int(out.strip()), None
    except ValueError:
        return 18, "decimals_decode_error"


def ierc20_symbol(rpc_url: str, token: str) -> tuple[str, str | None]:
    rc, out, _ = run_cast([
        "call", token, "symbol()(string)", "--rpc-url", rpc_url,
    ])
    if rc != 0 or not out.strip():
        return token[:8] + "…", "symbol_reverted"
    return out.strip(), None


def ierc20_total_supply(rpc_url: str, token: str) -> tuple[int, str | None]:
    rc, out, _ = run_cast([
        "call", token, "totalSupply()(uint256)", "--rpc-url", rpc_url,
    ])
    if rc != 0 or not out.strip():
        return 0, "total_supply_reverted"
    try:
        return int(out.strip()), None
    except ValueError:
        return 0, "total_supply_decode_error"


def ierc721_balance_of(rpc_url: str, nft: str, holder: str) -> int:
    rc, out, _ = run_cast([
        "call", nft, "balanceOf(address)(uint256)", holder, "--rpc-url", rpc_url,
    ])
    if rc != 0 or not out.strip():
        return 0
    try:
        return int(out.strip())
    except ValueError:
        return 0


def ierc721_name(rpc_url: str, nft: str) -> str:
    rc, out, _ = run_cast([
        "call", nft, "name()(string)", "--rpc-url", rpc_url,
    ])
    if rc != 0 or not out.strip():
        return nft[:8] + "…"
    return out.strip()


# --------------------------------------------------------------------------- #
# Token collection                                                            #
# --------------------------------------------------------------------------- #


def collect_erc20(
    rpc_url: str,
    holder: str,
    known: list[dict[str, Any]],
    custom_addrs: list[str],
    overrides: dict[str, dict[str, Any]],
) -> tuple[list[TokenHolding], list[dict[str, str]]]:
    holdings: list[TokenHolding] = []
    suspicious: list[dict[str, str]] = []
    seen: set[str] = set()

    # Known tokens
    for tok in known:
        addr = tok["address"].lower()
        if addr in seen:
            continue
        seen.add(addr)
        sym = tok.get("symbol", addr[:8] + "…")
        dec = int(tok.get("decimals", 18))
        raw = ierc20_balance_of(rpc_url, tok["address"], holder)
        if not raw or raw == "0":
            continue
        try:
            value = int(raw) / (10 ** dec)
        except ValueError:
            suspicious.append({"address": tok["address"], "reason": "decode_error"})
            continue
        holdings.append(TokenHolding(
            address=tok["address"],
            symbol=sym,
            decimals=dec,
            raw_balance=raw,
            balance=f"{value:,.{min(dec, 6)}f}".rstrip("0").rstrip("."),
            source="known",
        ))

    # Custom tokens
    for addr in custom_addrs:
        addr_lc = addr.lower()
        if addr_lc in seen:
            continue
        seen.add(addr_lc)
        # Apply manual override if present
        override = overrides.get(addr) or overrides.get(addr.lower()) or {}
        if override:
            sym = override.get("symbol", addr[:8] + "…")
            dec = int(override.get("decimals", 18))
            flags: list[str] = []
        else:
            dec, dec_flag = ierc20_decimals(rpc_url, addr)
            sym, sym_flag = ierc20_symbol(rpc_url, addr)
            flags = [f for f in [dec_flag, sym_flag] if f]
            # Extra heuristics
            ts, ts_flag = ierc20_total_supply(rpc_url, addr)
            if ts_flag:
                flags.append(ts_flag)
            if dec > 18:
                flags.append("decimals_out_of_range")
            if not sym or sym.strip() == "":
                flags.append("symbol_missing")
        raw = ierc20_balance_of(rpc_url, addr, holder)
        if not raw:
            flags.append("no_code_or_revert")
            suspicious.append({"address": addr, "reason": ",".join(flags) or "no_response"})
            continue
        try:
            value = int(raw) / (10 ** dec)
        except ValueError:
            flags.append("decode_error")
            suspicious.append({"address": addr, "reason": ",".join(set(flags))})
            continue
        if flags:
            suspicious.append({"address": addr, "reason": ",".join(set(flags))})
        holdings.append(TokenHolding(
            address=addr,
            symbol=sym,
            decimals=dec,
            raw_balance=raw,
            balance=f"{value:,.{min(dec, 6)}f}".rstrip("0").rstrip("."),
            source="custom",
            suspicious=flags,
        ))

    return holdings, suspicious


def collect_erc721(
    rpc_url: str, holder: str, nft_addrs: list[str]
) -> list[NFTHolding]:
    out: list[NFTHolding] = []
    for nft in nft_addrs:
        n = ierc721_balance_of(rpc_url, nft, holder)
        if n <= 0:
            continue
        name = ierc721_name(rpc_url, nft)
        out.append(NFTHolding(address=nft, name=name, balance=n))
    return out


# --------------------------------------------------------------------------- #
# Risk & diff                                                                 #
# --------------------------------------------------------------------------- #


def load_risk_bands(sap_dir: Path) -> dict[str, Any]:
    path = sap_dir / "assets" / "risk-bands.json"
    if not path.exists():
        return {"bands": [], "stablecoin_pattern": "USDC|USDT|DAI|FRAX"}
    return load_json(path)


def compute_risk(
    holdings: list[TokenHolding],
    native_ether: float,
    include_native: bool,
    collapse_stables: bool,
    bands_cfg: dict[str, Any],
) -> RiskReport:
    weights: list[tuple[str, float]] = []
    if include_native and native_ether > 0:
        weights.append(("NATIVE", native_ether))
    if collapse_stables:
        stable_re = re.compile(bands_cfg.get("stablecoin_pattern", "USDC|USDT|DAI|FRAX"))
        stable_total = 0.0
        stable_count = 0
        non_stable: list[tuple[str, float]] = []
        for h in holdings:
            try:
                v = float(h.balance.replace(",", ""))
            except ValueError:
                continue
            if stable_re.search(h.symbol or ""):
                stable_total += v
                stable_count += 1
            else:
                non_stable.append((h.symbol, v))
        if stable_total > 0:
            weights.append((f"STABLES({stable_count})", stable_total))
        weights.extend(non_stable)
    else:
        for h in holdings:
            try:
                v = float(h.balance.replace(",", ""))
            except ValueError:
                continue
            if v > 0:
                weights.append((h.symbol, v))

    total = sum(v for _, v in weights)
    if total <= 0:
        return RiskReport(hhi=0, top1_share_pct=0.0, top3_share_pct=0.0,
                          diversification_score=100, band="empty")
    shares = sorted((100.0 * v / total for _, v in weights), reverse=True)
    hhi = int(round(sum(s * s for s in shares)))
    top1 = shares[0] if shares else 0.0
    top3 = sum(shares[:3])
    score = max(0, min(100, 100 - (hhi // 100)))
    band = _band_for(hhi, bands_cfg.get("bands", []))
    return RiskReport(
        hhi=hhi,
        top1_share_pct=round(top1, 2),
        top3_share_pct=round(top3, 2),
        diversification_score=score,
        band=band,
    )


def _band_for(hhi: int, bands: list[dict[str, Any]]) -> str:
    for b in bands:
        if b["hhi_min"] <= hhi <= b["hhi_max"]:
            return b["name"]
    return "unknown"


def diff_watchlist(
    watchlist: dict[str, Any],
    holdings: list[TokenHolding],
    nfts: list[NFTHolding],
) -> dict[str, list[dict[str, str]]]:
    held = {h.address.lower(): h for h in holdings}
    held_nft = {n.address.lower(): n for n in nfts}
    out = {"in": [], "out": [], "moved": []}
    for item in watchlist.get("items", []):
        addr = item["address"].lower()
        if not ADDRESS_RE.match(item["address"]):
            continue
        kind = item.get("kind", "erc20")
        if kind == "erc20":
            if addr in held:
                out["in"].append({"address": item["address"], "symbol": held[addr].symbol})
            else:
                out["out"].append({"address": item["address"], "symbol_hint": item.get("symbol_hint", "")})
        else:
            if addr in held_nft:
                out["in"].append({"address": item["address"], "symbol": held_nft[addr].name})
            else:
                out["out"].append({"address": item["address"], "symbol_hint": item.get("symbol_hint", "")})
    return out


# --------------------------------------------------------------------------- #
# Output                                                                      #
# --------------------------------------------------------------------------- #


def render_markdown(
    address: str,
    network: dict[str, Any],
    generated_at: str,
    scan_scope: str,
    native: tuple[str, str],
    erc20: list[TokenHolding],
    erc721: list[NFTHolding],
    risk: RiskReport,
    watchlist_diff: dict[str, list[dict[str, str]]] | None,
    suspicious: list[dict[str, str]],
) -> str:
    sap_dir = Path(__file__).resolve().parent.parent
    tpl_path = sap_dir / "assets" / "templates" / "portfolio.md.tpl"
    tpl = tpl_path.read_text() if tpl_path.exists() else FALLBACK_TEMPLATE

    native_wei, native_ether = native
    sym = network.get("nativeToken", "ETH")
    explorer = network.get("explorerUrl", "").rstrip("/")
    wallet_link = f"{explorer}/address/{address}" if explorer else ""

    rows = []
    for h in erc20:
        marker = "⚠️ " if h.suspicious else ""
        rows.append(
            f"| {h.source} | {marker}{h.symbol} | {h.balance} | {h.raw_balance} | "
            f"`{h.address}` | {','.join(h.suspicious) or '—'} |"
        )
    erc20_rows = "\n".join(rows) if rows else "| — | — | — | — | — | — |"

    nft_rows = []
    for n in erc721:
        nft_rows.append(f"| {n.name} | {n.balance} | `{n.address}` |")
    erc721_rows = "\n".join(nft_rows) if nft_rows else "| — | — | — |"

    in_block = "_No watchlist provided._"
    if watchlist_diff is not None:
        ins = "\n".join(f"- ✅ `{x['address']}` ({x.get('symbol', '')})" for x in watchlist_diff["in"]) or "_none_"
        outs = "\n".join(f"- ❌ `{x['address']}` ({x.get('symbol_hint', '')})" for x in watchlist_diff["out"]) or "_none_"
        in_block = f"**Held (in watchlist)**\n{ins}\n\n**Not held (in watchlist)**\n{outs}"

    if suspicious:
        susp = "\n".join(
            f"- `{s['address']}` — {s['reason']}" for s in suspicious
        )
        suspicious_block = f"⚠️ The following tokens triggered one or more heuristics:\n\n{susp}"
    else:
        suspicious_block = "_No suspicious tokens detected._"

    network_warning = ""
    if network["name"] == "mainnet":
        network_warning = "**Network: Pharos mainnet (real assets).**"

    risk_block = (
        f"- HHI = **{risk.hhi}** → band `{risk.band}`\n"
        f"- Diversification score: **{risk.diversification_score} / 100**"
    )

    return tpl.format(
        address=address,
        network_label={"atlantic-testnet": "Atlantic Testnet", "mainnet": "Pharos Mainnet"}.get(
            network["name"], network["name"]
        ),
        network_key=network["name"],
        generated_at=generated_at,
        scan_scope=scan_scope,
        network_warning=network_warning,
        native_ether=native_ether,
        native_symbol=sym,
        native_wei=native_wei,
        erc20_count=len(erc20),
        erc721_count=len(erc721),
        diversification_score=risk.diversification_score,
        risk_band=risk.band,
        top1_share=risk.top1_share_pct,
        top3_share=risk.top3_share_pct,
        hhi=risk.hhi,
        in_block=in_block,
        suspicious_block=suspicious_block,
        wallet_link=wallet_link,
        erc20_rows=erc20_rows,
        erc721_rows=erc721_rows,
        risk_block=risk_block,
    )


FALLBACK_TEMPLATE = """# Portfolio Report — {address}

- **Network:** {network_label} (`{network_key}`)
- **Generated:** {generated_at}
- **Scan scope:** {scan_scope}

> {network_warning}

## Summary

| Metric | Value |
|--------|-------|
| Native balance | {native_ether} {native_symbol} |
| ERC20 holdings | {erc20_count} |
| ERC721 holdings | {erc721_count} |
| Diversification | {diversification_score}/100 ({risk_band}) |

## Watchlist Diff
{in_block}

## Suspicious Tokens
{suspicious_block}

## ERC20
{erc20_rows}

## ERC721
{erc721_rows}

## Risk
{risk_block}
"""


def render_csv(erc20: list[TokenHolding], erc721: list[NFTHolding], address: str, network_key: str) -> str:
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["address", "network", "kind", "symbol", "balance", "raw", "source", "suspicious"])
    for h in erc20:
        w.writerow([address, network_key, "erc20", h.symbol, h.balance, h.raw_balance, h.source, ";".join(h.suspicious)])
    for n in erc721:
        w.writerow([address, network_key, "erc721", n.name, n.balance, "", "custom", ""])
    return buf.getvalue()


def render_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True)


# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #


def main() -> int:
    p = argparse.ArgumentParser(description="SPN Architect Pro (SAP) — portfolio orchestrator")
    p.add_argument("--address", required=True, help="Wallet to scan")
    p.add_argument("--network", default="mainnet", help="Network key from networks.json (default: mainnet)")
    p.add_argument("--custom-erc20", default="", help="Comma-separated ERC20 contract addresses")
    p.add_argument("--custom-erc721", default="", help="Comma-separated ERC721 contract addresses")
    p.add_argument("--watchlist", default="", help="Path to a watchlist JSON file")
    p.add_argument("--out-dir", default="reports", help="Output directory")
    p.add_argument("--formats", default="md,csv,json", help="Comma-separated output formats")
    p.add_argument("--include-native", action="store_true", help="Include native in HHI")
    p.add_argument("--collapse-stables", action="store_true", help="Treat stables as one bucket in HHI")
    p.add_argument("--engine-dir", default=str(DEFAULT_ENGINE_DIR), help="Path to pharos-skill-engine")
    p.add_argument("--sap-dir", default=str(DEFAULT_SAP_DIR), help="Path to this SAP skill")
    args = p.parse_args()

    address = validate_address(args.address)
    engine_dir = Path(args.engine_dir)
    sap_dir = Path(args.sap_dir)

    if not engine_dir.exists():
        die(
            f"pharos-skill-engine not found at {engine_dir}. "
            f"Install it (https://github.com/PharosNetwork/pharos-skill-engine) or set SAP_ENGINE_DIR.",
            code=3,
        )

    network = resolve_network(engine_dir, args.network)
    rpc_url = network["rpcUrl"]
    known = load_known_tokens(engine_dir, args.network)

    custom_erc20 = [a.strip() for a in args.custom_erc20.split(",") if a.strip()]
    custom_erc721 = [a.strip() for a in args.custom_erc721.split(",") if a.strip()]
    for a in custom_erc20 + custom_erc721:
        validate_address(a)

    # Load SAP asset files
    overrides_path = sap_dir / "assets" / "symbol-overrides.json"
    overrides = {}
    if overrides_path.exists():
        try:
            overrides = load_json(overrides_path).get("overrides", {})
        except SystemExit:
            overrides = {}
    bands_cfg = load_risk_bands(sap_dir)

    # On-chain reads
    native = read_native(rpc_url)
    erc20_holdings, suspicious = collect_erc20(rpc_url, address, known, custom_erc20, overrides)
    erc721_holdings = collect_erc721(rpc_url, address, custom_erc721)

    # Watchlist
    watchlist_diff = None
    if args.watchlist:
        wl_path = Path(args.watchlist)
        if wl_path.exists():
            wl = load_json(wl_path)
            watchlist_diff = diff_watchlist(wl, erc20_holdings, erc721_holdings)

    # Risk
    try:
        native_ether_f = float(native[1])
    except ValueError:
        native_ether_f = 0.0
    risk = compute_risk(erc20_holdings, native_ether_f, args.include_native, args.collapse_stables, bands_cfg)

    # Output
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    scan_scope = (
        f"{len(known)} known tokens"
        + (f" + {len(custom_erc20)} custom ERC20s" if custom_erc20 else "")
        + (f" + {len(custom_erc721)} custom ERC721s" if custom_erc721 else "")
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = out_dir / f"{address}_{stamp}"

    formats = {f.strip().lower() for f in args.formats.split(",") if f.strip()}

    # Build machine-readable report
    report_obj = {
        "network": network["name"],
        "address": address,
        "generated_at": generated_at,
        "native": {
            "symbol": network.get("nativeToken", ""),
            "wei": native[0],
            "ether": native[1],
        },
        "erc20": [asdict(h) for h in erc20_holdings],
        "erc721": [asdict(n) for n in erc721_holdings],
        "risk": asdict(risk),
        "watchlist_diff": watchlist_diff,
        "suspicious": suspicious,
        "explorer_links": {
            "wallet": f"{network.get('explorerUrl', '').rstrip('/')}/address/{address}",
            "holdings": [
                f"{network.get('explorerUrl', '').rstrip('/')}/address/{h.address}"
                for h in erc20_holdings
            ] + [
                f"{network.get('explorerUrl', '').rstrip('/')}/address/{n.address}"
                for n in erc721_holdings
            ],
        },
    }

    written: list[str] = []
    if "md" in formats:
        md = render_markdown(
            address, network, generated_at, scan_scope,
            native, erc20_holdings, erc721_holdings,
            risk, watchlist_diff, suspicious,
        )
        (base.with_suffix(".md")).write_text(md)
        written.append(str(base.with_suffix(".md")))
    if "csv" in formats:
        (base.with_suffix(".csv")).write_text(
            render_csv(erc20_holdings, erc721_holdings, address, network["name"])
        )
        written.append(str(base.with_suffix(".csv")))
    if "json" in formats:
        (base.with_suffix(".json")).write_text(render_json(report_obj))
        written.append(str(base.with_suffix(".json")))

    # Stdout summary
    print("=== SAP Portfolio Report ===")
    print(f"Network: {network['name']}")
    print(f"Address: {address}")
    print(f"Native:  {native[1]} {network.get('nativeToken', '')}")
    print(f"ERC20s:  {len(erc20_holdings)} (non-zero)")
    print(f"ERC721s: {len(erc721_holdings)} (non-zero)")
    print(f"HHI:     {risk.hhi}  Band: {risk.band}  Score: {risk.diversification_score}/100")
    if suspicious:
        print(f"Suspicious tokens: {len(suspicious)}")
    if written:
        print("Artifacts:")
        for p in written:
            print(f"  - {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
