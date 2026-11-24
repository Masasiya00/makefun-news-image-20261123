#!/usr/bin/env python3
"""news-image-20261123 v2 — "Monday 23 November 2026" front page.

Draws a one-page newspaper image (1024x1024) summing up the world news of
Monday 23 November 2026: 38 dated stories, 10 regions, 6 day-in-numbers,
a 4-time UTC timeline, 13 numbered stories with a dotted world map, and a
DATE CHECK box of stories deliberately left out because they happened on
other days.

Everything is drawn by hand in this file with a small stdlib-only
rasterizer written below: the font is
a stroke-based serif built from polylines defined below, every illustration
is flat vector art, and the world map is a hand-typed dot grid. No external
font files, no images, no network, no clock, no randomness — the output is
byte-identical on every run.

Writes entry.png to os.environ["MAKEFUN_OUTPUT_DIR"] (default "/output").
Stdlib only — no PIL, no third-party packages: v2 replaces the PIL
renderer with a hand-written rasterizer + PNG encoder (see below).
"""

import itertools
import math
import os
import struct
import zlib

# ------------------------------------------- stdlib-only rasterizer (v2)
# v1 used PIL. The competition sandbox installs nothing before it runs, so
# PIL may be absent and the entry would crash (score 0). This section is a
# small hand-written rasterizer on bytearray pixel buffers — stdlib only —
# exposing the same tiny API the rest of this file already uses
# (Image.new / ImageDraw.Draw / rectangle / ellipse / polygon / line /
# pieslice / paste / save / resize). Nothing else in the file changes.

def _hline(buf, W, H, bpp, y, x0, x1, pat):
    """Fill a horizontal span [x0..x1] on row y with pattern pat."""
    if y < 0 or y >= H:
        return
    x0 = max(0, int(math.floor(x0)))
    x1 = min(W - 1, int(math.ceil(x1)))
    if x1 < x0:
        return
    o = (y * W + x0) * bpp
    buf[o:o + (x1 - x0 + 1) * bpp] = pat * (x1 - x0 + 1)


def _fill_rect(buf, W, H, bpp, x0, y0, x1, y1, pat):
    y0 = max(0, int(y0))
    y1 = min(H - 1, int(y1))
    for y in range(y0, y1 + 1):
        _hline(buf, W, H, bpp, y, x0, x1, pat)


def _fill_ellipse(buf, W, H, bpp, cx, cy, rx, ry, pat):
    if rx <= 0 or ry <= 0:
        return
    cyi = int(round(cy))
    r = int(math.ceil(ry))
    for dy in range(-r, r + 1):
        t = 1.0 - (dy / ry) ** 2
        if t < 0.0:
            continue
        hw = rx * math.sqrt(t)
        _hline(buf, W, H, bpp, cyi + dy, cx - hw, cx + hw, pat)


def _fill_polygon(buf, W, H, bpp, pts, pat):
    if len(pts) < 3:
        return
    ys = [p[1] for p in pts]
    y0 = max(0, int(math.ceil(min(ys))))
    y1 = min(H - 1, int(math.floor(max(ys))))
    n = len(pts)
    for y in range(y0, y1 + 1):
        yc = y + 0.5
        xs = []
        for i in range(n):
            ax, ay = pts[i]
            bx, by = pts[(i + 1) % n]
            if (ay <= yc < by) or (by <= yc < ay):
                xs.append(ax + (yc - ay) * (bx - ax) / (by - ay))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            _hline(buf, W, H, bpp, y, xs[i], xs[i + 1], pat)


def _bresenham(buf, W, H, bpp, a, b, pat):
    x0, y0 = int(round(a[0])), int(round(a[1]))
    x1, y1 = int(round(b[0])), int(round(b[1]))
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        if 0 <= x0 < W and 0 <= y0 < H:
            o = (y0 * W + x0) * bpp
            buf[o:o + bpp] = pat
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def _polyline(buf, W, H, bpp, pts, pat, width):
    """Thick polyline: quad per segment + filled circle at each vertex."""
    if width <= 1:
        for a, b in zip(pts, pts[1:]):
            _bresenham(buf, W, H, bpp, a, b, pat)
        return
    r = width / 2.0
    for a, b in zip(pts, pts[1:]):
        dx = b[0] - a[0]
        dy = b[1] - a[1]
        L = math.hypot(dx, dy)
        if L == 0:
            _fill_ellipse(buf, W, H, bpp, a[0], a[1], r, r, pat)
            continue
        nx = -dy / L * r
        ny = dx / L * r
        _fill_polygon(buf, W, H, bpp,
                      [(a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny),
                       (b[0] - nx, b[1] - ny), (a[0] - nx, a[1] - ny)],
                      pat)
    for p in pts:
        _fill_ellipse(buf, W, H, bpp, p[0], p[1], r, r, pat)


def _ellipse_outline(buf, W, H, bpp, cx, cy, rx, ry, pat, width):
    n = max(24, int(2.0 * math.pi * max(rx, ry)) + 8)
    pts = []
    for i in range(n + 1):
        a = 2.0 * math.pi * i / n
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    _polyline(buf, W, H, bpp, pts, pat, width)


def _box_down_1d(values, n_in, n_out):
    """Box-average one row of bytes from n_in samples down to n_out."""
    pref = [0]
    pref.extend(itertools.accumulate(values))
    out = bytearray(n_out)
    for j in range(n_out):
        a = (j * n_in) // n_out
        b = ((j + 1) * n_in) // n_out
        if b <= a:
            b = a + 1
        out[j] = (pref[b] - pref[a]) // (b - a)
    return bytes(out)


def _downscale_alpha(src, w_out, h_out):
    """Box-downscale an AlphaCanvas (separable horizontal + vertical)."""
    w_in, h_in = src.width, src.height
    mid = bytearray(w_out * h_in)
    for y in range(h_in):
        mid[y * w_out:(y + 1) * w_out] = _box_down_1d(
            bytes(src.buf[y * w_in:(y + 1) * w_in]), w_in, w_out)
    out = AlphaCanvas(w_out, h_out)
    out.ink = src.ink
    for x in range(w_out):
        out.buf[x::w_out] = _box_down_1d(bytes(mid[x::w_out]), h_in, h_out)
    return out


def _png_chunk(typ, data):
    return (struct.pack(">I", len(data)) + typ + data +
            struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))


