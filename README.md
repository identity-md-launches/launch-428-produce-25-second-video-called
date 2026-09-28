# Ghosts

[Watch the 25-second video](artifacts/video.mp4)

## Delivery

| Item | Value |
| --- | --- |
| Output | `artifacts/video.mp4` |
| Duration | 25.000 seconds, 25 fps |
| Frame size | 1280 × 720 |
| Video | H.264, yuv420p, fast-start MP4 |
| Audio | AAC mono, 48 kHz; original low-volume synthesized mechanical clicks, with silence from 0–3 seconds |
| File size | 435,713 bytes |

## Chain provenance

All calls were made against Ethereum mainnet (`eth_chainId = 1`) at **block 26,075,124** (`0x79e9b784a5cd6afb3294bc1a56fcad887a5a78935c36a045d0c4a8cfd1d1f7a2`). The SwarmPepe contract's `ART()` returned the supplied PixelArt address. The [verified renderer source](https://eth.blockscout.com/api/v2/smart-contracts/0x07Fd9841eEB6a359EfB30f861D59bFa1f6B03FcA) and ABI identify `renderSVG(uint256)` as `pure`; direct `eth_call` requests at that block returned valid SVGs for arbitrary 32-byte seeds. The [verified NFT source](https://eth.blockscout.com/api/v2/smart-contracts/0x999ce0ce8c5f7661e0c74a568ffe27ceb9177bdb) stores revealed artwork seeds in `seedOf(tokenId)` and calls this renderer for token images.

| On-screen value | On-chain read | Block height |
| --- | --- | ---: |
| `799 have a name` | `totalMinted() = 799` | 26,075,124 |
| `SWARM PEPE #1` | Token ID 1, confirmed by `ownerOf(1)` | 26,075,124 |
| `0x52ea578f6e9ffcba41d9866c6c88b49ab65df085769b43187fc495e4cbf34b07` | `seedOf(1)` | 26,075,124 |

The final card's contract address is the SwarmPepe address. At the same block, `MAX_SUPPLY()` returned 5,000. Of the 799 minted token IDs, 785 had nonzero revealed seeds and 14 had not yet been revealed.

## Ghost frame seeds

The complete ordered list of **320 ghost seeds** is [data/ghost_seeds.txt](data/ghost_seeds.txt). The initial still uses line 1; the accelerating single-image sequence uses lines 2–80; the 240-cell grid uses lines 81–320. Each SVG is the decoded return value of a separate `eth_call` to `PixelArt.renderSVG(seed)` at block 26,075,124. All 320 SVGs rasterize to distinct pixel images. None of their seeds matched any of the 799 `seedOf(tokenId)` results at that block. The exact SVG call returns and all 799 token-seed results are saved in [data/chain_calls.json.gz](data/chain_calls.json.gz), allowing that comparison without network access.

The video rasterizes the contract's SVG rectangles at their native 24 × 24 resolution and scales only by whole-number nearest-neighbour replication. Text and the near-black background are compositing elements; all depicted Pepes come from recorded contract calls.

## Rebuild and limits

Run `python3 src/build.py` with FFmpeg and its `drawtext` filter installed to rebuild the MP4 from the saved calls, without network access. `python3 src/capture.py` refreshes the on-chain capture at the pinned block using `curl` and a mainnet RPC. No Python packages were installed for this work.

The ownership comparison is a snapshot at block 26,075,124. Later mints and reveals may change the collection, while the video deliberately keeps its on-screen count fixed to the documented block. The 320 ghosts are samples of the renderer's much larger seed space. The clip uses no voice or external music.
