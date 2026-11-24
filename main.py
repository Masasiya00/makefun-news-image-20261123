#!/usr/bin/env python3
"""news-image-20261123 v2 — Monday 23 November 2026, one-day newspaper.

Stdlib only. Hand-built stroke font, hand-built rasterizer and PNG encoder.
Deterministic: no clock, no random, no network. Output 1024x1024 PNG.
"""
import itertools
import math
import os
import struct
import zlib

W = 1024
H = 1024

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
MAP_DOT = (46, 90, 60)
WHITE = (255, 255, 255)
TAG_CONFIRMED = GREEN
TAG_CLAIM = RED
TAG_REPORTED = (90, 86, 78)

REGION_COLOURS = {
    "EUROPE": NAVY, "MIDDLE EAST": AMBER, "NORTH AMERICA": GREEN,
    "SOUTH AMERICA": PURPLE, "EAST ASIA": PINK, "SOUTH ASIA": TEAL,
    "SOUTHEAST ASIA": LIME, "AFRICA": RED, "OCEANIA": SKY, "WORLD": INK,
}

WARNINGS = []


def warn(msg):
    WARNINGS.append(msg)


# ---------------------------------------------------------------- rasterizer
class Img:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.buf = bytearray(w * h * 3)
        r, g, b = bg
        for i in range(0, len(self.buf), 3):
            self.buf[i] = r
            self.buf[i + 1] = g
            self.buf[i + 2] = b

    def set_px(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.buf[i] = c[0]
            self.buf[i + 1] = c[1]
            self.buf[i + 2] = c[2]

    def blend_px(self, x, y, c, a):
        # a: 0..255
        if 0 <= x < self.w and 0 <= y < self.h and a:
            i = (y * self.w + x) * 3
            self.buf[i] = (c[0] * a + self.buf[i] * (255 - a)) // 255
            self.buf[i + 1] = (c[1] * a + self.buf[i + 1] * (255 - a)) // 255
            self.buf[i + 2] = (c[2] * a + self.buf[i + 2] * (255 - a)) // 255

    def fill_rect(self, x, y, w, h, c):
        x0 = max(0, int(math.floor(x)))
        y0 = max(0, int(math.floor(y)))
        x1 = min(self.w, int(math.ceil(x + w)))
        y1 = min(self.h, int(math.ceil(y + h)))
        for yy in range(y0, y1):
            base = (yy * self.w + x0) * 3
            for xx in range(x0, x1):
                i = base + (xx - x0) * 3
                self.buf[i] = c[0]
                self.buf[i + 1] = c[1]
                self.buf[i + 2] = c[2]

    def fill_ellipse(self, cx, cy, rx, ry, c):
        if rx <= 0 or ry <= 0:
            return
        x0 = max(0, int(math.floor(cx - rx)))
        x1 = min(self.w - 1, int(math.ceil(cx + rx)))
        y0 = max(0, int(math.floor(cy - ry)))
        y1 = min(self.h - 1, int(math.ceil(cy + ry)))
        for yy in range(y0, y1 + 1):
            dy = (yy - cy) / ry
            if abs(dy) > 1:
                continue
            dx = rx * math.sqrt(max(0.0, 1.0 - dy * dy))
            xa = max(x0, int(math.ceil(cx - dx)))
            xb = min(x1, int(math.floor(cx + dx)))
            for xx in range(xa, xb + 1):
                self.set_px(xx, yy, c)

    def ellipse_outline(self, cx, cy, rx, ry, c, thick=1):
        steps = max(24, int(2 * math.pi * max(rx, ry)))
        for k in range(steps):
            a = 2 * math.pi * k / steps
            self.fill_ellipse(cx + rx * math.cos(a), cy + ry * math.sin(a),
                              thick, thick, c)

    def fill_polygon(self, pts, c):
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0 = max(0, int(math.floor(min(ys))))
        y1 = min(self.h - 1, int(math.ceil(max(ys))))
        n = len(pts)
        for yy in range(y0, y1 + 1):
            xs = []
            for k in range(n):
                x0, y0p = pts[k]
                x1, y1p = pts[(k + 1) % n]
                if (y0p <= yy < y1p) or (y1p <= yy < y0p):
                    if y1p != y0p:
                        xs.append(x0 + (yy - y0p) * (x1 - x0) / (y1p - y0p))
            xs.sort()
            for j in range(0, len(xs) - 1, 2):
                xa = max(0, int(math.ceil(xs[j])))
                xb = min(self.w - 1, int(math.floor(xs[j + 1])))
                for xx in range(xa, xb + 1):
                    self.set_px(xx, yy, c)

    def thick_line(self, x0, y0, x1, y1, c, width=1.0):
        dx = x1 - x0
        dy = y1 - y0
        length = math.hypot(dx, dy)
        if length < 0.5:
            self.fill_ellipse(x0, y0, width / 2, width / 2, c)
            return
        nx = -dy / length * width / 2
        ny = dx / length * width / 2
        self.fill_polygon([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
                           (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], c)
        self.fill_ellipse(x0, y0, width / 2, width / 2, c)
        self.fill_ellipse(x1, y1, width / 2, width / 2, c)

    def polyline(self, pts, c, width=1.0):
        for k in range(len(pts) - 1):
            self.thick_line(pts[k][0], pts[k][1], pts[k + 1][0],
                            pts[k + 1][1], c, width)

    def line(self, x0, y0, x1, y1, c, width=1.0):
        self.thick_line(x0, y0, x1, y1, c, width)


# ------------------------------------------------------------- alpha buffer
# Used by the text renderer: draw strokes at 4x into an alpha layer, then
# downscale (box average) and blend onto the page.
class Alpha:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.buf = bytearray(w * h)

    def set_px(self, x, y, v=255):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = y * self.w + x
            if v > self.buf[i]:
                self.buf[i] = v

    def fill_ellipse(self, cx, cy, rx, ry):
        if rx <= 0 or ry <= 0:
            return
        x0 = max(0, int(math.floor(cx - rx)))
        x1 = min(self.w - 1, int(math.ceil(cx + rx)))
        y0 = max(0, int(math.floor(cy - ry)))
        y1 = min(self.h - 1, int(math.ceil(cy + ry)))
        for yy in range(y0, y1 + 1):
            dy = (yy - cy) / ry
            if abs(dy) > 1:
                continue
            dx = rx * math.sqrt(max(0.0, 1.0 - dy * dy))
            xa = max(x0, int(math.ceil(cx - dx)))
            xb = min(x1, int(math.floor(cx + dx)))
            for xx in range(xa, xb + 1):
                self.set_px(xx, yy)

    def fill_polygon(self, pts):
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0 = max(0, int(math.floor(min(ys))))
        y1 = min(self.h - 1, int(math.ceil(max(ys))))
        n = len(pts)
        for yy in range(y0, y1 + 1):
            xs = []
            for k in range(n):
                x0, y0p = pts[k]
                x1, y1p = pts[(k + 1) % n]
                if (y0p <= yy < y1p) or (y1p <= yy < y0p):
                    if y1p != y0p:
                        xs.append(x0 + (yy - y0p) * (x1 - x0) / (y1p - y0p))
            xs.sort()
            for j in range(0, len(xs) - 1, 2):
                xa = max(0, int(math.ceil(xs[j])))
                xb = min(self.w - 1, int(math.floor(xs[j + 1])))
                for xx in range(xa, xb + 1):
                    self.set_px(xx, yy)

    def thick_line(self, x0, y0, x1, y1, half):
        dx = x1 - x0
        dy = y1 - y0
        length = math.hypot(dx, dy)
        if length < 0.5:
            self.fill_ellipse(x0, y0, half, half)
            return
        nx = -dy / length * half
        ny = dx / length * half
        self.fill_polygon([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
                           (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)])
        self.fill_ellipse(x0, y0, half, half)
        self.fill_ellipse(x1, y1, half, half)

# ------------------------------------------------------------- stroke font
# Each glyph: list of strokes; each stroke: list of (x, y) on a 0..12 x
# 0..16 grid. Baseline y=12, cap top y=2, x-height top y=5, descender y=16.
# Accented letters are base glyph + accent strokes (y < 2 or below baseline).
GLYPHS = {
    "A": [[(0, 12), (6, 2), (12, 12)], [(3, 8), (9, 8)]],
    "B": [[(1, 2), (1, 12)], [(1, 2), (9, 2), (11, 5), (9, 7), (1, 7)],
          [(1, 7), (10, 7), (11, 10), (9, 12), (1, 12)]],
    "C": [[(11, 3), (8, 2), (3, 2), (1, 5), (1, 9), (3, 12), (8, 12), (11, 10)]],
    "D": [[(1, 2), (1, 12)], [(1, 2), (8, 2), (11, 5), (11, 9), (8, 12), (1, 12)]],
    "E": [[(11, 2), (1, 2), (1, 12), (11, 12)], [(1, 7), (8, 7)]],
    "F": [[(1, 2), (1, 12)], [(1, 2), (11, 2)], [(1, 7), (8, 7)]],
    "G": [[(11, 3), (8, 2), (3, 2), (1, 5), (1, 9), (3, 12), (9, 12), (11, 10), (11, 7), (7, 7)]],
    "H": [[(1, 2), (1, 12)], [(11, 2), (11, 12)], [(1, 7), (11, 7)]],
    "I": [[(6, 2), (6, 12)], [(3, 2), (9, 2)], [(3, 12), (9, 12)]],
    "J": [[(9, 2), (9, 11), (7, 12), (4, 12), (2, 10)], [(5, 2), (10, 2)]],
    "K": [[(1, 2), (1, 12)], [(11, 2), (1, 7)], [(4, 6), (11, 12)]],
    "L": [[(1, 2), (1, 12), (11, 12)]],
    "M": [[(1, 12), (1, 2), (6, 9), (11, 2), (11, 12)]],
    "N": [[(1, 12), (1, 2), (11, 12), (11, 2)]],
    "O": [[(6, 2), (9, 2), (11, 5), (11, 9), (9, 12), (6, 12), (3, 12), (1, 9), (1, 5), (3, 2), (6, 2)]],
    "P": [[(1, 12), (1, 2)], [(1, 2), (9, 2), (11, 5), (9, 7), (1, 7)]],
    "Q": [[(6, 2), (9, 2), (11, 5), (11, 9), (9, 12), (6, 12), (3, 12), (1, 9), (1, 5), (3, 2), (6, 2)], [(8, 10), (12, 14)]],
    "R": [[(1, 12), (1, 2)], [(1, 2), (9, 2), (11, 5), (9, 7), (1, 7)], [(5, 7), (12, 12)]],
    "S": [[(11, 3), (8, 2), (4, 2), (2, 4), (2, 6), (4, 7), (8, 7), (10, 8), (10, 10), (8, 12), (4, 12), (1, 10)]],
    "T": [[(6, 2), (6, 12)], [(1, 2), (11, 2)]],
    "U": [[(1, 2), (1, 10), (3, 12), (9, 12), (11, 10), (11, 2)]],
    "V": [[(1, 2), (6, 12), (11, 2)]],
    "W": [[(1, 2), (3, 12), (6, 7), (9, 12), (11, 2)]],
    "X": [[(1, 2), (11, 12)], [(11, 2), (1, 12)]],
    "Y": [[(1, 2), (6, 7), (11, 2)], [(6, 7), (6, 12)]],
    "Z": [[(1, 2), (11, 2), (1, 12), (11, 12)]],
    "a": [[(11, 5), (11, 12)], [(3, 6), (5, 5), (9, 5), (11, 7), (11, 10), (9, 12), (5, 12), (3, 10), (3, 8), (5, 6)]],
    "b": [[(1, 2), (1, 12)], [(1, 7), (3, 5), (8, 5), (11, 7), (11, 10), (9, 12), (4, 12), (1, 10)]],
    "c": [[(11, 6), (8, 5), (4, 5), (2, 7), (2, 10), (4, 12), (8, 12), (11, 10)]],
    "d": [[(11, 2), (11, 12)], [(11, 7), (9, 5), (4, 5), (1, 7), (1, 10), (3, 12), (8, 12), (11, 10)]],
    "e": [[(11, 10), (9, 12), (4, 12), (2, 10), (2, 7), (4, 5), (9, 5), (11, 7), (11, 8), (2, 8)]],
    "f": [[(8, 2), (5, 3), (4, 5), (4, 12)], [(2, 5), (9, 5)]],
    "g": [[(3, 6), (5, 5), (9, 5), (11, 7), (11, 10), (9, 12), (5, 12), (3, 10), (3, 8), (5, 6)], [(11, 6), (11, 13), (9, 16), (4, 16), (2, 14)]],
    "h": [[(1, 2), (1, 12)], [(1, 7), (4, 5), (8, 5), (11, 7), (11, 12)]],
    "i": [[(6, 5), (6, 12)], [(5, 2), (7, 2)]],
    "j": [[(8, 5), (8, 13), (6, 16), (3, 16)], [(7, 2), (9, 2)]],
    "k": [[(1, 2), (1, 12)], [(11, 5), (1, 9)], [(5, 8), (11, 12)]],
    "l": [[(6, 2), (6, 12)]],
    "m": [[(1, 12), (1, 5), (3, 5), (5, 7), (5, 12)], [(5, 7), (7, 5), (10, 5), (11, 7), (11, 12)]],
    "n": [[(1, 12), (1, 5)], [(1, 7), (4, 5), (8, 5), (11, 7), (11, 12)]],
    "o": [[(6, 5), (9, 5), (11, 7), (11, 10), (9, 12), (6, 12), (3, 12), (1, 10), (1, 7), (3, 5), (6, 5)]],
    "p": [[(1, 5), (1, 16)], [(1, 7), (4, 5), (9, 5), (11, 7), (11, 10), (9, 12), (4, 12), (1, 10)]],
    "q": [[(11, 5), (11, 16)], [(11, 7), (8, 5), (3, 5), (1, 7), (1, 10), (3, 12), (7, 12), (11, 10)]],
    "r": [[(1, 12), (1, 5)], [(1, 7), (4, 5), (8, 5), (10, 7)]],
    "s": [[(10, 6), (8, 5), (4, 5), (2, 7), (2, 8), (4, 9), (8, 9), (10, 10), (10, 11), (8, 12), (4, 12), (2, 11)]],
    "t": [[(6, 2), (6, 12)], [(3, 5), (9, 5)], [(6, 12), (9, 12)]],
    "u": [[(1, 5), (1, 10), (3, 12), (8, 12), (11, 10), (11, 5)]],
    "v": [[(1, 5), (6, 12), (11, 5)]],
    "w": [[(1, 5), (3, 12), (6, 8), (9, 12), (11, 5)]],
    "x": [[(1, 5), (11, 12)], [(11, 5), (1, 12)]],
    "y": [[(1, 5), (6, 11), (11, 5)], [(6, 11), (5, 16), (3, 16)]],
    "z": [[(1, 5), (11, 5), (1, 12), (11, 12)]],
    "0": [[(6, 2), (9, 2), (11, 5), (11, 9), (9, 12), (6, 12), (3, 12), (1, 9), (1, 5), (3, 2), (6, 2)], [(4, 9), (8, 5)]],
    "1": [[(6, 2), (6, 12)], [(3, 4), (6, 2)], [(3, 12), (9, 12)]],
    "2": [[(2, 4), (4, 2), (9, 2), (11, 4), (11, 6), (2, 12), (11, 12)]],
    "3": [[(2, 3), (5, 2), (9, 2), (11, 4), (10, 7), (7, 7)], [(7, 7), (10, 7), (11, 9), (9, 12), (5, 12), (2, 11)]],
    "4": [[(8, 2), (8, 12)], [(1, 9), (10, 9)], [(8, 2), (1, 9)]],
    "5": [[(11, 2), (1, 2), (1, 7), (8, 7), (11, 9), (11, 11), (9, 12), (3, 12), (1, 10)]],
    "6": [[(10, 3), (7, 2), (3, 4), (1, 7), (1, 10), (3, 12), (8, 12), (11, 10), (11, 7), (8, 5), (3, 5)]],
    "7": [[(1, 2), (11, 2), (6, 12)]],
    "8": [[(6, 2), (8, 2), (10, 4), (10, 6), (8, 7), (6, 7), (4, 7), (2, 6), (2, 4), (4, 2), (6, 2)], [(6, 7), (9, 7), (11, 9), (11, 11), (9, 12), (6, 12), (3, 12), (1, 11), (1, 9), (3, 7), (6, 7)]],
    "9": [[(11, 12), (11, 4), (10, 2), (6, 2), (3, 3), (2, 5), (2, 7), (4, 9), (8, 9), (11, 7)]],
    ".": [[(5, 11), (7, 11)]],
    ",": [[(6, 11), (6, 12), (5, 14), (4, 15)]],
    ":": [[(5, 6), (7, 6)], [(5, 11), (7, 11)]],
    ";": [[(5, 6), (7, 6)], [(6, 11), (6, 12), (5, 14), (4, 15)]],
    "'": [[(6, 2), (5, 5)]],
    '"': [[(4, 2), (3, 5)], [(8, 2), (7, 5)]],
    "\u201c": [[(4, 2), (3, 5)], [(8, 2), (7, 5)]],
    "\u201d": [[(4, 5), (3, 2)], [(8, 5), (7, 2)]],
    "\u2013": [[(1, 7), (11, 7)]],
    "\u2014": [[(0, 7), (12, 7)]],
    "\u00b7": [[(5, 6), (7, 6)]],
    "\u2022": [[(5, 6), (7, 6)]],
    "%": [[(3, 2), (5, 2), (6, 4), (6, 6), (4, 6), (3, 4), (3, 2)], [(9, 12), (9, 10), (7, 10), (6, 12), (6, 14), (8, 14), (9, 12)], [(10, 2), (2, 12)]],
    "(": [[(9, 2), (6, 4), (5, 7), (6, 10), (9, 12)]],
    ")": [[(3, 2), (6, 4), (7, 7), (6, 10), (3, 12)]],
    "/": [[(9, 2), (3, 12)]],
    "&": [[(9, 3), (7, 2), (4, 3), (3, 6), (5, 8), (8, 8), (10, 10), (10, 12), (8, 12), (3, 12), (2, 10), (3, 8), (6, 6), (10, 2)]],
    "!": [[(6, 2), (6, 9)], [(5, 11), (7, 11)]],
    "?": [[(3, 4), (6, 2), (10, 3), (10, 6), (8, 8), (6, 8)], [(5, 11), (7, 11)]],
    "+": [[(6, 3), (6, 11)], [(2, 7), (10, 7)]],
    "=": [[(1, 5), (11, 5)], [(1, 9), (11, 9)]],
    "$": [[(11, 4), (8, 2), (4, 2), (2, 4), (2, 6), (4, 7), (8, 7), (10, 8), (10, 10), (8, 12), (4, 12), (1, 10)], [(6, 1), (6, 13)]],
    "-": [[(2, 7), (10, 7)]],
    "*": [[(6, 2), (6, 12)], [(2, 5), (10, 9)], [(10, 5), (2, 9)]],
}

# Accented letters: base glyph + accent strokes (in glyph coords).
ACCENTS = {
    "\u00dc": ("U", [[(3, 0), (4, 0)], [(8, 0), (9, 0)]]),
    "\u00fc": ("u", [[(3, 3), (4, 3)], [(8, 3), (9, 3)]]),
    "\u00e9": ("e", [[(7, 1), (10, -1)]]),
    "\u00e1": ("a", [[(7, 1), (10, -1)]]),
    "\u00ed": ("i", [[(7, 1), (10, -1)]]),
    "\u00f6": ("o", [[(3, 3), (4, 3)], [(8, 3), (9, 3)]]),
    "\u00e7": ("c", [[(6, 13), (7, 15), (5, 16)]]),
    "\u00f1": ("n", [[(2, 3), (4, 2), (6, 3), (8, 2), (10, 3)]]),
    "\u00e0": ("a", [[(5, -1), (8, 1)]]),
    "\u00f3": ("o", [[(7, 1), (10, -1)]]),
}

NARROW = {"i": 6, "j": 6, "l": 6, "I": 6, "1": 7, "f": 7, "t": 7, "r": 7, ".": 5,
          ",": 5, ":": 5, ";": 5, "'": 4, '"': 8, "\u201c": 8, "\u201d": 8,
          "\u00b7": 5, "!": 5, "(": 6, ")": 6, "/": 7, "-": 7, "\u2013": 9,
          "\u2014": 12, "%": 12, " ": 7}
WIDE = {"M": 14, "W": 14, "m": 13, "w": 13, "O": 12, "Q": 12, "G": 12,
        "D": 12, "U": 12, "H": 12, "N": 12, "A": 12, "V": 12, "X": 12,
        "Y": 12, "C": 12, "S": 12, "B": 12, "E": 11, "F": 11, "K": 12,
        "R": 12, "P": 11, "J": 11, "T": 11, "Z": 12, "0": 12, "2": 12,
        "3": 12, "5": 12, "6": 12, "8": 12, "9": 12, "&": 12, "$": 12,
        "=": 12, "+": 11}


def glyph_strokes(ch):
    if ch in GLYPHS:
        return GLYPHS[ch]
    if ch in ACCENTS:
        base, acc = ACCENTS[ch]
        return GLYPHS[base] + acc
    return []


def glyph_advance(ch):
    if ch in NARROW:
        return NARROW[ch]
    if ch in WIDE:
        return WIDE[ch]
    if ch.islower():
        return 10
    return 11


def text_width(text, size, tracking=0.0):
    scale = size / 16.0
    total = 0.0
    for ch in text:
        total += glyph_advance(ch) * scale
    if len(text) > 1:
        total += tracking * (len(text) - 1)
    return total


def fit_size(text, start_size, max_width, min_size=5.0, tracking=0.0):
    size = start_size
    while size > min_size and text_width(text, size, tracking) > max_width:
        size -= 0.5
    return size


def wrap_text(text, size, max_width, tracking=0.0):
    words = text.split(" ")
    lines = []
    cur = ""
    for w in words:
        trial = (cur + " " + w).strip()
        if text_width(trial, size, tracking) <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_text(img, x, y, text, size, color, weight=1.0, align="left",
              tracking=0.0):
    """Draw text; (x, y) is the top-left (left align) of the em box.
    y is the top of the glyph grid (y=0)."""
    if not text:
        return
    scale = size / 16.0
    total_w = text_width(text, size, tracking)
    if align == "center":
        x0 = x - total_w / 2.0
    elif align == "right":
        x0 = x - total_w
    else:
        x0 = x
    # 4x supersampled alpha layer. Em spans y 0..16; accents reach y=-2.
    pad_top = 2.5 * scale  # px above em top for accents
    buf_h_px = int(math.ceil((18.5 * scale + 2 * pad_top))) + 2
    buf_w_px = int(math.ceil(total_w)) + 4
    w4 = buf_w_px * 4
    h4 = buf_h_px * 4
    alpha = Alpha(w4, h4)
    stroke_px = max(1.05 * scale * weight, 0.8)
    half4 = stroke_px * 4 / 2.0
    cursor = 0.0
    for ch in text:
        if ch == " ":
            cursor += glyph_advance(ch) * scale + tracking
            continue
        strokes = glyph_strokes(ch)
        for stroke in strokes:
            pts4 = []
            for (gx, gy) in stroke:
                px4 = (2.0 + cursor + gx * scale) * 4
                py4 = (pad_top + gy * scale) * 4
                pts4.append((px4, py4))
            if len(pts4) == 1:
                alpha.fill_ellipse(pts4[0][0], pts4[0][1], half4, half4)
            else:
                for k in range(len(pts4) - 1):
                    alpha.thick_line(pts4[k][0], pts4[k][1],
                                     pts4[k + 1][0], pts4[k + 1][1], half4)
        cursor += glyph_advance(ch) * scale + tracking
    # Downscale 4x4 box average and blend.
    img_x0 = int(math.floor(x0)) - 1
    img_y0 = int(math.floor(y - pad_top)) - 1
    for oy in range(buf_h_px):
        for ox in range(buf_w_px):
            s = 0
            for dy in range(4):
                row = (oy * 4 + dy) * w4 + ox * 4
                s += (alpha.buf[row] + alpha.buf[row + 1] +
                      alpha.buf[row + 2] + alpha.buf[row + 3])
            a = s // 16
            if a:
                img.blend_px(img_x0 + ox, img_y0 + oy, color, a)


def draw_block(img, x, y, lines, size, color, weight=1.0, leading=None,
               tracking=0.0):
    if leading is None:
        leading = size * 1.15
    for ln in lines:
        draw_text(img, x, y, ln, size, color, weight, "left", tracking)
        y += leading
    return y

# ------------------------------------------------------------- illustrations
def lead1_cop(img, x, y, w, h):
    # Negotiation hall: warm wall, dusk windows, clock, red NO DEAL banner,
    # 5 small flags on the back wall, table with papers, seated delegates.
    img.fill_rect(x, y, w, h, (232, 213, 170))
    img.fill_rect(x, y, w, 10, (198, 168, 118))
    # two windows with dusk sky
    for wx in (x + 22, x + 208):
        img.fill_rect(wx, y + 12, 62, 30, (88, 62, 110))
        img.fill_rect(wx, y + 12, 62, 12, (240, 150, 80))
        img.fill_rect(wx, y + 30, 62, 12, (150, 70, 110))
        img.fill_rect(wx + 29, y + 12, 4, 30, (232, 213, 170))
        img.fill_rect(wx, y + 25, 62, 4, (232, 213, 170))
    # wall clock between windows
    img.fill_ellipse(x + 150, y + 28, 12, 12, WHITE)
    img.ellipse_outline(x + 150, y + 28, 12, 12, INK, 1)
    img.thick_line(x + 150, y + 28, x + 150, y + 20, INK, 2)
    img.thick_line(x + 150, y + 28, x + 156, y + 31, INK, 2)
    # red NO DEAL banner across the middle
    img.fill_rect(x, y + 44, w, 18, RED)
    draw_text(img, x + w / 2, y + 46, "NO DEAL", 15, WHITE, 1.3, "center")
    # 5 small flags along the back wall, below the banner
    flag_cols = [NAVY, RED, GREEN, SKY, AMBER]
    for i, fc in enumerate(flag_cols):
        fx = x + 18 + i * 56
        img.fill_rect(fx, y + 66, 22, 9, fc)
        img.fill_rect(fx, y + 66, 22, 3, WHITE)
    # long table with papers
    img.fill_rect(x + 8, y + 80, w - 16, 10, (120, 82, 50))
    img.fill_rect(x + 8, y + 80, w - 16, 3, (150, 110, 70))
    for px in (x + 30, x + 90, x + 150, x + 210, x + 255):
        img.fill_rect(px, y + 78, 26, 4, WHITE)
    # seated delegates: heads + shoulders, in front of flags and table
    skins = [(210, 170, 130), (190, 140, 100), (220, 180, 140),
             (170, 120, 85), (205, 165, 125)]
    suits = [NAVY, (60, 60, 60), TEAL, (90, 40, 40), (50, 70, 40)]
    for i in range(5):
        cx = x + 38 + i * 56
        img.fill_ellipse(cx, y + 71, 7, 7, skins[i])
        img.fill_ellipse(cx, y + 93, 15, 9, suits[i])


def lead2_merkury(img, x, y, w, h):
    # Night sea: dark-blue sky, stars, crescent moon, dark sea, warship,
    # orange explosion glow, 3 drone boats with wakes, wave lines.
    img.fill_rect(x, y, w, h // 2 + 6, (12, 24, 58))
    img.fill_rect(x, y + h // 2 + 6, w, h - h // 2 - 6, (16, 48, 88))
    for sx, sy in ((x + 20, y + 12), (x + 70, y + 8), (x + 130, y + 16),
                   (x + 200, y + 10), (x + 260, y + 18), (x + 45, y + 26),
                   (x + 170, y + 24), (x + 235, y + 28)):
        img.fill_ellipse(sx, sy, 1.5, 1.5, WHITE)
    # crescent moon
    img.fill_ellipse(x + 262, y + 22, 11, 11, (240, 235, 200))
    img.fill_ellipse(x + 267, y + 19, 10, 10, (12, 24, 58))
    # explosion glow above the ship
    img.fill_ellipse(x + 195, y + 42, 26, 16, (255, 140, 40))
    img.fill_ellipse(x + 195, y + 44, 16, 10, (255, 200, 80))
    img.fill_ellipse(x + 195, y + 46, 7, 5, (255, 240, 180))
    # grey warship centre-right
    img.fill_polygon([(x + 150, y + 66), (x + 248, y + 66), (x + 238, y + 80),
                      (x + 160, y + 80)], (120, 125, 130))
    img.fill_rect(x + 178, y + 52, 34, 14, (140, 145, 150))
    img.fill_rect(x + 190, y + 42, 6, 10, (140, 145, 150))
    img.fill_rect(x + 204, y + 46, 16, 3, (90, 95, 100))
    # 3 small white drone boats with wakes
    for bx in (x + 30, x + 78, x + 118):
        img.fill_rect(bx, y + 82, 18, 5, WHITE)
        img.polyline([(bx + 18, y + 84), (bx + 34, y + 80),
                      (bx + 34, y + 88)], (200, 220, 235), 1)
    # wave lines at the bottom
    for wy in (y + 92, y + 99):
        img.polyline([(x + 6, wy), (x + 40, wy - 3), (x + 80, wy),
                      (x + 130, wy - 3), (x + 180, wy), (x + 230, wy - 3),
                      (x + 294, wy)], (120, 170, 210), 1)


def lead3_capitol(img, x, y, w, h):
    # Light-blue sky, sun, green lawn, white Capitol dome left, seat bar right.
    img.fill_rect(x, y, w, h, (178, 214, 236))
    img.fill_ellipse(x + 262, y + 16, 12, 12, (255, 210, 60))
    img.fill_rect(x, y + h - 18, w, 18, (90, 150, 70))
    # Capitol: building + columns + dome + tiny flag
    img.fill_rect(x + 14, y + 58, 96, 28, WHITE)
    img.fill_rect(x + 8, y + 84, 108, 4, (200, 200, 200))
    for cx in range(x + 22, x + 104, 16):
        img.fill_rect(cx, y + 60, 5, 24, (210, 210, 210))
    img.fill_ellipse(x + 62, y + 48, 30, 16, WHITE)
    img.fill_rect(x + 32, y + 48, 60, 12, WHITE)
    img.thick_line(x + 62, y + 22, x + 62, y + 34, INK, 1)
    img.fill_polygon([(x + 62, y + 22), (x + 74, y + 26), (x + 62, y + 30)],
                     RED)
    # seat bar: grey bar 148 wide, blue segment 258 of 435
    bar_x = x + 138
    bar_y = y + 50
    img.fill_rect(bar_x, bar_y, 148, 14, (200, 200, 200))
    blue_w = int(148 * 258 / 435)
    img.fill_rect(bar_x, bar_y, blue_w, 14, (30, 80, 180))
    draw_text(img, bar_x + 74, y + 24, "258", 22, (30, 80, 180), 1.3, "center")
    draw_text(img, bar_x + 74, y + 66, "HOUSE SEATS", 10, INK, 1.3, "center")
    draw_text(img, bar_x + 74, y + 78, "DEMOCRATS \u00b7 LARGEST IN DECADES",
              9, GREEN, 1.3, "center")


def thumb_court(img, x, y, w, h):
    img.fill_rect(x, y, w, h, (222, 205, 165))
    img.fill_polygon([(x + 46, y + 4), (x + 96, y + 4), (x + 146, y + 4),
                      (x + 96, y + 16)], (180, 160, 125))
    img.fill_rect(x + 52, y + 16, 88, 4, (150, 130, 95))
    for cx in range(x + 58, x + 140, 20):
        img.fill_rect(cx, y + 20, 6, 14, WHITE)
    img.fill_rect(x + 88, y + 24, 16, 10, (90, 70, 45))
    img.fill_rect(x + 40, y + 34, 112, 4, (150, 130, 95))
    img.fill_rect(x + 34, y + 38, 124, 4, (130, 110, 80))


def thumb_chart(img, x, y, w, h):
    img.fill_rect(x, y, w, h, WHITE)
    img.thick_line(x + 14, y + 6, x + 14, y + 38, INK, 1)
    img.thick_line(x + 14, y + 38, x + 184, y + 38, INK, 1)
    img.polyline([(x + 20, y + 8), (x + 70, y + 14), (x + 110, y + 20),
                  (x + 150, y + 30), (x + 178, y + 36)], RED, 2)
    img.fill_polygon([(x + 178, y + 36), (x + 168, y + 32), (x + 172, y + 42)],
                     RED)
    draw_text(img, x + 188, y + 4, "-5.8%", 13, RED, 1.3, "right")


def thumb_rescue(img, x, y, w, h):
    img.fill_rect(x, y, w, h, (40, 40, 48))
    img.fill_rect(x + 18, y + 4, 84, 41, (110, 110, 118))
    for wy in range(y + 8, y + 40, 9):
        for wx in range(x + 24, x + 96, 14):
            col = (255, 220, 90) if (wx + wy) % 28 == 0 else (70, 70, 80)
            img.fill_rect(wx, wy, 8, 6, col)
    img.fill_ellipse(x + 150, y + 34, 26, 12, (255, 120, 30))
    img.fill_ellipse(x + 150, y + 38, 16, 8, (255, 180, 60))
    img.thick_line(x + 118, y + 44, x + 168, y + 8, (200, 160, 60), 3)
    img.fill_ellipse(x + 168, y + 6, 5, 5, (230, 190, 150))


def thumb_nato(img, x, y, w, h):
    img.fill_rect(x, y, w, h, (225, 228, 232))
    for i in range(4):
        fx = x + 18 + i * 44
        img.fill_rect(fx, y + 6, 34, 20, NAVY)
        img.fill_ellipse(fx + 17, y + 16, 7, 7, (255, 210, 60))
    img.fill_ellipse(x + 96, y + 36, 26, 8, RED)
    draw_text(img, x + 96, y + 28, "32", 13, WHITE, 1.3, "center")


def thumb_iran(img, x, y, w, h):
    # NEW dusk scene: purple sky -> orange horizon, missile arcs, coastal
    # city skyline (Manama), explosion glow, dark-blue water + small ship.
    for i in range(18):
        t = i / 17.0
        r = int(58 + (235 - 58) * t)
        g = int(32 + (120 - 32) * t)
        b = int(110 + (40 - 110) * t)
        img.fill_rect(x, y + int(i * h / 18), w, h // 18 + 1, (r, g, b))
    # missile arcs sweeping down from upper left, bright heads
    img.polyline([(x + 8, y + 2), (x + 50, y + 10), (x + 95, y + 22),
                  (x + 130, y + 34)], (255, 230, 180), 2)
    img.polyline([(x + 30, y + 2), (x + 70, y + 12), (x + 108, y + 26),
                  (x + 138, y + 38)], (255, 200, 120), 2)
    img.fill_ellipse(x + 130, y + 34, 4, 4, (255, 240, 200))
    img.fill_ellipse(x + 138, y + 38, 4, 4, (255, 220, 150))
    # dark coastal city skyline along the bottom
    img.fill_rect(x, y + 26, w, 12, (30, 20, 55))
    for bx, bh in ((x + 8, 16), (x + 30, 20), (x + 52, 14), (x + 74, 22),
                   (x + 98, 15), (x + 120, 19), (x + 144, 13), (x + 166, 17)):
        img.fill_rect(bx, y + 38 - bh, 16, bh, (25, 18, 48))
    for wx, wy in ((x + 34, y + 26), (x + 58, y + 30), (x + 80, y + 22),
                   (x + 104, y + 28), (x + 126, y + 24), (x + 150, y + 30),
                   (x + 170, y + 26)):
        img.fill_rect(wx, wy, 3, 3, (255, 210, 90))
    # small orange explosion glow near one building
    img.fill_ellipse(x + 80, y + 30, 9, 6, (255, 140, 40))
    img.fill_ellipse(x + 80, y + 31, 5, 3, (255, 210, 120))
    # dark-blue water strip at the very bottom + small ship silhouette
    img.fill_rect(x, y + 39, w, 6, (18, 42, 78))
    img.fill_polygon([(x + 150, y + 41), (x + 176, y + 41), (x + 172, y + 44),
                      (x + 154, y + 44)], (10, 20, 40))
    img.fill_rect(x + 160, y + 37, 6, 4, (10, 20, 40))


def thumb_toxic(img, x, y, w, h):
    img.fill_rect(x, y, w, h, (150, 140, 90))
    img.fill_rect(x, y + 30, w, 15, (120, 110, 65))
    img.fill_polygon([(x + 96, y + 4), (x + 138, y + 40), (x + 54, y + 40)],
                     (250, 200, 30))
    img.fill_polygon([(x + 96, y + 4), (x + 138, y + 40), (x + 54, y + 40)],
                     (250, 200, 30))
    img.fill_rect(x + 93, y + 16, 6, 14, INK)
    img.fill_ellipse(x + 96, y + 35, 3, 3, INK)


def thumb_handcuffs(img, x, y, w, h):
    img.fill_rect(x, y, w, h, (35, 35, 42))
    img.ellipse_outline(x + 62, y + 16, 16, 12, (200, 200, 205), 3)
    img.ellipse_outline(x + 128, y + 16, 16, 12, (200, 200, 205), 3)
    img.thick_line(x + 76, y + 20, x + 114, y + 20, (180, 180, 185), 2)
    img.fill_ellipse(x + 84, y + 20, 2, 2, (160, 160, 165))
    img.fill_ellipse(x + 106, y + 20, 2, 2, (160, 160, 165))
    draw_text(img, x + 96, y + 31, "FBI TOP 10", 11, WHITE, 1.3, "center")


def thumb_hospital(img, x, y, w, h):
    img.fill_rect(x, y, w, h, (235, 240, 238))
    img.fill_rect(x + 62, y + 8, 68, 26, WHITE)
    img.fill_rect(x + 88, y + 12, 16, 5, RED)
    img.fill_rect(x + 93, y + 7, 5, 15, RED)
    img.fill_rect(x + 66, y + 24, 10, 6, SKY)
    img.fill_rect(x + 116, y + 24, 10, 6, SKY)
    img.fill_polygon([(x + 8, y + 40), (x + 34, y + 28), (x + 60, y + 40)],
                     TEAL)
    img.fill_polygon([(x + 132, y + 40), (x + 158, y + 28), (x + 184, y + 40)],
                     AMBER)
    img.fill_rect(x + 70, y + 38, 52, 5, (180, 180, 180))


def thumb_concert(img, x, y, w, h):
    img.fill_rect(x, y, w, h, (25, 22, 40))
    for bx, col in ((x + 40, PURPLE), (x + 80, SKY), (x + 110, PINK),
                    (x + 150, AMBER)):
        img.fill_polygon([(bx, y + 2), (bx + 14, y + 2), (bx + 26, y + 30),
                          (bx - 4, y + 30)], col)
    img.fill_rect(x + 56, y + 28, 80, 10, WHITE)
    img.fill_rect(x + 56, y + 28, 80, 3, (200, 200, 200))
    for i in range(12):
        cx = x + 14 + i * 15
        img.fill_ellipse(cx, y + 41, 4, 4, (220, 200, 170))


def thumb_server(img, x, y, w, h):
    img.fill_rect(x, y, w, h, (30, 32, 40))
    for i in range(3):
        rx = x + 22 + i * 52
        img.fill_rect(rx, y + 6, 42, 30, (70, 75, 85))
        for ly in range(y + 10, y + 32, 7):
            img.fill_rect(rx + 5, ly, 20, 3, (50, 55, 65))
            img.fill_ellipse(rx + 34, ly + 1, 2, 2, (80, 220, 100))
            img.fill_ellipse(rx + 39, ly + 1, 1.5, 1.5, (255, 210, 60))
    img.fill_ellipse(x + 178, y + 8, 4, 4, RED)
    draw_text(img, x + 96, y + 33, "NCIC", 10, RED, 1.3, "center")


THUMB_DRAW = {4: thumb_court, 5: thumb_chart, 6: thumb_rescue,
              7: thumb_nato, 8: thumb_iran, 9: thumb_toxic,
              10: thumb_handcuffs, 11: thumb_hospital, 12: thumb_concert,
              13: thumb_server}

# ------------------------------------------------------------- world map
# Hand-typed 18 rows x 78 cols; "#" = land. Rows lat 75..-54, cols lon -180..180.
MAP_MASK = [
    ("    ##### " "##  ######" "#####  ###" "#####     " "  ##      "
     "##########" "##########" "########"),
    ("   #######" "##########" "##########" "###       " "   ###    "
     "##########" "##########" "########"),
    ("  ########" "##########" "##########" "  ##      " "  ########"
     "##########" "##########" "########"),
    ("   #######" "##########" "########  " "   #######" "##########"
     "##########" "##########" "########"),
    ("    ######" "##########" "#######   " "    ######" "##########"
     "##########" "######### " "###     "),
    ("     #####" "##########" "#####     " "   #######" "##########"
     "##########" "##########" "##      "),
    ("      ####" "######### " "###       " "  ########" "##########"
     "##########" "##########" "        "),
    ("       ###" "####      " "###       " " #########" "##########"
     "##########" "######### " "        "),
    ("        ##" "##        " "##  ##### " "  ########" "##########"
     "####  ####" "####  ### " "        "),
    ("          " "          " "  ########" "#        #" "##########"
     "##   ## ##" "##  #  #  " "        "),
    ("          " "          " "  ####### " "###       " "######### "
     "##    ##  " " #  #     " "        "),
    ("          " "          " "   ###### " "##        " " #########"
     "#         " "      ####" "####    "),
    ("          " "          " "    ##### " "#         " "  ######  "
     "          " "     #####" "###     "),
    ("          " "          " "     #### " "          " "   ####   "
     "          " "     #####" "#       "),
    ("          " "          " "     ###  " "          " "    ###   "
     "          " "      ### " "        "),
    ("          " "          " "    ##    " "          " "          "
     "          " "          " "##    ##"),
    ("          " "          " "    #     " "          " "          "
     "          " "          " "    ### "),
    ("          " "          " "    #     " "          " "          "
     "          " "          " "        "),
]

# (name, lat, lon, dx, dy)
PINS = [
    ("Antalya", 36.9, 30.7, -14, -6),
    ("Benghazi", 32.1, 20.1, -12, 10),
    ("Washington", 38.9, -77.0, 0, 0),
    ("The Hague", 52.1, 4.3, -9, -7),
    ("Seoul", 37.6, 127.0, 0, 0),
    ("Dymer", 50.5, 30.5, 8, -5),
    ("Brussels", 50.8, 4.4, 9, 6),
    ("Manama", 26.2, 50.6, 0, 0),
    ("Gaza", 31.5, 34.5, 13, 8),
    ("Guasave", 25.6, -108.5, 0, 0),
    ("Ituri", 1.5, 29.5, 0, 0),
    ("Manchester", 53.5, -2.2, -12, -5),
    ("Washington", 38.9, -77.0, 18, 10),
]

# ------------------------------------------------------------- story data
TOP_STRIP = ("THE WORLD IN ONE DAY \u00b7 38 STORIES \u00b7 10 REGIONS \u00b7 "
             "EVERY ONE DATED MONDAY 23 NOVEMBER 2026")
TITLE = "Monday 23 November 2026"
SUBTITLE = ("No Deal in Antalya \u00b7 Corvette Sunk Off Libya \u00b7 "
            "258 Seats in Washington")
RED_LINE = ("COP31 ends with no deal \u00b7 Ukraine sinks a Russian warship "
            "in the Med \u00b7 Democrats take the House")

NUMBERS = [("258", "HOUSE SEATS"), ("11", "KILLED IN DYMER"),
           ("5.8%", "KOSPI FALL, AT WORST"), ("99%", "OF GAZA \"TOXIC\""),
           ("14", "NATIONS BACK ICJ RULING"), ("7", "NAVAL DRONES SANK MERKURY")]

REGIONS = [("EUROPE", 8), ("MIDDLE EAST", 4), ("NORTH AMERICA", 9),
           ("SOUTH AMERICA", 3), ("EAST ASIA", 4), ("SOUTH ASIA", 2),
           ("SOUTHEAST ASIA", 1), ("AFRICA", 3), ("OCEANIA", 3),
           ("WORLD", 1)]

TIMELINE = [("01:28", "WOMAN, 79, PULLED ALIVE IN DYMER"),
            ("02:33", "KOSPI SIDECAR HALT, SEOUL"),
            ("05:23", "DYMER TOLL REACHES 11"),
            ("14:43", "14 NATIONS BACK ICJ RULING")]

LEADS = [
    {"n": 1, "kicker": "1 \u00b7 ANTALYA, T\u00dcRKIYE \u00b7 WORLD \u00b7 CLIMATE",
     "tag": "CONFIRMED",
     "headline": "COP31 ends with no deal",
     "body": ("EU + 130 nations reject a text with no fossil-fuel mention \u2014 "
              "the first COP since 2000 to end with no deal. Kurum: "
              "\"no agreement on this text.\""),
     "source": "UNFCCC / Reuters", "draw": lead1_cop},
    {"n": 2, "kicker": "2 \u00b7 BENGHAZI, LIBYA \u00b7 AFRICA \u00b7 WAR",
     "tag": "CONFIRMED",
     "headline": "Ukraine sinks Russian corvette off Libya",
     "body": ("Zelenskyy: 7 naval drones sank the Merkury at Benghazi, "
              "1,500 miles from the front. A Russian cargo ship was also "
              "hit. Libya asks the UN to investigate."),
     "source": "Reuters / Zelenskyy", "draw": lead2_merkury},
    {"n": 3, "kicker": "3 \u00b7 WASHINGTON, USA \u00b7 NORTH AMERICA \u00b7 POLITICS",
     "tag": "CONFIRMED",
     "headline": "Democrats win biggest House majority in decades",
     "body": ("Democrats hold at least 258 House seats \u2014 largest in "
              "decades. Trump moves to block oversight with an order "
              "limiting Congress's access to agency files."),
     "source": "AP / Reuters", "draw": lead3_capitol},
]

SMALL = [
    {"n": 4, "kicker": "4 \u00b7 THE HAGUE \u00b7 WORLD \u00b7 WORLD COURT",
     "tag": "CONFIRMED", "label": "ICJ RULING",
     "headline": "14 nations back Myanmar genocide ruling",
     "body": ("14 countries back the ICJ ruling that Myanmar committed "
              "genocide. UK recognises it, sanctions 5 generals."),
     "source": "gov.uk / AP"},
    {"n": 5, "kicker": "5 \u00b7 SEOUL \u00b7 EAST ASIA \u00b7 MARKETS",
     "tag": "CONFIRMED", "label": "KOSPI FALLS",
     "headline": "Asian chip stocks slide",
     "body": ("Kospi fell as much as 5.8%, closing down 3.3%. "
              "Samsung -3.1%, SK Hynix -2.5%."),
     "source": "AP / Al Jazeera"},
    {"n": 6, "kicker": "6 \u00b7 DYMER, UKRAINE \u00b7 EUROPE \u00b7 WAR",
     "tag": "CONFIRMED", "label": "RESCUE IN DYMER",
     "headline": "11 killed in Dymer drone strike",
     "body": ("A drone hit a five-storey block at 5am Sunday. A boy, 7, "
              "was pulled alive after 14 hours; 2 missing."),
     "source": "Reuters / Kyiv Post"},
    {"n": 7, "kicker": "7 \u00b7 BRUSSELS \u00b7 EUROPE \u00b7 SECURITY",
     "tag": "CONFIRMED", "label": "NATO TALKS",
     "headline": "NATO holds emergency talks on Poland",
     "body": ("32 members meet after 3 Russian missiles and a drone "
              "entered Poland. Rutte: NATO will defend every inch."),
     "source": "Reuters / NATO"},
    {"n": 8, "kicker": "8 \u00b7 MANAMA, BAHRAIN \u00b7 MIDDLE EAST \u00b7 IRAN",
     "tag": "CLAIM", "label": "IRAN WAR",
     "headline": "Iran war: Bahrain hit, blockade vowed",
     "body": ("Iran hit a civilian site in Bahrain, 2 hurt, and struck US "
              "positions. Tehran vows to confront a US blockade."),
     "source": "Reuters / IRGC"},
    {"n": 9, "kicker": "9 \u00b7 GAZA \u00b7 MIDDLE EAST \u00b7 HEALTH",
     "tag": "CONFIRMED", "label": "TOXIC GAZA",
     "headline": "Gaza \"toxic\" on 99% of land",
     "body": ("Toxic contamination covers more than 99% of Gaza \u2014 air, "
              "soil and water dangerous for decades to come."),
     "source": "Oxfam / Al Jazeera"},
    {"n": 10, "kicker": "10 \u00b7 SINALOA, MEXICO \u00b7 NORTH AMERICA \u00b7 CRIME",
     "tag": "CONFIRMED", "label": "CAPTURED",
     "headline": "\"El Chapo Isidro\" captured",
     "body": ("Fausto Isidro Meza Flores, one of the FBI's 10 most wanted, "
              "captured in Guasave. 4 soldiers, 7 gunmen killed."),
     "source": "Reuters / FBI"},
    {"n": 11, "kicker": "11 \u00b7 ITURI, DR CONGO \u00b7 AFRICA \u00b7 HEALTH",
     "tag": "CONFIRMED", "label": "EBOLA",
     "headline": "Ebola response disrupted by fighting",
     "body": ("Heavy fighting near a hospital traps Ebola teams in a "
              "maternity ward. WHO warns the response is disrupted."),
     "source": "WHO / UN News"},
    {"n": 12, "kicker": "12 \u00b7 MANCHESTER, UK \u00b7 EUROPE",
     "tag": "REPORTED", "label": "EVACUATED",
     "headline": "Manchester concert evacuated",
     "body": ("12,000+ evacuated from a Don Toliver concert after an "
              "unknown substance, believed to be tear gas, was released."),
     "source": "Police / BBC"},
    {"n": 13, "kicker": "13 \u00b7 WASHINGTON, USA \u00b7 NORTH AMERICA \u00b7 CYBER",
     "tag": "REPORTED", "label": "HACK PROBE",
     "headline": "FBI probes hack of police database",
     "body": ("The FBI is investigating an apparent hack of the National "
              "Crime Information Center, the police database."),
     "source": "FBI / Reuters"},
]

ALSO = [
    "West Bank: Eisenkot calls settler arson \"Jewish terrorism\" \u2014 Reuters",
    "Israel unity talks end with no deal; Likud and Yashar split \u2014 Reuters",
    "NATO intel: Russia plans a nuclear-armed satellite launch this year \u2014 German media",
    "Denmark: Russia plotted to kill rapper Kyivstoner; 3 stopped \u2014 Danish police",
    "Tajikistan begins ICC withdrawal during Putin visit \u2014 Reuters",
    "Nvidia reinstates Huang as CEO; SEC probe unconfirmed \u2014 Reuters",
    "Armenia proposes a new constitution, a step to peace with Azerbaijan \u2014 Reuters",
    "Bangladesh: Hasina to be jailed if she returns from India \u2014 Reuters",
    "South Korea exam minister quits over AI cheating scandal \u2014 AP",
    "Denmark to propose mobile phone ban in schools in 2027 \u2014 Reuters",
    "Istanbul: thousands march against the S\u00f6zc\u00fc TV seizure \u2014 AP",
    "China warns citizens off Mount Fuji; $75,000 reward for a missing climber \u2014 Reuters",
    "Delta outages in Atlanta; US intel chief warns of more tech failures \u2014 AP",
    "Pacific despair at COP flop; Bowen told to quit \u2014 Reuters",
    "Venezuela workers strike over pay \u2014 AP",
    "Pope hit by a rosary in Peru, jokes it off \u2014 AP",
    "Lula backs S\u00e1nchez in Spain's snap vote \u2014 Reuters",
    "Fiji edge Italy 21-16 for a first Nations Championship win \u2014 AP",
    "Anthropic -8.5% after IPO; Nvidia -14% on Friday \u2014 AP",
    "Skubal: 9-year, $450m Mets deal, largest ever for a pitcher \u2014 AP",
    "Singapore PM visits Canberra; Wong to defend US alliance \u2014 SMH",
    "Goldblum honoured at the Marrakech Film Festival \u2014 AP",
    "Trump open to capping credit-card interest rates \u2014 Fox News",
    "Taiwan warns Canada on China trade; Pentagon presses Ottawa \u2014 Reuters",
    "Guterres urges greater AI regulation at Barbados summit \u2014 UN News",
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

TAG_COLOUR = {"CONFIRMED": TAG_CONFIRMED, "CLAIM": TAG_CLAIM,
              "REPORTED": TAG_REPORTED}

# ------------------------------------------------------------- layout
def tag_colour(tag):
    return TAG_COLOUR[tag]


def build():
    img = Img(W, H, PAPER)
    # Top navy strip
    img.fill_rect(0, 0, W, 25, NAVY)
    sz = fit_size(TOP_STRIP, 13, 990)
    draw_text(img, W / 2, 6, TOP_STRIP, sz, WHITE, 1.2, "center")
    # Title
    sz = fit_size(TITLE, 68, 990)
    draw_text(img, W / 2, 22, TITLE, sz, INK, 1.3, "center")
    # Subtitle
    sz = fit_size(SUBTITLE, 26, 990)
    draw_text(img, W / 2, 100, SUBTITLE, sz, INK, 1.3, "center")
    # Red sub-line
    sz = fit_size(RED_LINE, 17.5, 990)
    draw_text(img, W / 2, 126, RED_LINE, sz, RED, 1.2, "center")
    # Day in numbers
    cell_w = W / 6.0
    for i, (num, lab) in enumerate(NUMBERS):
        cx = cell_w * i + cell_w / 2.0
        draw_text(img, cx, 144, num, 34, INK, 1.3, "center")
        lsz = fit_size(lab, 11, cell_w - 12)
        draw_text(img, cx, 180, lab, lsz, INK_SOFT, 1.2, "center")
        if i:
            img.fill_rect(int(cell_w * i) - 1, 142, 1, 46, RULE)
    img.fill_rect(16, 192, 992, 1, RULE)
    # Region tally strip, centred, segments in region colours
    tally_size = 12.5
    parts = []
    total_w = 0.0
    for name, n in REGIONS:
        seg = "%s %d" % (name, n)
        parts.append(seg)
        total_w += text_width(seg, tally_size)
    sep = " \u00b7 "
    total_w += text_width(sep, tally_size) * (len(parts) - 1)
    while total_w > 990 and tally_size > 9:
        tally_size -= 0.5
        total_w = sum(text_width(p, tally_size) for p in parts) + \
            text_width(sep, tally_size) * (len(parts) - 1)
    x = (W - total_w) / 2.0
    for j, (name, n) in enumerate(REGIONS):
        seg = parts[j]
        draw_text(img, x, 195, seg, tally_size, REGION_COLOURS[name], 1.3)
        x += text_width(seg, tally_size)
        if j < len(parts) - 1:
            draw_text(img, x, 195, sep, tally_size, GREY, 1.0)
            x += text_width(sep, tally_size)
    # Timeline strip
    tl_size = 12.5
    tl_full = "THE DAY IN UTC"
    for t, txt in TIMELINE:
        tl_full += " \u00b7 " + t + " " + txt
    while text_width(tl_full, tl_size) > 990 and tl_size > 9:
        tl_size -= 0.5
    x = (W - text_width(tl_full, tl_size)) / 2.0
    draw_text(img, x, 211, "THE DAY IN UTC", tl_size, RED, 1.3)
    x += text_width("THE DAY IN UTC", tl_size)
    for t, txt in TIMELINE:
        draw_text(img, x, 211, " \u00b7 ", tl_size, GREY, 1.0)
        x += text_width(" \u00b7 ", tl_size)
        draw_text(img, x, 211, t, tl_size, RED, 1.3)
        x += text_width(t, tl_size)
        draw_text(img, x, 211, " " + txt, tl_size, INK, 1.0)
        x += text_width(" " + txt, tl_size)
    img.fill_rect(16, 227, 992, 1, RULE)
    # 3 lead cards
    for ci, lead in enumerate(LEADS):
        col_x = 16 + ci * 332
        if ci:
            img.fill_rect(col_x - 2, 232, 1, 236, RULE)
        lead["draw"](img, col_x + 14, 230, 300, 105)
        tag = lead["tag"]
        tag_w = text_width(tag, 9.5, 0.0) + 14
        kicker_max = 320 - tag_w - 8
        ksz = fit_size(lead["kicker"], 9.5, kicker_max)
        draw_text(img, col_x + 14, 340, lead["kicker"], ksz, INK, 1.2)
        img.fill_rect(col_x + 14 + 320 - tag_w, 338, tag_w, 15,
                      tag_colour(tag))
        draw_text(img, col_x + 14 + 320 - tag_w / 2, 340, tag, 9.5, WHITE,
                  1.3, "center")
        hsize = 25.0
        hlines = wrap_text(lead["headline"], hsize, 320)
        for cand in (24.0, 22.0, 21.0, 20.0):
            if len(hlines) <= 2:
                break
            hsize = cand
            hlines = wrap_text(lead["headline"], hsize, 320)
        if len(hlines) > 2:
            warn("lead %d headline wraps to %d lines" % (lead["n"], len(hlines)))
        y = draw_block(img, col_x + 14, 358, hlines, hsize, INK, 1.3, 26)
        bsize = 11.5
        blines = wrap_text(lead["body"], bsize, 320)
        while len(blines) > 3 and bsize > 10:
            bsize -= 0.5
            blines = wrap_text(lead["body"], bsize, 312)
        if len(blines) > 3:
            warn("lead %d body wraps to %d lines" % (lead["n"], len(blines)))
        draw_block(img, col_x + 14, y + 2, blines, bsize, INK_SOFT, 1.0, 14)
        draw_text(img, col_x + 14, 455, lead["source"], 10, GREY, 1.0)
    # 10 small stories, 2 rows of 5
    for idx, st in enumerate(SMALL):
        row = idx // 5
        col = idx % 5
        x0 = 16 + col * 200
        y0 = 470 + row * 152
        tc = tag_colour(st["tag"])
        img.fill_rect(x0, y0, 192, 11, tc)
        draw_text(img, x0 + 4, y0 + 1, st["label"], 8, WHITE, 1.3)
        draw_text(img, x0 + 188, y0 + 1, st["tag"], 8, WHITE, 1.3, "right")
        THUMB_DRAW[st["n"]](img, x0, y0 + 11, 192, 45)
        ksz = fit_size(st["kicker"], 8.5, 192)
        draw_text(img, x0, y0 + 60, st["kicker"], ksz, INK, 1.2)
        hsize = 15.0
        hlines = wrap_text(st["headline"], hsize, 192)
        for cand in (14.5, 14.0, 13.5, 13.0):
            if len(hlines) <= 2:
                break
            hsize = cand
            hlines = wrap_text(st["headline"], hsize, 192)
        if len(hlines) > 2:
            warn("story %d headline wraps to %d lines"
                 % (st["n"], len(hlines)))
        hy = draw_block(img, x0, y0 + 72, hlines, hsize, INK, 1.3, 17)
        bsize = 10.0
        blines = wrap_text(st["body"], bsize, 192)
        while len(blines) > 3 and bsize > 8.5:
            bsize -= 0.5
            blines = wrap_text(st["body"], bsize, 192)
        if len(blines) > 3:
            warn("story %d body wraps to %d lines" % (st["n"], len(blines)))
        draw_block(img, x0, y0 + 104, blines, bsize, INK_SOFT, 1.0, 11.5)
        draw_text(img, x0, y0 + 138, st["source"], 9.5, RED, 1.0)
    # ALSO heading + 25 one-line entries in 2 columns
    draw_text(img, 16, 775, "ALSO ON MONDAY 23 NOVEMBER \u2014 25 MORE STORIES",
              14, INK, 1.3)
    img.fill_rect(16, 792, 992, 1, RULE)
    for i, entry in enumerate(ALSO):
        col = 0 if i < 13 else 1
        r = i if i < 13 else i - 13
        ex = 16 if col == 0 else 524
        ey = 796 + r * 9.0
        text = "%d. %s" % (14 + i, entry)
        esz = fit_size(text, 9.0, 492)
        draw_text(img, ex, ey, text, esz, INK, 1.0)
    # Bottom band: dotted world map (left) + DATE CHECK box (right)
    draw_text(img, 16, 914, "WHERE IT HAPPENED \u00b7 PINS MATCH STORY NUMBERS",
              11, INK, 1.3)
    dx = 520.0 / 78.0
    dy = 72.0 / 18.0
    for r, row in enumerate(MAP_MASK):
        for c, ch in enumerate(row):
            if ch == "#":
                img.fill_ellipse(16 + c * dx + dx / 2, 928 + r * dy + dy / 2,
                                 1.5, 1.5, MAP_DOT)
    for k, (name, lat, lon, offx, offy) in enumerate(PINS):
        px = 16 + (lon + 180) / 360.0 * 520 + offx
        py = 928 + (75 - lat) / 136.0 * 72 + offy
        img.fill_ellipse(px, py, 6.5, 6.5, RED)
        img.ellipse_outline(px, py, 6.5, 6.5, WHITE, 1)
        draw_text(img, px, py - 5, str(k + 1), 9, WHITE, 1.3, "center")
    img.fill_rect(544, 914, 464, 2, RED)
    img.fill_rect(544, 914, 2, 88, RED)
    img.fill_rect(1006, 914, 2, 88, RED)
    img.fill_rect(544, 1000, 464, 2, RED)
    dc_head = ("DATE CHECK \u2014 left out on purpose: "
               "these happened on other days")
    hsz = fit_size(dc_head, 11, 448)
    draw_text(img, 776, 917, dc_head, hsz, RED, 1.3, "center")
    img.fill_rect(552, 929, 448, 1, RED)
    for i, item in enumerate(DATE_CHECK):
        col = 0 if i < 7 else 1
        r = i if i < 7 else i - 7
        ix = 552 if col == 0 else 784
        iy = 932 + r * 9.8
        isz = fit_size("\u2022 " + item, 9.5, 224)
        draw_text(img, ix, iy, "\u2022 " + item, isz, INK, 1.0)
    # Footer
    draw_text(img, W / 2, 1005,
              "Sources: Reuters, BBC, AP, AFP, Al Jazeera, The Guardian, "
              "UN News, Kyiv Post, gov.uk", 9.5, INK_SOFT, 1.0, "center")
    draw_text(img, W / 2, 1014,
              "CONFIRMED verified by multiple sources \u00b7 CLAIM not "
              "verified \u00b7 REPORTED single-source report \u00b7 Wires "
              "read to press time 23:48 UTC", 9.5, INK_SOFT, 1.0, "center")
    return img


# ------------------------------------------------------------- PNG encoder
def png_bytes(img):
    def chunk(ctype, data):
        out = struct.pack(">I", len(data)) + ctype + data
        out += struct.pack(">I", zlib.crc32(ctype + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    raw = bytearray()
    for y in range(H):
        raw.append(0)
        raw += img.buf[y * W * 3:(y + 1) * W * 3]
    idat = zlib.compress(bytes(raw), 6)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
            chunk(b"IDAT", idat) + chunk(b"IEND", b""))


def main():
    for r in MAP_MASK:
        if len(r) != 78:
            warn("map row length %d, expected 78" % len(r))
    if len(MAP_MASK) != 18:
        warn("map rows %d, expected 18" % len(MAP_MASK))
    img = build()
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "entry.png")
    with open(path, "wb") as f:
        f.write(png_bytes(img))
    n_stories = len(LEADS) + len(SMALL) + len(ALSO)
    n_regions = sum(n for _, n in REGIONS)
    print(path)
    print("stories %d regions %d datecheck %d numbers %d timeline %d pins %d"
          % (n_stories, n_regions, len(DATE_CHECK), len(NUMBERS),
             len(TIMELINE), len(PINS)))
    if WARNINGS:
        print("layout warnings:")
        for wmsg in WARNINGS:
            print(" - " + wmsg)
    else:
        print("no layout warnings")


if __name__ == "__main__":
    main()
