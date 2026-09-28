#!/usr/bin/env python3
"""Build Ghosts offline from the saved eth_call results. Standard library only."""

import array
import bisect
import gzip
import hashlib
import json
import math
import pathlib
import subprocess
import wave
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "data/chain_calls.json.gz"
OUT = ROOT / "artifacts/video.mp4"
SCRATCH = ROOT / "test/scratch"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
WIDTH, HEIGHT, FPS, DURATION = 1280, 720, 25, 25
BG = (4, 7, 6)


def png_pixels_from_chain_svg(svg):
    """Rasterize literal 24x24 SVG rects. No replacement artwork is drawn."""
    root = ET.fromstring(svg)
    if root.attrib.get("viewBox") != "0 0 24 24":
        raise ValueError("Unexpected contract SVG viewBox")
    pixels = bytearray(24 * 24 * 3)
    for child in root:
        if child.tag.rsplit("}", 1)[-1] != "rect":
            raise ValueError("Unexpected SVG element")
        x = int(child.attrib["x"])
        y = int(child.attrib["y"])
        w = int(child.attrib["width"])
        h = int(child.attrib["height"])
        color = bytes.fromhex(child.attrib["fill"].removeprefix("#"))
        if not (0 <= x < 24 and 0 <= y < 24 and 0 < w <= 24 - x and 0 < h <= 24 - y):
            raise ValueError("SVG rectangle outside pixel canvas")
        for row in range(y, y + h):
            start = (row * 24 + x) * 3
            pixels[start:start + w * 3] = color * w
    return bytes(pixels)


def upscale_nearest(pixels, scale):
    side = 24 * scale
    rows = []
    for y in range(24):
        row = b"".join(pixels[(y * 24 + x) * 3:(y * 24 + x + 1) * 3] * scale for x in range(24))
        rows.extend([row] * scale)
    return (side, b"".join(rows))


def blit(frame, sprite, x, y):
    side, data = sprite
    for row in range(side):
        start = ((y + row) * WIDTH + x) * 3
        frame[start:start + side * 3] = data[row * side * 3:(row + 1) * side * 3]


def replacement_times():
    # Cumulative rate from 2/s to about 22/s across 3..12 seconds.
    def cumulative(elapsed):
        return 2 * elapsed + (62 / 3) * elapsed ** 3 / 81
    times = [3.0]
    for event in range(1, 79):
        lo, hi = 0.0, 9.0
        for _ in range(40):
            mid = (lo + hi) / 2
            if cumulative(mid) < event:
                lo = mid
            else:
                hi = mid
        times.append(3 + (lo + hi) / 2)
    return times


def grid_order():
    cells = [(col, row) for row in range(12) for col in range(20)]
    cells.sort(key=lambda cell: ((cell[0] - 9.5) ** 2 + (cell[1] - 5.5) ** 2,
                                 hashlib.sha256(f"{cell[0]},{cell[1]}".encode()).digest()))
    return cells