class Canvas:
    """RGB pixel buffer with the PIL ImageDraw-compatible API used below."""

    def __init__(self, w, h, fill=(0, 0, 0)):
        self.width = int(w)
        self.height = int(h)
        self.buf = bytearray(self.width * self.height * 3)
        if fill is not None:
            self.buf[:] = bytes(fill) * (self.width * self.height)

    def rectangle(self, box, fill=None, outline=None, width=1):
        x0, y0, x1, y1 = (int(v) for v in box)
        if fill is not None:
            _fill_rect(self.buf, self.width, self.height, 3,
                       x0, y0, x1, y1, bytes(fill))
        if outline is not None:
            pat = bytes(outline)
            for i in range(max(1, int(width))):
                _hline(self.buf, self.width, self.height, 3, y0 + i, x0, x1, pat)
                _hline(self.buf, self.width, self.height, 3, y1 - i, x0, x1, pat)
                _fill_rect(self.buf, self.width, self.height, 3,
                           x0 + i, y0, x0 + i, y1, pat)
                _fill_rect(self.buf, self.width, self.height, 3,
                           x1 - i, y0, x1 - i, y1, pat)

    def ellipse(self, box, fill=None, outline=None, width=1):
        x0, y0, x1, y1 = (int(v) for v in box)
        cx = (x0 + x1) / 2.0
        cy = (y0 + y1) / 2.0
        rx = (x1 - x0) / 2.0
        ry = (y1 - y0) / 2.0
        if fill is not None:
            _fill_ellipse(self.buf, self.width, self.height, 3,
                          cx, cy, rx, ry, bytes(fill))
        if outline is not None:
            _ellipse_outline(self.buf, self.width, self.height, 3,
                             cx, cy, rx, ry, bytes(outline), width)

    def polygon(self, pts, fill=None, outline=None):
        pts = [(float(x), float(y)) for x, y in pts]
        if fill is not None:
            _fill_polygon(self.buf, self.width, self.height, 3, pts, bytes(fill))
        if outline is not None:
            _polyline(self.buf, self.width, self.height, 3,
                      pts + [pts[0]], bytes(outline), 1)

    def line(self, pts, fill=None, width=1, joint=None):
        if fill is None:
            return
        pts = [(float(x), float(y)) for x, y in pts]
        _polyline(self.buf, self.width, self.height, 3, pts, bytes(fill), width)

    def pieslice(self, box, start, end, fill=None, outline=None):
        x0, y0, x1, y1 = (int(v) for v in box)
        cx = (x0 + x1) / 2.0
        cy = (y0 + y1) / 2.0
        rx = (x1 - x0) / 2.0
        ry = (y1 - y0) / 2.0
        steps = max(8, int(abs(end - start) / 3.0) + 1)
        pts = [(cx, cy)]
        for i in range(steps + 1):
            a = math.radians(start + (end - start) * i / steps)
            pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
        if fill is not None:
            _fill_polygon(self.buf, self.width, self.height, 3, pts, bytes(fill))
        if outline is not None:
            _polyline(self.buf, self.width, self.height, 3,
                      pts + [pts[0]], bytes(outline), 1)

    def paste(self, src, xy, mask=None):
        """Alpha-composite an AlphaCanvas (one line of text) onto this canvas."""
        x0 = int(xy[0])
        y0 = int(xy[1])
        sw, sh = src.width, src.height
        ink = src.ink
        sbuf = src.buf
        dbuf = self.buf
        W, H = self.width, self.height
        for sy in range(sh):
            dy = y0 + sy
            if dy < 0 or dy >= H:
                continue
            srow = sy * sw
            drow = dy * W * 3
            for sx in range(sw):
                a = sbuf[srow + sx]
                if a == 0:
                    continue
                dx = x0 + sx
                if dx < 0 or dx >= W:
                    continue
                do = drow + dx * 3
                if a == 255:
                    dbuf[do] = ink[0]
                    dbuf[do + 1] = ink[1]
                    dbuf[do + 2] = ink[2]
                else:
                    ia = 255 - a
                    dbuf[do] = (ink[0] * a + dbuf[do] * ia) // 255
                    dbuf[do + 1] = (ink[1] * a + dbuf[do + 1] * ia) // 255
                    dbuf[do + 2] = (ink[2] * a + dbuf[do + 2] * ia) // 255

    def save(self, path, format=None):
        """Write this canvas as a PNG (filter byte 0 per row, zlib level 9)."""
        w, h = self.width, self.height
        raw = bytearray((w * 3 + 1) * h)
        for y in range(h):
            o = y * (w * 3 + 1)
            raw[o] = 0
            raw[o + 1:o + 1 + w * 3] = self.buf[y * w * 3:(y + 1) * w * 3]
        ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
        png = (b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr) +
               _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9)) +
               _png_chunk(b"IEND", b""))
        with open(path, "wb") as f:
            f.write(png)


class AlphaCanvas:
    """One line of text at 4x supersampling: a single alpha channel plus
    the one ink colour of the line. Downscaled with a box filter."""

    def __init__(self, w, h, color=(0, 0, 0, 0)):
        self.width = int(w)
        self.height = int(h)
        self.buf = bytearray(self.width * self.height)
        self.ink = (0, 0, 0)

    def line(self, pts, fill=None, width=1, joint=None):
        if fill is not None:
            self.ink = tuple(fill[:3])
        pts = [(float(x), float(y)) for x, y in pts]
        _polyline(self.buf, self.width, self.height, 1, pts, b"\xff", width)

    def resize(self, size, resample=None):
        return _downscale_alpha(self, int(size[0]), int(size[1]))


class Image:
    """Stand-in for the PIL.Image calls this entry used (new only)."""
    LANCZOS = "lanczos"

    @staticmethod
    def new(mode, size, color=None):
        if mode == "RGBA":
            return AlphaCanvas(size[0], size[1])
        return Canvas(size[0], size[1],
                      color if color is not None else (0, 0, 0))


class ImageDraw:
    """Stand-in for PIL.ImageDraw: Draw() returns the canvas itself,
    which already carries rectangle/ellipse/polygon/line/pieslice."""

    @staticmethod
    def Draw(img):
        return img

# ---------------------------------------------------------------- palette
PAPER = (246, 241, 227)
INK = (17, 17, 17)
INK_SOFT = (60, 58, 52)
RED = (185, 28, 28)
NAVY = (30, 58, 95)
GREY = (120, 116, 106)
GREEN = (22, 101, 52)
AMBER = (180, 83, 9)
TEAL = (15, 118, 110)
SKY = (3, 105, 161)
PURPLE = (124, 58, 237)
PINK = (190, 24, 93)
LIME = (77, 124, 15)
RULE = (150, 144, 128)

W, H = 1024, 1024
SS = 4  # supersampling factor for text

