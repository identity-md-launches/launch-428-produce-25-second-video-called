#!/usr/bin/env python3
"""Capture exact Ethereum eth_call results used by Ghosts.

Uses only the Python standard library. Re-running this file requires network
access; build.py uses the saved capture and works offline.
"""

import gzip
import hashlib
import json
import pathlib
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RPC = "https://ethereum.publicnode.com"
NFT = "0x999ce0ce8c5f7661e0c74a568ffe27ceb9177bdb"
PIXEL = "0x07fd9841eeb6a359efb30f861d59bfa1f6b03fca"
BLOCK = 26075124
BLOCK_HEX = hex(BLOCK)

# keccak256 four-byte selectors, independently checked with Foundry's cast sig.
TOTAL_MINTED = "a2309ff8"
MAX_SUPPLY = "32cb6b0c"
ART = "9cb84a01"
SEED_OF = "82829f74"
OWNER_OF = "6352211e"
RENDER_SVG = "d12a4c98"


def rpc_batch(calls):
    payload = json.dumps([
        {"jsonrpc": "2.0", "id": i, "method": m, "params": p}
        for i, (m, p) in enumerate(calls)
    ]).encode()
    for attempt in range(6):
        try:
            response = subprocess.run(
                ["curl", "-fsS", "--max-time", "90", "-H", "Content-Type: application/json",
                 "--data-binary", "@-", RPC], input=payload, capture_output=True, check=True
            )
            raw = json.loads(response.stdout)
            if not isinstance(raw, list):
                raw = [raw]
            by_id = {item["id"]: item for item in raw}
            values = []
            for i in range(len(calls)):
                item = by_id[i]
                if "error" in item:
                    raise RuntimeError(str(item["error"]))
                values.append(item["result"])
            return values
        except Exception:
            if attempt == 5:
                raise
            time.sleep(1.5 * (attempt + 1))


def call(to, selector, arg=None):
    data = "0x" + selector + (format(arg, "064x") if arg is not None else "")
    return ("eth_call", [{"to": to, "data": data}, BLOCK_HEX])


def decode_uint(raw):
    return int(raw, 16)


def decode_svg(raw):
    raw = bytes.fromhex(raw[2:])
    offset = int.from_bytes(raw[:32], "big")
    length = int.from_bytes(raw[offset:offset + 32], "big")
    svg = raw[offset + 32:offset + 32 + length].decode("utf-8")
    if not svg.startswith('<svg xmlns="http://www.w3.org/2000/svg"') or not svg.endswith("</svg>"):
        raise ValueError("Unexpected SVG call result")
    return svg


def chunks(items, n):
    for start in range(0, len(items), n):
        yield items[start:start + n]


def main():
    DATA.mkdir(exist_ok=True)
    chain_raw, block, count_raw, cap_raw, art_raw = rpc_batch([
        ("eth_chainId", []),
        ("eth_getBlockByNumber", [BLOCK_HEX, False]),
        call(NFT, TOTAL_MINTED),
        call(NFT, MAX_SUPPLY),
        call(NFT, ART),
    ])
    if decode_uint(chain_raw) != 1:
        raise ValueError("RPC is not Ethereum mainnet")
    count = decode_uint(count_raw)
    cap = decode_uint(cap_raw)
    art = "0x" + art_raw[-40:].lower()
    if art != PIXEL:
        raise ValueError(f"NFT ART() returned {art}, expected {PIXEL}")
    if not (0 < count <= cap):
        raise ValueError("Invalid mint count")
    print("block", BLOCK, block["hash"], "totalMinted", count, "MAX_SUPPLY", cap, flush=True)

    token_ids = list(range(1, count + 1))
    token_seeds = []
    for group in chunks(token_ids, 50):
        results = rpc_batch([call(NFT, SEED_OF, token_id) for token_id in group])
        token_seeds.extend(decode_uint(r) for r in results)
    owned_seeds = {s for s in token_seeds if s != 0}
    print("revealed seeds", len(owned_seeds), flush=True)

    # Token #1 is used if it has been revealed; otherwise take the first
    # revealed token. ownerOf is checked only as an existence test. Its value
    # is deliberately excluded from every output file.
    real_id = next(i for i, seed in enumerate(token_seeds, 1) if seed != 0)
    real_seed = token_seeds[real_id - 1]
    owner = decode_uint(rpc_batch([call(NFT, OWNER_OF, real_id)])[0])
    if owner == 0:
        raise ValueError("Selected token has no owner")

    # Distinct 32-byte inputs, deterministic and disjoint from every revealed
    # minted seed at the pinned block. Visual duplicates are also discarded.
    ghosts = []
    seen_svg = set()
    candidate = 0
    while len(ghosts) < 320:
        batch = []
        while len(batch) < 24:
            seed = int.from_bytes(hashlib.sha256(f"IdentityMD Ghosts / {candidate:06d}".encode()).digest(), "big")
            candidate += 1
            if seed not in owned_seeds and seed != 0:
                batch.append(seed)
        results = rpc_batch([call(PIXEL, RENDER_SVG, seed) for seed in batch])
        for seed, raw in zip(batch, results):
            svg = decode_svg(raw)
            digest = hashlib.sha256(svg.encode()).hexdigest()
            if digest not in seen_svg:
                seen_svg.add(digest)
                ghosts.append({"seed": "0x" + format(seed, "064x"), "svg": svg})
            if len(ghosts) == 320:
                break
        print("ghost calls", len(ghosts), flush=True)

    real_svg = decode_svg(rpc_batch([call(PIXEL, RENDER_SVG, real_seed)])[0])
    if real_svg in [g["svg"] for g in ghosts]:
        raise ValueError("Real token visually duplicates a ghost")
    capture = {
        "chain_id": 1,
        "rpc": RPC,
        "block": BLOCK,
        "block_hash": block["hash"],
        "nft": NFT,
        "renderer": PIXEL,
        "total_minted": count,
        "max_supply": cap,
        "revealed_token_count": len(owned_seeds),
        "token_seeds_at_block": ["0x" + format(seed, "064x") for seed in token_seeds],
        "real_token": {"id": real_id, "seed": "0x" + format(real_seed, "064x"), "svg": real_svg},
        "ghosts": ghosts,
    }
    with gzip.open(DATA / "chain_calls.json.gz", "wt", encoding="utf-8", compresslevel=9) as file:
        json.dump(capture, file, separators=(",", ":"))
    (DATA / "ghost_seeds.txt").write_text("\n".join(g["seed"] for g in ghosts) + "\n")
    print("saved", DATA / "chain_calls.json.gz", flush=True)


if __name__ == "__main__":
    main()