def write_audio(ticks):
    # Original synthesized dry clicks, at low level. Initial 0..3s is silent.
    rate = 48000
    samples = array.array("h", [0]) * (DURATION * rate)
    for t in ticks:
        offset = int(t * rate)
        length = int(0.022 * rate)
        for i in range(length):
            p = offset + i
            if p >= len(samples):
                break
            envelope = math.exp(-i / (rate * 0.004))
            click = math.sin(2 * math.pi * (730 + 90 * i / length) * i / rate)
            samples[p] = max(-32768, min(32767, samples[p] + int(620 * envelope * click)))
    path = SCRATCH / "clicks.wav"
    with wave.open(str(path), "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(rate)
        file.writeframes(samples.tobytes())
    return path


def drawtext_file(name, content):
    path = SCRATCH / name
    path.write_text(content, encoding="utf-8")
    return path


def text_filter(path, size, color, x, y, start, end):
    return (f"drawtext=fontfile={FONT}:textfile={path}:fontsize={size}:"
            f"fontcolor={color}:x={x}:y={y}:enable='gte(t,{start})*lt(t,{end})'")


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(CAPTURE, "rt", encoding="utf-8") as file:
        capture = json.load(file)
    if len(capture["ghosts"]) != 320:
        raise ValueError("Need exactly 320 recorded ghost calls")
    ghost_pixels = [png_pixels_from_chain_svg(item["svg"]) for item in capture["ghosts"]]
    if len(set(hashlib.sha256(p).digest() for p in ghost_pixels)) != 320:
        raise ValueError("Ghosts must look distinct")
    real_pixels = png_pixels_from_chain_svg(capture["real_token"]["svg"])
    large = [upscale_nearest(pixels, 20) for pixels in ghost_pixels[:80]]
    small = [upscale_nearest(pixels, 2) for pixels in ghost_pixels[80:]]
    real_small = upscale_nearest(real_pixels, 2)
    real_large = upscale_nearest(real_pixels, 20)
    events = replacement_times()
    order = grid_order()
    center_cell = min(range(240), key=lambda i: abs(order[i][0] - 9) + abs(order[i][1] - 5))

    ticks = events + [12 + (i / 240) * 4 for i in range(0, 240, 6)]
    ticks += [16.8 + (i / 240) * 1.7 for i in range(0, 240, 10)]
    audio = write_audio(ticks)
    token = capture["real_token"]
    seed = token["seed"]
    token_title = drawtext_file("token_title.txt", f"SWARM PEPE #{token['id']}")
    seed_label = drawtext_file("seed_label.txt", "SEED")
    seed_first = drawtext_file("seed_first.txt", seed[:34])
    seed_second = drawtext_file("seed_second.txt", seed[34:])
    end_first = drawtext_file("end_first.txt", "the contract can draw all of them")
    end_second = drawtext_file("end_second.txt", f"{capture['total_minted']} have a name")
    end_address = drawtext_file("end_address.txt", capture["nft"])
    credit = drawtext_file("credit.txt", "generated by $IMD swarm")
    filters = [
        text_filter(token_title, 30, "white", 700, 250, 18.5, 21),
        text_filter(seed_label, 17, "0x8c9a91", 700, 327, 18.7, 21),
        text_filter(seed_first, 18, "white", 700, 362, 18.7, 21),
        text_filter(seed_second, 18, "white", 700, 388, 18.7, 21),
        text_filter(end_first, 33, "white", "(w-text_w)/2", 268, 21.2, 25),
        text_filter(end_second, 33, "white", "(w-text_w)/2", 331, 22.4, 25),
        text_filter(end_address, 20, "0xa5aea7", "(w-text_w)/2", 464, 23.35, 25),
        text_filter(credit, 14, "0x8c9a91", 20, 681, 24.3, 25),
    ]
    command = [
        "ffmpeg", "-hide_banner", "-y", "-f", "rawvideo", "-pixel_format", "rgb24",
        "-video_size", f"{WIDTH}x{HEIGHT}", "-framerate", str(FPS), "-i", "pipe:0",
        "-i", str(audio), "-vf", ",".join(filters),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-t", str(DURATION), str(OUT),
    ]
    with (SCRATCH / "ffmpeg.log").open("wb") as log:
        ffmpeg = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=log)
        try:
            for frame_index in range(DURATION * FPS):
                t = frame_index / FPS
                frame = bytearray(bytes(BG) * (WIDTH * HEIGHT))
                if t < 12:
                    index = 0 if t < 3 else min(79, bisect.bisect_right(events, t))
                    blit(frame, large[index], 400, 120)
                elif t < 16:
                    visible = min(240, 12 + int((t - 12) * 57))
                    for i in range(visible):
                        col, row = order[i]
                        blit(frame, small[i], 40 + col * 60 + 6, row * 60 + 6)
                elif t < 16.8:
                    for i, (col, row) in enumerate(order):
                        blit(frame, small[i], 40 + col * 60 + 6, row * 60 + 6)
                elif t < 18.5:
                    remaining = max(0, math.ceil(240 * (18.5 - t) / 1.7))
                    for i in range(remaining):
                        if i == center_cell:
                            continue
                        col, row = order[i]
                        blit(frame, small[i], 40 + col * 60 + 6, row * 60 + 6)
                    col, row = order[center_cell]
                    blit(frame, real_small, 40 + col * 60 + 6, row * 60 + 6)
                elif t < 21:
                    blit(frame, real_large, 160, 120)
                ffmpeg.stdin.write(frame)
                if frame_index % 125 == 0:
                    print(f"frame {frame_index}/{DURATION * FPS}", flush=True)
        finally:
            ffmpeg.stdin.close()
        status = ffmpeg.wait()
    if status:
        raise RuntimeError(f"ffmpeg failed ({status}); see {SCRATCH / 'ffmpeg.log'}")
    print(OUT, OUT.stat().st_size, "bytes", flush=True)


if __name__ == "__main__":
    main()