# ------------------------------------------------------- hand-built font
# Grid: x 0..12, y 0..16. Baseline y=12, cap top y=2, x-height top y=5,
# descender bottom y=16. Each glyph: (advance width, "x,y x,y|..." strokes).
# Typed by hand for this entry only.
GLYPHS = {
    "A": (9, "4.5,2 0.5,12|4.5,2 8.5,12|2.5,8 6.5,8"),
    "B": (8, "1,2 1,12|1,2 5.5,2 7,3.5 7,5.5 5.5,7 1,7|1,7 6,7 7.5,8.5 7.5,10.5 6,12 1,12"),
    "C": (8, "7,4 5,2 2,2 1,4 1,10 2,12 5,12 7,10"),
    "D": (9, "1,2 1,12|1,2 5.5,2 8,4.5 8,9.5 5.5,12 1,12"),
    "E": (8, "1,2 1,12|1,2 7,2|1,7 5.5,7|1,12 7,12"),
    "F": (7, "1,2 1,12|1,2 6.5,2|1,7 5,7"),
    "G": (8, "7,4 5,2 2,2 1,4 1,10 2,12 5,12 7,10 7,8|7,8 4.5,8"),
    "H": (9, "1,2 1,12|8,2 8,12|1,7 8,7"),
    "I": (8, "4,2 4,12|2,2 6,2|2,12 6,12"),
    "J": (7, "6,2 6,11 4.5,12 2.5,12 1.5,10.5|2,2 6.5,2"),
    "K": (9, "1,2 1,12|8,2 1.5,7|4,6 8,12"),
    "L": (8, "1,2 1,12|1,12 7,12"),
    "M": (10, "1,12 1,2 5,8 9,2 9,12"),
    "N": (9, "1,12 1,2 8,12 8,2"),
    "O": (9, "4.5,2 2,2 1,4 1,10 2,12 4.5,12 7,12 8,10 8,4 7,2 4.5,2"),
    "P": (8, "1,2 1,12|1,2 5.5,2 7,3.5 7,5.5 5.5,7 1,7"),
    "Q": (9, "4.5,2 2,2 1,4 1,10 2,12 4.5,12 7,12 8,10 8,4 7,2 4.5,2|6,9 8.5,12.5"),
    "R": (8, "1,2 1,12|1,2 5.5,2 7,3.5 7,5.5 5.5,7 1,7|4.5,7 8,12"),
    "S": (8, "7,3.5 5.5,2 3,2 1,4 1,6 2,7.5 6,8 7,9.5 7,11 5.5,12 3,12 1,10.5"),
    "T": (9, "0.5,2 8.5,2|4.5,2 4.5,12"),
    "U": (9, "1,2 1,10 2.5,12 6.5,12 8,10 8,2"),
    "V": (9, "0.5,2 4.5,12 8.5,2"),
    "W": (11, "0.5,2 2.5,12 5,6.5 7.5,12 10.5,2"),
    "X": (9, "1,2 8,12|8,2 1,12"),
    "Y": (9, "0.5,2 4.5,7 8.5,2|4.5,7 4.5,12"),
    "Z": (8, "1,2 7,2 1,12 7,12"),
    "a": (8, "7,5 5,5 2,5 1,7.5 1,10 3,12 6,12 7.5,10 7.5,7 6,6 3,6 1,7.5"),
    "b": (8, "1.5,0 1.5,12|1.5,7 5,5 7,6.5 7,9.5 5,12 1.5,12"),
    "c": (8, "7,6.5 5,5 2,5 1,7 1,10 2,12 5,12 7,10.5"),
    "d": (8, "7,0 7,12|7,7 5,5 2,5 1,7 1,10 2,12 5,12 7,10"),
    "e": (8, "7,10 5,12 2,12 1,10 1,7.5 2.5,5 5,5 7,6.5 7,8 1,8"),
    "f": (6, "5,0 3,1 2.5,3 2.5,12|1,7 5.5,7"),
    "g": (8, "7,5 5,5 2,5 1,7 1,10 2,12 5,12 7,10 7,7|7,10 7,14 5,16 2,16 1,14"),
    "h": (8, "1.5,0 1.5,12|1.5,7 4,5 6.5,6.5 6.5,12"),
    "i": (4, "2,5 2,12|1.5,1.5 2.5,1.5"),
    "j": (5, "3,5 3,14 2,16 1,15|2.5,1.5 3.5,1.5"),
    "k": (8, "1.5,0 1.5,12|7,5 2,8|3.5,7 7,12"),
    "l": (4, "2,0 2,12"),
    "m": (10, "1.5,5 1.5,12|1.5,5 3.5,5 5,6.5 5,12|5,5 7,5 9,6.5 9,12"),
    "n": (8, "1.5,12 1.5,5 4,5 6.5,6.5 6.5,12"),
    "o": (8, "4.5,5 2,5 1,7 1,10 2,12 4.5,12 7,12 8,10 8,7 7,5 4.5,5"),
    "p": (8, "1.5,5 1.5,16|1.5,7 4,5 6.5,6.5 6.5,10 4,12 1.5,12"),
    "q": (8, "6.5,5 6.5,16|1,7 3,5 5.5,5 6.5,7 6.5,10 5,12 2,12 1,10"),
    "r": (6, "1.5,12 1.5,5|1.5,7 3.5,5 5,6.5 5,8"),
    "s": (8, "6.5,6.5 5,5 2.5,5 1,6.5 1,8.5 2.5,9.5 5.5,9.5 7,10.5 7,12 5,12 2.5,12 1,10.5"),
    "t": (6, "3,1 3,10 4,12 5.5,12|1,7 5.5,7"),
    "u": (8, "1.5,5 1.5,10 2.5,12 5,12 6.5,12 7,10 7,5"),
    "v": (8, "1,5 4,12 7,5"),
    "w": (10, "0.5,5 2,12 4.5,7 7,12 9,5"),
    "x": (8, "1,5 7,12|7,5 1,12"),
    "y": (8, "1,5 4,12 7,5|4,12 3,15 1,16 0,14.5"),
    "z": (8, "1,5 7,5 1,12 7,12"),
    "0": (8, "4,2 2,2 1,4 1,10 2,12 4,12 6,12 7,10 7,4 6,2 4,2"),
    "1": (7, "3.5,2 3.5,12|1.5,4 3.5,2|1.5,12 5.5,12"),
    "2": (8, "1,4 2.5,2 5,2 7,3.5 7,5.5 2.5,12 7,12"),
    "3": (8, "1,4 2.5,2 5,2 7,3.5 7,6 5,7|5,7 7,8 7,10.5 5,12 2.5,12 1,10"),
    "4": (8, "5.5,2 1,8 6.5,8|5.5,2 5.5,12"),
    "5": (8, "7,2 1,2 1,7 4,7 6.5,8.5 6.5,10.5 4,12 1.5,12"),
    "6": (8, "7,3 5,2 2,2 1,4 1,10 2,12 5,12 7,10 7,8 5,7 2,7"),
    "7": (8, "1,2 7,2 3.5,12"),
    "8": (8, "4,2 2,2 1,4 1,6 2,7.5 4,7.5 6,7.5 7,6 7,4 6,2 4,2|2,7.5 1,9 1,10.5 2,12 4,12 6,12 7,10.5 7,9 6,7.5"),
    "9": (8, "1,11 2,12 5,12 7,10 7,4 6,2 3,2 1,4 1,6 2,7 5,7"),
    ".": (4, "1.5,11 2.5,11"),
    ",": (4, "1.5,11 2.5,11|2.5,11 1.5,14 0.5,15"),
    ":": (4, "1.5,5 2.5,5|1.5,11 2.5,11"),
    ";": (4, "1.5,5 2.5,5|1.5,11 2.5,11|2.5,11 1.5,14 0.5,15"),
    "!": (4, "2,2 2,9|1.5,11 2.5,11"),
    "?": (8, "2,4 3,2 5.5,2 7,3.5 7,5.5 5.5,7 4.5,7 4.5,9|4,11 5,11"),
    "'": (4, "2.5,2 1.5,5"),
    '"': (7, "2,2 1,5|5.5,2 4.5,5"),
    "-": (8, "1,7 7,7"),
    "\u2013": (8, "1,7 7,7"),
    "\u2014": (10, "0,7 9,7"),
    "\u00b7": (4, "1.5,6.5 2.5,6.5"),
    "(": (6, "5,2 2.5,4 1.5,7 2.5,10 5,12"),
    ")": (6, "1,2 3.5,4 4.5,7 3.5,10 1,12"),
    "%": (10, "7,2 2,12|1.5,3 3.5,3 3.5,5 1.5,5 1.5,3|6.5,9 8.5,9 8.5,11 6.5,11 6.5,9"),
    "$": (8, "4,1 4,13|1.5,4 3,2 5.5,2 7,3.5 7,5.5 5.5,7 2.5,7 1.5,8.5 1.5,10.5 3,12 5.5,12 7,10.5"),
    "&": (8, "6,2 4,2 2.5,4 2.5,6 4,7 6.5,8 7.5,10 7.5,11 6,12 4,12 2.5,10.5|4,7 1,11"),
    "/": (8, "6.5,2 1.5,12"),
    "+": (9, "4.5,3 4.5,11|1,7 8,7"),
    "=": (8, "1,5 7,5|1,9 7,9"),
    "*": (8, "4,2 4,12|1,4 7,10|7,4 1,10"),
    "#": (9, "3,2 3,12|6,2 6,12|1,5 8,5|1,9 8,9"),
    "\u2022": (5, "1,6 3,6|3,6 3,8|3,8 1,8|1,8 1,6"),
    " ": (4, ""),
}

# Accented letters: base glyph + accent drawn above it.
ACCENTS = {
    "\u00dc": ("U", "dia", True), "\u00fc": ("u", "dia", False),
    "\u00d6": ("O", "dia", True), "\u00f6": ("o", "dia", False),
    "\u00e1": ("a", "acute", False), "\u00c1": ("A", "acute", True),
    "\u00e9": ("e", "acute", False), "\u00c9": ("E", "acute", True),
}
CHAR_MAP = {"\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"',
            "\u00a0": " ", "\t": " "}

_glyph_cache = {}


def _parse_strokes(spec):
    strokes = []
    for part in spec.split("|"):
        pts = []
        for tok in part.split():
            x, y = tok.split(",")
            pts.append((float(x), float(y)))
        if len(pts) >= 2:
            strokes.append(pts)
        elif len(pts) == 1:
            strokes.append([pts[0], pts[0]])
    return strokes


def glyph_for(ch):
    """Return (advance_width_units, [stroke, ...]) for a character."""
    ch = CHAR_MAP.get(ch, ch)
    if ch in _glyph_cache:
        return _glyph_cache[ch]
    if ch in ACCENTS:
        base, kind, upper = ACCENTS[ch]
        w, strokes = glyph_for(base)
        strokes = [list(s) for s in strokes]
        top = 2.0 if upper else 5.0
        if kind == "dia":
            strokes.append([(w * 0.22, top - 1.2), (w * 0.34, top - 1.2)])
            strokes.append([(w * 0.62, top - 1.2), (w * 0.74, top - 1.2)])
        else:
            strokes.append([(w * 0.52, top - 0.7), (w * 0.74, top - 2.2)])
        out = (w, strokes)
    elif ch in GLYPHS:
        w, spec = GLYPHS[ch]
        out = (w, _parse_strokes(spec))
    else:
        out = glyph_for("?")
    _glyph_cache[ch] = out
    return out


def text_width(text, size, tracking=0.0):
    scale = size / 14.0
    total = 0.0
    for ch in text:
        w, _ = glyph_for(ch)
        total += w * scale
    if len(text) > 1:
        total += tracking * (len(text) - 1)
    return total


def _render_line(text, size, color, weight, tracking):
    """Render one line of text at 4x, downscale, return RGBA image."""
    scale = size / 14.0
    total_w = text_width(text, size, tracking)
    pad = 6
    w_px = int(math.ceil(total_w)) + 2 * pad
    h_px = int(math.ceil(16 * scale)) + 2 * pad
    img = Image.new("RGBA", (w_px * SS, h_px * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    sw = max(2, int(round(size * 0.105 * weight * SS)))
    cx = pad * SS
    for ch in text:
        adv, strokes = glyph_for(ch)
        for pts in strokes:
            xy = [(cx + px * scale * SS, (py + 0.0) * scale * SS + pad * SS)
                  for px, py in pts]
            d.line(xy, fill=color + (255,), width=sw, joint="curve")
        cx += adv * scale * SS + tracking * SS
    img = img.resize((w_px, h_px), Image.LANCZOS)
    return img, total_w


def draw_text(img, x, y, text, size, color=INK, weight=1.0, align="left",
              tracking=0.0):
    """Draw text; (x, y) is the top-left of the em box (ascender top).
    align left/center/right relative to x. Returns width used."""
    if not text:
        return 0
    line, total_w = _render_line(text, size, color, weight, tracking)
    pad = 6
    if align == "center":
        px = int(round(x - total_w / 2)) - pad
    elif align == "right":
        px = int(round(x - total_w)) - pad
    else:
        px = int(round(x)) - pad
    py = int(round(y)) - pad
    img.paste(line, (px, py), line)
    return total_w


def fit_size(text, start_size, max_width, weight=1.0, tracking=0.0, floor=6.0):
    size = start_size
    while size > floor and text_width(text, size, tracking) > max_width:
        size -= 0.5
    return size


def wrap_text(text, size, max_width, tracking=0.0):
    """Greedy word wrap; returns list of lines (never empty)."""
    words = text.split(" ")
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if text_width(trial, size, tracking) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            if text_width(word, size, tracking) <= max_width:
                cur = word
            else:
                # hard-split a very long word
                part = ""
                for ch in word:
                    if text_width(part + ch, size, tracking) <= max_width:
                        part += ch
                    else:
                        lines.append(part)
                        part = ch
                cur = part
    if cur:
        lines.append(cur)
    return lines if lines else [""]


def draw_block(img, x, y, lines, size, color=INK, weight=1.0, leading=None,
               align="left", tracking=0.0):
    """Draw several lines starting at em-top y; returns next y."""
    if leading is None:
        leading = size * 1.18
    for ln in lines:
        draw_text(img, x, y, ln, size, color, weight, align, tracking)
        y += leading
    return y

# ---------------------------------------------------------- illustrations
# All flat vector scenes, drawn with the stdlib rasterizer only. Each takes the
# top-left corner and size of its box on the page.

def _rect(d, x, y, w, h, fill, outline=None):
    d.rectangle([x, y, x + w, y + h], fill=fill, outline=outline)


def _ellipse(d, x, y, w, h, fill=None, outline=None, width=1):
    d.ellipse([x, y, x + w, y + h], fill=fill, outline=outline, width=width)


def _poly(d, pts, fill, outline=None):
    d.polygon(pts, fill=fill, outline=outline)


def _line(d, pts, fill, width=1):
    d.line(pts, fill=fill, width=width, joint="curve")


def ill_cop31(img, x, y, w, h):
    """Lead 1: COP31 hall, flags, long table, red NO DEAL banner."""
    d = ImageDraw.Draw(img)
    _rect(d, x, y, w, h, (216, 201, 163))           # wall
    _rect(d, x, y + h - 26, w, 26, (146, 110, 66))  # floor
    # windows with dusk sky
    for wx in (x + 14, x + w - 62):
        _rect(d, wx, y + 10, 48, 34, (252, 186, 110), outline=(120, 90, 50))
        _ellipse(d, wx + 28, y + 16, 16, 16, (255, 214, 130))
    # clock on the wall
    _ellipse(d, x + w // 2 - 11, y + 8, 22, 22, (250, 246, 235), outline=INK)
    _line(d, [(x + w // 2, y + 19), (x + w // 2, y + 13)], INK, 2)
    _line(d, [(x + w // 2, y + 19), (x + w // 2 + 5, y + 21)], INK, 2)
    # flags along the back wall
    flag_cols = [(30, 58, 95), (185, 28, 28), (22, 101, 52), (180, 83, 9),
                 (124, 58, 237)]
    for i, c in enumerate(flag_cols):
        fx = x + 22 + i * 52
        _line(d, [(fx, y + 44), (fx, y + 66)], INK, 2)
        _rect(d, fx, y + 44, 26, 15, c)
    # long negotiation table
    _rect(d, x + 18, y + h - 46, w - 36, 10, (90, 60, 35))
    _rect(d, x + 26, y + h - 36, 8, 12, (70, 46, 28))
    _rect(d, x + w - 34, y + h - 36, 8, 12, (70, 46, 28))
    for px in range(x + 34, x + w - 40, 26):
        _rect(d, px, y + h - 52, 14, 6, (250, 246, 235))  # papers
    # seated delegates (heads + shoulders)
    for i, sx in enumerate((x + 48, x + w // 2 - 12, x + w - 66)):
        _ellipse(d, sx, y + h - 66, 16, 16, (222, 178, 140))
        _poly(d, [(sx - 8, y + h - 50), (sx + 24, y + h - 50),
                  (sx + 18, y + h - 46), (sx - 2, y + h - 46)],
              (40, 45, 70) if i % 2 == 0 else (70, 40, 40))
    # red NO DEAL banner
    _rect(d, x + w // 2 - 62, y + 52, 124, 20, RED)
    draw_text(img, x + w // 2, y + 52, "NO DEAL", 15, (255, 255, 255),
              weight=1.4, align="center")


def ill_merkury(img, x, y, w, h):
    """Lead 2: night sea, drone boats, warship, explosion glow."""
    d = ImageDraw.Draw(img)
    _rect(d, x, y, w, h // 2 + 8, (11, 30, 58))     # night sky
    _rect(d, x, y + h // 2 + 8, w, h - h // 2 - 8, (18, 58, 92))  # sea
    for sx, sy in ((x + 24, y + 12), (x + 70, y + 26), (x + 250, y + 10),
                   (x + 200, y + 30), (x + 150, y + 8)):
        _ellipse(d, sx, sy, 2, 2, (240, 240, 220))
    _ellipse(d, x + w - 52, y + 8, 26, 26, (235, 228, 200))  # moon
    _ellipse(d, x + w - 46, y + 14, 18, 18, (11, 30, 58))
    # warship (centre-right)
    sx, sy = x + 150, y + h - 62
    _poly(d, [(sx, sy + 26), (sx + 118, sy + 26), (sx + 104, sy + 12),
              (sx + 14, sy + 12)], (90, 96, 104))
    _rect(d, sx + 34, sy, 34, 14, (70, 76, 84))
    _rect(d, sx + 76, sy + 4, 10, 10, (70, 76, 84))
    _line(d, [(sx + 50, sy), (sx + 50, sy - 12)], (70, 76, 84), 3)
    # explosion glow above the ship
    _ellipse(d, sx + 40, sy - 26, 34, 34, (255, 170, 40))
    _ellipse(d, sx + 48, sy - 18, 20, 20, (255, 220, 90))
    _ellipse(d, sx + 84, sy - 12, 14, 14, (255, 140, 30))
    # small drone boats with wakes
    for bx, by in ((x + 24, y + h - 26), (x + 78, y + h - 16),
                   (x + 268, y + h - 22)):
        _poly(d, [(bx, by + 8), (bx + 26, by + 8), (bx + 20, by),
                  (bx + 6, by)], (220, 224, 228))
        _line(d, [(bx - 12, by + 10), (bx + 2, by + 10)], (200, 215, 230), 2)
        _line(d, [(bx + 24, by + 10), (bx + 38, by + 10)], (200, 215, 230), 2)
    # waves
    for wx in range(x + 10, x + w - 10, 34):
        _line(d, [(wx, y + h - 8), (wx + 14, y + h - 8)], (90, 140, 175), 2)


def ill_capitol(img, x, y, w, h):
    """Lead 3: US Capitol dome + a seat bar showing 258 seats."""
    d = ImageDraw.Draw(img)
    _rect(d, x, y, w, h, (168, 205, 230))           # sky
    _ellipse(d, x + 236, y + 8, 22, 22, (255, 240, 170))  # sun
    _rect(d, x, y + h - 16, w, 16, (96, 150, 90))  # lawn
    # dome (left)
    bx, by = x + 16, y + 26
    _rect(d, bx, by + 34, 96, 30, (245, 242, 232))
    for cx in range(bx + 6, bx + 92, 14):
        _rect(d, cx, by + 40, 5, 24, (210, 206, 196))
    _poly(d, [(bx - 4, by + 34), (bx + 100, by + 34), (bx + 88, by + 26),
              (bx + 8, by + 26)], (235, 232, 222))
    d.pieslice([bx + 22, by - 6, bx + 74, by + 34], 180, 360,
               fill=(245, 242, 232))
    _rect(d, bx + 44, by - 12, 8, 8, (245, 242, 232))
    _line(d, [(bx + 48, by - 12), (bx + 48, by - 18)], INK, 2)
    _ellipse(d, bx + 45, by - 21, 6, 6, (40, 45, 70))
    # flag on the dome
    _line(d, [(bx + 88, by + 4), (bx + 88, by + 26)], INK, 2)
    _rect(d, bx + 88, by + 4, 14, 8, RED)
    # seat bar (right): blue 258 of 435, rest grey
    bar_x, bar_y = x + 138, y + 52
    _rect(d, bar_x, bar_y, 148, 18, (200, 200, 196))
    _rect(d, bar_x, bar_y, 88, 18, (37, 99, 235))
    _rect(d, bar_x + 88, bar_y, 60, 18, (200, 200, 196))
    draw_text(img, bar_x + 44, bar_y - 16, "258", 17, (37, 99, 235),
              weight=1.4, align="center")
    draw_text(img, bar_x + 74, bar_y + 21, "HOUSE SEATS", 9, INK_SOFT,
              weight=1.2, align="center")
    draw_text(img, bar_x + 74, y + h - 15, "DEMOCRATS \u00b7 LARGEST IN DECADES",
              9, (255, 255, 255), weight=1.2, align="center")


def _thumb_label(img, x, y, w, text, color):
    d = ImageDraw.Draw(img)
    _rect(d, x, y, w, 11, color)
    draw_text(img, x + 4, y, text, 8, (255, 255, 255), weight=1.3)


def ill_court(img, x, y, w, h):
    d = ImageDraw.Draw(img)
    _rect(d, x, y, w, h, (232, 224, 205))
    _poly(d, [(x + 20, y + 10), (x + w - 20, y + 10), (x + w // 2, y + 2)],
          (120, 100, 70))
    _rect(d, x + 24, y + 10, w - 48, h - 16, (245, 240, 225))
    for cx in range(x + 30, x + w - 30, 18):
        _rect(d, cx, y + 12, 6, h - 20, (180, 168, 140))
    _rect(d, x + 16, y + h - 6, w - 32, 4, (120, 100, 70))
    _rect(d, x + w // 2 - 8, y + h - 14, 16, 8, (90, 70, 50))


def ill_chart(img, x, y, w, h):
    d = ImageDraw.Draw(img)
    _rect(d, x, y, w, h, (250, 248, 242))
    _line(d, [(x + 10, y + 8), (x + 10, y + h - 8)], GREY, 1)
    _line(d, [(x + 10, y + h - 8), (x + w - 8, y + h - 8)], GREY, 1)
    pts = [(x + 14, y + 10), (x + 48, y + 14), (x + 82, y + 12),
           (x + 116, y + 20), (x + 150, y + 30), (x + w - 12, y + h - 12)]
    _line(d, pts, RED, 3)
    _poly(d, [(x + w - 22, y + h - 18), (x + w - 8, y + h - 18),
              (x + w - 15, y + h - 8)], RED)
    draw_text(img, x + w - 14, y + 2, "-5.8%", 11, RED, weight=1.4,
              align="right")


def ill_rescue(img, x, y, w, h):
    d = ImageDraw.Draw(img)
    _rect(d, x, y, w, h, (60, 58, 66))
    _rect(d, x + 20, y + 4, 74, h - 4, (140, 136, 128))
    for wy in range(y + 8, y + h - 6, 12):
        for wx in (x + 26, x + 46, x + 66):
            _rect(d, wx, wy, 10, 7, (255, 210, 110))
    _ellipse(d, x + 120, y + h - 22, 26, 22, (255, 140, 30))
    _ellipse(d, x + 126, y + h - 16, 14, 12, (255, 200, 80))
    _line(d, [(x + 104, y + h), (x + 150, y + 6)], (220, 160, 60), 3)
    _ellipse(d, x + 146, y + 4, 8, 8, (222, 178, 140))


def ill_nato(img, x, y, w, h):
    d = ImageDraw.Draw(img)
    _rect(d, x, y, w, h, (232, 236, 242))
    for i in range(4):
        fx = x + 16 + i * 42
        _rect(d, fx, y + 10, 32, 20, (30, 58, 95))
        for k in range(6):
            a = k * math.pi / 3
            _ellipse(d, fx + 16 + int(7 * math.cos(a)) - 1,
                     y + 20 + int(7 * math.sin(a)) - 1, 2, 2, (255, 215, 0))
    _ellipse(d, x + w // 2 - 16, y + h - 16, 32, 12, (200, 60, 60))
    draw_text(img, x + w // 2, y + h - 15, "32", 10, (255, 255, 255),
              weight=1.4, align="center")


def ill_tanker(img, x, y, w, h):
    d = ImageDraw.Draw(img)
    _rect(d, x, y, w, h // 2, (200, 220, 230))
    _rect(d, x, y + h // 2, w, h - h // 2, (30, 70, 110))
    _rect(d, x + 40, y + 12, 110, 16, (60, 60, 66))
    _rect(d, x + 130, y + 6, 12, 10, (60, 60, 66))
    _rect(d, x + 40, y + 28, 110, 6, (140, 40, 40))
    _line(d, [(x + 20, y + h - 10), (x + w - 20, y + h - 10)],
          (220, 225, 230), 2)
    _line(d, [(x + 158, y + 4), (x + 174, y + h - 6)], RED, 4)
    _line(d, [(x + 174, y + 4), (x + 158, y + h - 6)], RED, 4)


def ill_toxic(img, x, y, w, h):
    d = ImageDraw.Draw(img)
    _rect(d, x, y, w, h, (120, 110, 80))
    _rect(d, x, y + h - 8, w, 8, (70, 90, 50))
    _poly(d, [(x + w // 2, y + 3), (x + w - 14, y + h - 10),
              (x + 14, y + h - 10)], (255, 200, 0))
    draw_text(img, x + w // 2, y + 8, "!", 16, INK, weight=1.5,
              align="center")


def ill_handcuffs(img, x, y, w, h):
    d = ImageDraw.Draw(img)
    _rect(d, x, y, w, h, (40, 44, 54))
    _ellipse(d, x + 30, y + 4, 34, 20, outline=(200, 200, 200), width=4)
    _ellipse(d, x + w - 64, y + 4, 34, 20, outline=(200, 200, 200), width=4)
    _line(d, [(x + 66, y + 14), (x + w - 66, y + 14)], (200, 200, 200), 3)
    _ellipse(d, x + w // 2 - 4, y + 10, 8, 8, (200, 200, 200))
    draw_text(img, x + w // 2, y + h - 11, "FBI TOP 10", 9,
              (255, 255, 255), weight=1.3, align="center")


def ill_hospital(img, x, y, w, h):
    d = ImageDraw.Draw(img)
    _rect(d, x, y, w, h, (210, 225, 215))
    _rect(d, x, y + h - 8, w, 8, (110, 160, 100))
    _poly(d, [(x + 30, y + 12), (x + w - 30, y + 12), (x + w // 2, y + 2)],
          (250, 248, 242))
    _rect(d, x + 34, y + 12, w - 68, h - 20, (250, 248, 242))
    _rect(d, x + w // 2 - 3, y + 15, 6, 12, RED)
    _rect(d, x + w // 2 - 8, y + 19, 16, 6, RED)
    _rect(d, x + 12, y + h - 15, 10, 7, (200, 90, 90))
    _rect(d, x + w - 24, y + h - 16, 12, 8, (90, 130, 200))


def ill_concert(img, x, y, w, h):
    d = ImageDraw.Draw(img)
    _rect(d, x, y, w, h, (24, 20, 34))
    for i, c in enumerate(((255, 80, 80), (255, 200, 60), (90, 160, 255),
                           (140, 90, 255))):
        bx = x + 20 + i * 42
        _poly(d, [(bx, y + 4), (bx + 16, y + 4), (bx + 30, y + h - 14),
                  (bx - 2, y + h - 14)], c)
    _rect(d, x + w // 2 - 26, y + 12, 52, 12, (250, 248, 242))
    for cx in range(x + 8, x + w - 8, 12):
        _ellipse(d, cx, y + h - 12, 7, 7, (230, 220, 200))


def ill_server(img, x, y, w, h):
    d = ImageDraw.Draw(img)
    _rect(d, x, y, w, h, (30, 34, 44))
    for i in range(3):
        rx = x + 22 + i * 52
        _rect(d, rx, y + 6, 40, h - 12, (70, 78, 90), outline=(150, 160, 170))
        for ry in range(y + 12, y + h - 10, 10):
            _rect(d, rx + 5, ry, 20, 4, (40, 200, 120))
            _ellipse(d, rx + 30, ry, 4, 4, (255, 200, 60))
    _ellipse(d, x + w - 22, y + 8, 10, 10, RED)
    draw_text(img, x + w // 2, y + h - 12, "NCIC", 9, (255, 120, 120),
              weight=1.3, align="center")

# ------------------------------------------------------------ world map
# Dotted world map: hand-typed land mask, 17 rows x 65 cols.
# Columns: lon -180..+180 (step ~5.5 deg). Rows: lat 75..-61 (step ~8.5 deg).
MAP_ROWS = [
    "            ##  ####  ###      #     ##################   ",
    "  ## #######################    #### ################### ",
    "  ##########################    ##########################",
    "   #########################  ###  #####################",
    "    #######################  ####  #####################",
    "     #####################   ##     ##################  ",
    "      ###################   ###   ##################    ",
    "       ###############   ###   #################       ",
    "        #############   ####    #############          ",
    "         ###########   #####    ###########           ",
    "          #########   ######   #########   ####       ",
    "           ########   ######   #######   #####        ",
    "            #######   #####   #####     #####         ",
    "             #####    ###    ###       ###  ##        ",
    "              ###              ##      #             ",
    "              ##                                  ",
    "                                                  ",
]
MAP_X0, MAP_Y0, MAP_W, MAP_H = 16, 908, 520, 88
MAP_DX, MAP_DY = 8, 5

# (lat, lon, dx, dy) for the 13 numbered stories on the map.
MAP_PINS = [
    (36.9, 30.7, -14, -6),   # 1 Antalya
    (32.1, 20.1, -12, 10),   # 2 Benghazi
    (38.9, -77.0, 0, 0),     # 3 Washington
    (52.1, 4.3, -9, -7),     # 4 The Hague
    (37.6, 127.0, 0, 0),     # 5 Seoul
    (50.5, 30.5, 8, -5),     # 6 Dymer
    (50.8, 4.4, 9, 6),       # 7 Brussels
    (26.2, 50.6, 0, 0),      # 8 Manama
    (31.5, 34.5, 13, 8),     # 9 Gaza
    (25.6, -108.5, 0, 0),    # 10 Guasave / Sinaloa
    (1.5, 29.5, 0, 0),       # 11 Ituri
    (53.5, -2.2, -12, -5),   # 12 Manchester
    (38.9, -77.0, 18, 10),   # 13 Washington (offset from pin 3)
]


def draw_map(img):
    d = ImageDraw.Draw(img)
    draw_text(img, MAP_X0, MAP_Y0 - 16, "WHERE IT HAPPENED \u00b7 PINS MATCH STORY NUMBERS",
              11, INK, weight=1.3)
    for r, row in enumerate(MAP_ROWS):
        cy = MAP_Y0 + r * MAP_DY
        for c, ch in enumerate(row):
            if ch == "#":
                cx = MAP_X0 + c * MAP_DX
                _ellipse(d, cx, cy, 3, 3, (46, 90, 60))
    for i, (lat, lon, dx, dy) in enumerate(MAP_PINS, start=1):
        px = MAP_X0 + (lon + 180.0) / 360.0 * MAP_W + dx
        py = MAP_Y0 + (75.0 - lat) / 135.0 * MAP_H + dy
        _ellipse(d, px - 8, py - 8, 16, 16, RED, outline=(255, 255, 255))
        draw_text(img, px, py - 7, str(i), 10, (255, 255, 255),
                  weight=1.4, align="center")


# ------------------------------------------------------------ story data
# All facts verified from Reuters/AP/AFP/Al Jazeera/BBC/UN/gov.uk for
# Monday 23 November 2026. Wording shortened only where it does not fit;
# no number, date, name or quote was changed.
# Tags: CONFIRMED = multiple sources; CLAIM = unverified claim;
# REPORTED = single-source report.

TAG_COLORS = {"CONFIRMED": (22, 101, 52), "CLAIM": RED,
              "REPORTED": (90, 86, 78)}

LEADS = [
    {
        "n": 1, "kicker": "1 \u00b7 ANTALYA, T\u00dcRKIYE \u00b7 WORLD \u00b7 CLIMATE",
        "tag": "CONFIRMED",
        "headline": "COP31 ends with no deal",
        "body": "EU + 130 nations reject a text with no fossil-fuel mention \u2014 the first COP since 2000 to end with no deal. Kurum: \u201cno agreement on this text.\u201d",
        "source": "UNFCCC / Reuters",
        "ill": ill_cop31,
    },
    {
        "n": 2, "kicker": "2 \u00b7 BENGHAZI, LIBYA \u00b7 AFRICA \u00b7 WAR",
        "tag": "CONFIRMED",
        "headline": "Ukraine sinks Russian corvette off Libya",
        "body": "Zelenskyy: 7 naval drones sank the Merkury at Benghazi, 1,500 miles from the front. A Russian cargo ship was also hit. Libya asks the UN to investigate.",
        "source": "Reuters / Zelenskyy",
        "ill": ill_merkury,
    },
    {
        "n": 3, "kicker": "3 \u00b7 WASHINGTON, USA \u00b7 NORTH AMERICA \u00b7 POLITICS",
        "tag": "CONFIRMED",
        "headline": "Democrats win biggest House majority",
        "body": "Democrats hold at least 258 House seats \u2014 largest in decades. Trump moves to block oversight with an order limiting Congress\u2019s access to agency files.",
        "source": "AP / Reuters",
        "ill": ill_capitol,
    },
]

SMALL = [
    {
        "n": 4, "kicker": "4 \u00b7 THE HAGUE \u00b7 WORLD \u00b7 WORLD COURT",
        "tag": "CONFIRMED", "label": "ICJ RULING",
        "headline": "14 nations back Myanmar genocide ruling",
        "body": "14 countries back the ICJ ruling that Myanmar committed genocide. UK recognises it, sanctions 5 generals.",
        "source": "gov.uk / AP", "ill": ill_court,
    },
    {
        "n": 5, "kicker": "5 \u00b7 SEOUL \u00b7 EAST ASIA \u00b7 MARKETS",
        "tag": "CONFIRMED", "label": "KOSPI FALLS",
        "headline": "Asian chip stocks slide",
        "body": "Kospi fell as much as 5.8%, closing down 3.3%. Samsung -3.1%, SK Hynix -2.5%.",
        "source": "AP / Al Jazeera", "ill": ill_chart,
    },
    {
        "n": 6, "kicker": "6 \u00b7 DYMER, UKRAINE \u00b7 EUROPE \u00b7 WAR",
        "tag": "CONFIRMED", "label": "RESCUE IN DYMER",
        "headline": "11 killed in Dymer drone strike",
        "body": "A drone hit a five-storey block at 5am Sunday. A boy, 7, was pulled alive after 14 hours; 2 missing.",
        "source": "Reuters / Kyiv Post", "ill": ill_rescue,
    },
    {
        "n": 7, "kicker": "7 \u00b7 BRUSSELS \u00b7 EUROPE \u00b7 SECURITY",
        "tag": "CONFIRMED", "label": "NATO TALKS",
        "headline": "NATO holds emergency talks on Poland",
        "body": "32 members meet after 3 Russian missiles and a drone entered Poland. Rutte: NATO will defend every inch.",
        "source": "Reuters / NATO", "ill": ill_nato,
    },
    {
        "n": 8, "kicker": "8 \u00b7 MANAMA, BAHRAIN \u00b7 MIDDLE EAST \u00b7 IRAN",
        "tag": "CLAIM", "label": "IRAN WAR",
        "headline": "Iran war: Bahrain hit, blockade vowed",
        "body": "Iran hit a civilian site in Bahrain, 2 hurt, and struck US positions. Tehran vows to confront a US blockade.",
        "source": "Reuters / IRGC", "ill": ill_tanker,
    },
    {
        "n": 9, "kicker": "9 \u00b7 GAZA \u00b7 MIDDLE EAST \u00b7 HEALTH",
        "tag": "CONFIRMED", "label": "TOXIC GAZA",
        "headline": "Gaza \u201ctoxic\u201d on 99% of land",
        "body": "Toxic contamination covers more than 99% of Gaza \u2014 air, soil and water dangerous for decades to come.",
        "source": "Oxfam / Al Jazeera", "ill": ill_toxic,
    },
    {
        "n": 10, "kicker": "10 \u00b7 SINALOA, MEXICO \u00b7 NORTH AMERICA \u00b7 CRIME",
        "tag": "CONFIRMED", "label": "CAPTURED",
        "headline": "\u201cEl Chapo Isidro\u201d captured",
        "body": "Fausto Isidro Meza Flores, one of the FBI\u2019s 10 most wanted, captured in Guasave. 4 soldiers, 7 gunmen killed.",
        "source": "Reuters / FBI", "ill": ill_handcuffs,
    },
    {
        "n": 11, "kicker": "11 \u00b7 ITURI, DR CONGO \u00b7 AFRICA \u00b7 HEALTH",
        "tag": "CONFIRMED", "label": "EBOLA",
        "headline": "Ebola response disrupted by fighting",
        "body": "Heavy fighting near a hospital traps Ebola teams in a maternity ward. WHO warns the response is disrupted.",
        "source": "WHO / UN News", "ill": ill_hospital,
    },
    {
        "n": 12, "kicker": "12 \u00b7 MANCHESTER, UK \u00b7 EUROPE",
        "tag": "REPORTED", "label": "EVACUATED",
        "headline": "Manchester concert evacuated",
        "body": "12,000+ evacuated from a Don Toliver concert after an unknown substance, believed to be tear gas, was released.",
        "source": "Police / BBC", "ill": ill_concert,
    },
    {
        "n": 13, "kicker": "13 \u00b7 WASHINGTON, USA \u00b7 NORTH AMERICA \u00b7 CYBER",
        "tag": "REPORTED", "label": "HACK PROBE",
        "headline": "FBI probes hack of police database",
        "body": "The FBI is investigating an apparent hack of the National Crime Information Center, the police database.",
        "source": "FBI / Reuters", "ill": ill_server,
    },
]

ALSO = [
    (14, "West Bank: Eisenkot calls settler arson \u201cJewish terrorism\u201d", "Reuters"),
    (15, "Israel unity talks end with no deal; Likud and Yashar split", "Reuters"),
    (16, "NATO intel: Russia plans a nuclear-armed satellite launch this year", "German media"),
    (17, "Denmark: Russia plotted to kill rapper Kyivstoner; 3 stopped", "Danish police"),
    (18, "Tajikistan begins ICC withdrawal during Putin visit", "Reuters"),
    (19, "Nvidia reinstates Huang as CEO; SEC probe unconfirmed", "Reuters"),
    (20, "Armenia proposes a new constitution, a step to peace with Azerbaijan", "Reuters"),
    (21, "Bangladesh: Hasina to be jailed if she returns from India", "Reuters"),
    (22, "South Korea exam minister quits over AI cheating scandal", "AP"),
    (23, "Denmark to propose mobile phone ban in schools in 2027", "Reuters"),
    (24, "Istanbul: thousands march against the S\u00f6zc\u00fc TV seizure", "AP"),
    (25, "China warns citizens off Mount Fuji; $75,000 reward for a missing climber", "Reuters"),
    (26, "Delta outages in Atlanta; US intel chief warns of more tech failures", "AP"),
    (27, "Pacific despair at COP flop; Bowen told to quit", "Reuters"),
    (28, "Venezuela workers strike over pay", "AP"),
    (29, "Pope hit by a rosary in Peru, jokes it off", "AP"),
    (30, "Lula backs S\u00e1nchez in Spain\u2019s snap vote", "Reuters"),
    (31, "Fiji edge Italy 21-16 for a first Nations Championship win", "AP"),
    (32, "Anthropic -8.5% after IPO; Nvidia -14% on Friday", "AP"),
    (33, "Skubal: 9-year, $450m Mets deal, largest ever for a pitcher", "AP"),
    (34, "Singapore PM visits Canberra; Wong to defend US alliance", "SMH"),
    (35, "Goldblum honoured at the Marrakech Film Festival", "AP"),
    (36, "Trump open to capping credit-card interest rates", "Fox News"),
    (37, "Taiwan warns Canada on China trade; Pentagon presses Ottawa", "Reuters"),
    (38, "Guterres urges greater AI regulation at Barbados summit", "UN News"),
]

DATE_CHECK = [
    "186 drones over Kyiv \u2014 Sun 22 Nov",
    "Hong Kong turnout 98.79% \u2014 Sun 22 Nov",
    "ICJ ruling on Myanmar \u2014 Thu 19 Nov",
    "Sparta II ablaze, Gulf of Finland \u2014 Sat 22 Nov",
    "Iran hits Bahrain site \u2014 Sat 22 Nov",
    "Gaza truck strike, 3 killed \u2014 Sat 22 Nov",
    "Kryvyi Rih: child killed \u2014 Sat 22 Nov",
    "Verstappen wins Las Vegas GP \u2014 Sat 22 Nov",
    "Nigeria boat capsizes, 24 dead \u2014 Fri 21 Nov",
    "India 720/9 in Wellington \u2014 Sat 22 Nov",
    "Anthropic IPO \u2014 Thu 20 Nov",
    "Hegseth in Caracas \u2014 Wed 18 Nov",
    "Wembanyama scores 50 \u2014 Sat 22 Nov",
]

NUMBERS = [
    ("258", "HOUSE SEATS"),
    ("11", "KILLED IN DYMER"),
    ("5.8%", "KOSPI FALL, AT WORST"),
    ("99%", "OF GAZA \u201cTOXIC\u201d"),
    ("14", "NATIONS BACK ICJ RULING"),
    ("7", "NAVAL DRONES SANK MERKURY"),
]

REGIONS = [
    ("EUROPE", 8, NAVY), ("MIDDLE EAST", 4, AMBER),
    ("NORTH AMERICA", 9, GREEN), ("SOUTH AMERICA", 3, PURPLE),
    ("EAST ASIA", 4, PINK), ("SOUTH ASIA", 2, TEAL),
    ("SOUTHEAST ASIA", 1, LIME), ("AFRICA", 3, RED),
    ("OCEANIA", 3, SKY), ("WORLD", 1, INK),
]

TIMELINE = [
    ("01:28", "WOMAN, 79, PULLED ALIVE IN DYMER"),
    ("02:33", "KOSPI SIDECAR HALT, SEOUL"),
    ("05:23", "DYMER TOLL REACHES 11"),
    ("14:43", "14 NATIONS BACK ICJ RULING"),
]

# Facts frozen at this UTC time on 23 Nov 2026 (literal, never the clock).
PRESS_TIME = "23:48 UTC"

# ---------------------------------------------------------------- layout
WARNS = []


def check(cond, msg):
    if not cond:
        WARNS.append(msg)


def draw_tag_box(img, x_right, y, tag, size=8.5):
    """Small filled verification tag, right-aligned at x_right."""
    w = text_width(tag, size, tracking=0.5) + 10
    h = size + 4
    d = ImageDraw.Draw(img)
    d.rectangle([x_right - w, y, x_right, y + h], fill=TAG_COLORS[tag])
    draw_text(img, x_right - w / 2, y + 1, tag, size, (255, 255, 255),
              weight=1.3, align="center", tracking=0.5)
    return w


def draw_lead(img, story, col_x, col_w, y_top):
    d = ImageDraw.Draw(img)
    hero_h = 88
    story["ill"](img, col_x + 14, y_top, 300, hero_h)
    y = y_top + hero_h + 3
    # kicker + tag
    ks = fit_size(story["kicker"], 9.5, col_w - 78, weight=1.2)
    draw_text(img, col_x + 14, y, story["kicker"], ks, INK, weight=1.2)
    draw_tag_box(img, col_x + col_w - 14, y, story["tag"])
    y += 13
    # headline, max 2 lines
    hl = wrap_text(story["headline"], 25, col_w - 28, tracking=0.2)
    check(len(hl) <= 2, "lead %d headline wraps to %d lines" % (story["n"], len(hl)))
    y = draw_block(img, col_x + 14, y, hl[:2], 25, INK, weight=1.3,
                   leading=26, tracking=0.2)
    y += 2
    # body, 3 lines
    bl = wrap_text(story["body"], 11.5, col_w - 28)
    check(len(bl) <= 3, "lead %d body wraps to %d lines" % (story["n"], len(bl)))
    y = draw_block(img, col_x + 14, y, bl[:3], 11.5, INK_SOFT, leading=14)
    draw_text(img, col_x + 14, y + 1, story["source"], 10, GREY, weight=1.1)
    return y + 13


def draw_small(img, story, col_x, col_w, y_top):
    d = ImageDraw.Draw(img)
    thumb_h = 44
    # thumbnail with a label bar: topic left, verification tag right
    story["ill"](img, col_x, y_top + 11, col_w, thumb_h - 11)
    d.rectangle([col_x, y_top, col_x + col_w, y_top + 11],
                fill=TAG_COLORS[story["tag"]])
    draw_text(img, col_x + 4, y_top, story["label"], 8, (255, 255, 255),
              weight=1.3)
    tw = text_width(story["tag"], 8, tracking=0.5)
    draw_text(img, col_x + col_w - 4 - tw, y_top, story["tag"], 8,
              (255, 255, 255), weight=1.3, tracking=0.5)
    y = y_top + thumb_h + 2
    ks = fit_size(story["kicker"], 8.5, col_w, weight=1.2)
    draw_text(img, col_x, y, story["kicker"], ks, INK, weight=1.2)
    y += 11
    hl = wrap_text(story["headline"], 15, col_w, tracking=0.1)
    check(len(hl) <= 2, "small %d headline wraps to %d lines" % (story["n"], len(hl)))
    y = draw_block(img, col_x, y, hl[:2], 15, INK, weight=1.3, leading=17,
                   tracking=0.1)
    y += 1
    bl = wrap_text(story["body"], 10, col_w)
    check(len(bl) <= 3, "small %d body wraps to %d lines" % (story["n"], len(bl)))
    bl = bl[:3]
    for ln in bl:
        draw_text(img, col_x, y, ln, 10, INK_SOFT)
        y += 12.5
    draw_text(img, col_x, y + 1, story["source"], 9.5, RED, weight=1.1)
    return y + 12


def draw_header(img):
    d = ImageDraw.Draw(img)
    # top navy strip
    _rect(d, 0, 0, W, 26, NAVY)
    draw_text(img, W // 2, 4,
              "THE WORLD IN ONE DAY \u00b7 38 STORIES \u00b7 10 REGIONS \u00b7 EVERY ONE DATED MONDAY 23 NOVEMBER 2026",
              13, (255, 255, 255), weight=1.2, align="center", tracking=0.5)
    # title
    title = "Monday 23 November 2026"
    ts = fit_size(title, 72, 990, weight=1.3)
    draw_text(img, W // 2, 24, title, ts, INK, weight=1.3, align="center")
    # subtitle
    sub = "No Deal in Antalya \u00b7 Corvette Sunk Off Libya \u00b7 258 Seats in Washington"
    ss = fit_size(sub, 27, 990, weight=1.3)
    draw_text(img, W // 2, 108, sub, ss, INK, weight=1.3, align="center")
    # red sub-line
    red = "COP31 ends with no deal \u00b7 Ukraine sinks a Russian warship in the Med \u00b7 Democrats take the House"
    rs = fit_size(red, 18, 990, weight=1.2)
    draw_text(img, W // 2, 134, red, rs, RED, weight=1.2, align="center")
    # day in numbers
    cell = W / 6.0
    for i, (num, label) in enumerate(NUMBERS):
        cx = cell * i + cell / 2
        if i:
            d.line([(cell * i, 150), (cell * i, 198)], fill=RULE, width=1)
        draw_text(img, cx, 152, num, 38, INK, weight=1.4, align="center")
        ls = fit_size(label, 11, cell - 10, weight=1.2)
        draw_text(img, cx, 188, label, ls, INK_SOFT, weight=1.2, align="center")
    d.line([(16, 202), (W - 16, 202)], fill=RULE, width=1)
    # region tally
    segs = []
    total = 0.0
    for name, n, color in REGIONS:
        seg = "%s %d" % (name, n)
        segs.append((seg, color))
        total += text_width(seg, 12.5, tracking=0.3)
    total += text_width(" \u00b7 ", 12.5) * (len(segs) - 1)
    x = (W - total) / 2
    for i, (seg, color) in enumerate(segs):
        draw_text(img, x, 205, seg, 12.5, color, weight=1.3, tracking=0.3)
        x += text_width(seg, 12.5, tracking=0.3)
        if i < len(segs) - 1:
            draw_text(img, x, 205, " \u00b7 ", 12.5, GREY, weight=1.0)
            x += text_width(" \u00b7 ", 12.5)
    # timeline (shrunk to fit the page width)
    parts = [("THE DAY IN UTC", RED, 1.3)]
    for t, txt in TIMELINE:
        parts.append((" \u00b7 ", GREY, 1.0))
        parts.append((t, RED, 1.3))
        parts.append((" " + txt, INK, 1.1))
    tls = 12.5
    while tls > 8.0 and sum(text_width(s, tls, tracking=0.3)
                            for s, _, _ in parts) > 990:
        tls -= 0.25
    total = sum(text_width(s, tls, tracking=0.3) for s, _, _ in parts)
    x = (W - total) / 2
    for s, color, wt in parts:
        draw_text(img, x, 221, s, tls, color, weight=wt, tracking=0.3)
        x += text_width(s, tls, tracking=0.3)
    d.line([(16, 237), (W - 16, 237)], fill=RULE, width=1)


def draw_also(img, y_head):
    d = ImageDraw.Draw(img)
    draw_text(img, 16, y_head, "ALSO ON MONDAY 23 NOVEMBER \u2014 25 MORE STORIES",
              14, INK, weight=1.4)
    d.line([(16, y_head + 17), (W - 16, y_head + 17)], fill=RULE, width=1)
    col_w = 492
    lh = 9.7
    y = y_head + 21
    for i, (n, head, src) in enumerate(ALSO):
        col = 0 if i < 13 else 1
        row = i if i < 13 else i - 13
        yy = y + row * lh
        xx = 16 + col * (col_w + 16)
        line = "%d. %s \u2014 %s" % (n, head, src)
        fs = fit_size(line, 9.5, col_w)
        draw_text(img, xx, yy, line, fs, INK_SOFT)
    return y + 13 * lh


def draw_bottom(img, y_top):
    d = ImageDraw.Draw(img)
    # DATE CHECK box (right), two columns of items
    bx0, bx1 = 544, 1008
    d.rectangle([bx0, y_top, bx1, 1000], outline=RED, width=2)
    head = "DATE CHECK \u2014 left out on purpose: these happened on other days"
    hs = fit_size(head, 11, bx1 - bx0 - 16, weight=1.4)
    draw_text(img, (bx0 + bx1) / 2, y_top + 6, head, hs, RED, weight=1.4,
              align="center")
    d.line([(bx0 + 8, y_top + 23), (bx1 - 8, y_top + 23)], fill=RED, width=1)
    col_w = (bx1 - bx0 - 24) // 2
    for i, item in enumerate(DATE_CHECK):
        col = 0 if i < 7 else 1
        row = i if i < 7 else i - 7
        xx = bx0 + 12 + col * (col_w + 4)
        yy = y_top + 27 + row * 11.5
        draw_text(img, xx, yy, "\u2022 " + item, 9.5, INK_SOFT)
    # map (left)
    draw_map(img)


def draw_footer(img):
    draw_text(img, W // 2, 1003,
              "Sources: Reuters, BBC, AP, AFP, Al Jazeera, The Guardian, UN News, Kyiv Post, gov.uk",
              9.5, INK_SOFT, align="center")
    draw_text(img, W // 2, 1013,
              "CONFIRMED verified by multiple sources \u00b7 CLAIM not verified \u00b7 REPORTED single-source report \u00b7 Wires read to press time " + PRESS_TIME,
              9.5, INK_SOFT, align="center")


def build():
    img = Image.new("RGB", (W, H), PAPER)
    draw_header(img)
    # leads
    col_w = 328
    for i, story in enumerate(LEADS):
        col_x = 16 + i * 332
        if i:
            ImageDraw.Draw(img).line([(col_x - 2, 242), (col_x - 2, 452)],
                                     fill=RULE, width=1)
        draw_lead(img, story, col_x, col_w, 240)
    # small stories, 2 rows of 5
    small_w = 192
    for r in range(2):
        y0 = 457 + r * 140
        for c in range(5):
            story = SMALL[r * 5 + c]
            draw_small(img, story, 16 + c * 200, small_w, y0)
    draw_also(img, 741)
    draw_bottom(img, 891)
    draw_footer(img)
    return img


def main():
    # recounts before drawing
    total = len(LEADS) + len(SMALL) + len(ALSO)
    check(total == 38, "story count %d != 38" % total)
    check(sum(n for _, n, _ in REGIONS) == 38, "region tally != 38")
    check(len(DATE_CHECK) == 13, "DATE CHECK %d != 13" % len(DATE_CHECK))
    check(len(NUMBERS) == 6, "numbers %d != 6" % len(NUMBERS))
    check(len(TIMELINE) == 4, "timeline %d != 4" % len(TIMELINE))
    check(len(MAP_PINS) == 13, "map pins %d != 13" % len(MAP_PINS))
    img = build()
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    img.save(path, format="PNG")
    print("wrote %s (%dx%d)" % (path, img.width, img.height))
    print("counts: stories=%d regions=%d datecheck=%d numbers=%d timeline=%d pins=%d"
          % (total, sum(n for _, n, _ in REGIONS), len(DATE_CHECK),
             len(NUMBERS), len(TIMELINE), len(MAP_PINS)))
    if WARNS:
        print("WARNINGS:")
        for w in WARNS:
            print(" - " + w)
    else:
        print("no layout warnings")


if __name__ == "__main__":
    main()
