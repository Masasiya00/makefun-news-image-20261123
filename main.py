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
BLACK = (0, 0, 0)
TAGC = {"CONFIRMED": GREEN, "CLAIM": RED, "REPORTED": (90, 86, 78)}
REGC = {"EUROPE": NAVY, "MIDDLE EAST": AMBER, "NORTH AMERICA": GREEN,
        "SOUTH AMERICA": PURPLE, "EAST ASIA": PINK, "SOUTH ASIA": TEAL,
        "SOUTHEAST ASIA": LIME, "AFRICA": RED, "OCEANIA": SKY, "WORLD": INK}


def new_canvas(w, h, rgb):
    buf = bytearray(w * h * 3)
    r, g, b = rgb
    for i in range(0, len(buf), 3):
        buf[i] = r
        buf[i + 1] = g
        buf[i + 2] = b
    return buf


def _set(b, bw, bh, x, y, rgb):
    if 0 <= x < bw and 0 <= y < bh:
        o = (y * bw + x) * 3
        b[o] = rgb[0]
        b[o + 1] = rgb[1]
        b[o + 2] = rgb[2]


def fill_rect(b, bw, bh, x, y, w, h, rgb):
    x0 = max(0, int(x))
    y0 = max(0, int(y))
    x1 = min(bw, int(x + w))
    y1 = min(bh, int(y + h))
    r, g, bl = rgb
    for yy in range(y0, y1):
        base = yy * bw * 3
        for xx in range(x0, x1):
            o = base + xx * 3
            b[o] = r
            b[o + 1] = g
            b[o + 2] = bl


def fill_ellipse(b, bw, bh, cx, cy, rx, ry, rgb):
    if rx <= 0 or ry <= 0:
        return
    r, g, bl = rgb
    for y in range(max(0, cy - ry), min(bh, cy + ry + 1)):
        dy = (y - cy) / ry
        rem = 1.0 - dy * dy
        if rem < 0:
            continue
        dx = rx * math.sqrt(rem)
        xa = max(0, int(math.ceil(cx - dx)))
        xb = min(bw - 1, int(math.floor(cx + dx)))
        base = y * bw * 3
        for x in range(xa, xb + 1):
            o = base + x * 3
            b[o] = r
            b[o + 1] = g
            b[o + 2] = bl


def fill_poly(b, bw, bh, pts, rgb):
    if len(pts) < 3:
        return
    ys = [p[1] for p in pts]
    lo = max(0, int(math.floor(min(ys))))
    hi = min(bh - 1, int(math.ceil(max(ys))))
    n = len(pts)
    r, g, bl = rgb
    for y in range(lo, hi + 1):
        yc = y + 0.5
        xs = []
        for i in range(n):
            ax, ay = pts[i]
            bx, by = pts[(i + 1) % n]
            if (ay <= yc < by) or (by <= yc < ay):
                t = (yc - ay) / (by - ay)
                xs.append(ax + t * (bx - ax))
        xs.sort()
        base = y * bw * 3
        for k in range(0, len(xs) - 1, 2):
            xa = max(0, int(math.ceil(xs[k])))
            xb = min(bw - 1, int(math.floor(xs[k + 1])))
            for x in range(xa, xb + 1):
                o = base + x * 3
                b[o] = r
                b[o + 1] = g
                b[o + 2] = bl


def line(b, bw, bh, x0, y0, x1, y1, rgb):
    x0 = int(round(x0))
    y0 = int(round(y0))
    x1 = int(round(x1))
    y1 = int(round(y1))
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        _set(b, bw, bh, x0, y0, rgb)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def polyline(b, bw, bh, pts, width, rgb):
    if len(pts) < 2:
        return
    half = width / 2.0
    for i in range(len(pts) - 1):
        ax, ay = pts[i]
        bx, by = pts[i + 1]
        dx = bx - ax
        dy = by - ay
        ln = math.hypot(dx, dy)
        if ln == 0:
            continue
        nx = -dy / ln * half
        ny = dx / ln * half
        fill_poly(b, bw, bh,
                  [(ax + nx, ay + ny), (bx + nx, by + ny),
                   (bx - nx, by - ny), (ax - nx, ay - ny)], rgb)
    rad = max(1, int(math.ceil(half)))
    for (px, py) in pts:
        fill_ellipse(b, bw, bh, int(round(px)), int(round(py)), rad, rad, rgb)


def ellipse_outline(b, bw, bh, cx, cy, rx, ry, rgb, width=1):
    steps = 64
    prev = None
    for i in range(steps + 1):
        a = 2.0 * math.pi * i / steps
        p = (cx + rx * math.cos(a), cy + ry * math.sin(a))
        if prev is not None:
            if width <= 1:
                line(b, bw, bh, prev[0], prev[1], p[0], p[1], rgb)
            else:
                polyline(b, bw, bh, [prev, p], width, rgb)
        prev = p


def paste(dst, dbw, dbh, src, sw, sh, dx, dy):
    for y in range(sh):
        ty = dy + y
        if ty < 0 or ty >= dbh:
            continue
        for x in range(sw):
            tx = dx + x
            if tx < 0 or tx >= dbw:
                continue
            so = (y * sw + x) * 3
            do = (ty * dbw + tx) * 3
            dst[do] = src[so]
            dst[do + 1] = src[so + 1]
            dst[do + 2] = src[so + 2]


def _png_chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data +
            struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def encode_png(buf, w, h):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += buf[y * w * 3:(y + 1) * w * 3]
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr) +
            _png_chunk(b"IDAT", zlib.compress(bytes(raw), 6)) +
            _png_chunk(b"IEND", b""))

GL = {
 "A": [((1, 12), (6, 2), (11, 12)), ((3, 9), (9, 9))],
 "B": [((1, 2), (1, 12), (9, 12), (11, 10), (11, 8), (9, 7), (1, 7)),
       ((1, 2), (9, 2), (11, 4), (11, 6), (9, 7))],
 "C": [((11, 3), (9, 2), (3, 2), (1, 4), (1, 10), (3, 12), (9, 12), (11, 10))],
 "D": [((1, 2), (1, 12), (8, 12), (11, 9), (11, 5), (8, 2), (1, 2))],
 "E": [((11, 2), (1, 2), (1, 12), (11, 12)), ((1, 7), (8, 7))],
 "F": [((11, 2), (1, 2), (1, 12)), ((1, 7), (8, 7))],
 "G": [((11, 3), (9, 2), (3, 2), (1, 4), (1, 10), (3, 12), (9, 12),
        (11, 10), (11, 7), (7, 7))],
 "H": [((1, 2), (1, 12)), ((11, 2), (11, 12)), ((1, 7), (11, 7))],
 "I": [((5, 2), (5, 12)), ((2, 2), (8, 2)), ((2, 12), (8, 12))],
 "J": [((10, 2), (10, 11), (8, 12), (4, 12), (2, 10))],
 "K": [((1, 2), (1, 12)), ((10, 2), (1, 7)), ((4, 6), (11, 12))],
 "L": [((1, 2), (1, 12), (11, 12))],
 "M": [((1, 12), (1, 2), (6, 8), (11, 2), (11, 12))],
 "N": [((1, 12), (1, 2), (11, 12), (11, 2))],
 "O": [((6, 2), (10, 3), (11, 6), (11, 9), (9, 12), (3, 12),
        (1, 9), (1, 5), (3, 2), (6, 2))],
 "P": [((1, 12), (1, 2), (9, 2), (11, 4), (11, 6), (9, 8), (1, 7))],
 "Q": [((6, 2), (10, 3), (11, 6), (11, 9), (9, 12), (3, 12),
        (1, 9), (1, 5), (3, 2), (6, 2)), ((8, 10), (12, 14))],
 "R": [((1, 12), (1, 2), (9, 2), (11, 4), (11, 6), (9, 8), (1, 7)),
       ((5, 7), (11, 12))],
 "S": [((11, 3), (9, 2), (3, 2), (1, 4), (1, 6), (3, 8), (9, 8),
        (11, 10), (11, 11), (9, 12), (3, 12), (1, 11))],
 "T": [((1, 2), (11, 2)), ((6, 2), (6, 12))],
 "U": [((1, 2), (1, 10), (3, 12), (9, 12), (11, 10), (11, 2))],
 "V": [((1, 2), (6, 12), (11, 2))],
 "W": [((1, 2), (3, 12), (6, 7), (9, 12), (11, 2))],
 "X": [((1, 2), (11, 12)), ((11, 2), (1, 12))],
 "Y": [((1, 2), (6, 7), (11, 2)), ((6, 7), (6, 12))],
 "Z": [((1, 2), (11, 2), (1, 12), (11, 12))],
 "a": [((10, 5), (10, 12)), ((1, 8), (3, 6), (8, 5), (10, 7),
        (10, 11), (8, 12), (3, 12), (1, 10), (1, 8))],
 "b": [((1, 2), (1, 12)), ((1, 8), (4, 5), (8, 5), (10, 7),
        (10, 10), (8, 12), (4, 12), (1, 10))],
 "c": [((10, 6), (8, 5), (3, 5), (1, 7), (1, 10), (3, 12), (8, 12), (10, 11))],
 "d": [((11, 2), (11, 12)), ((1, 8), (4, 5), (8, 5), (10, 7),
        (10, 10), (8, 12), (4, 12), (1, 10))],
 "e": [((10, 11), (8, 12), (3, 12), (1, 10), (1, 7), (3, 5), (8, 5),
        (10, 7), (10, 8), (1, 8))],
 "f": [((9, 2), (7, 2), (5, 3), (5, 12)), ((2, 6), (8, 6))],
 "g": [((10, 5), (10, 15), (8, 16), (4, 16), (2, 14)),
       ((1, 8), (3, 5), (8, 5), (10, 7), (10, 10), (8, 12), (4, 12), (1, 10))],
 "h": [((1, 2), (1, 12)), ((1, 8), (3, 5), (8, 5), (10, 7), (10, 12))],
 "i": [((2, 5), (2, 12)), ((2, 2), (2, 3))],
 "j": [((4, 5), (4, 14), (2, 16), (0, 16)), ((4, 2), (4, 3))],
 "k": [((1, 2), (1, 12)), ((9, 5), (1, 8)), ((3, 7), (9, 12))],
 "l": [((2, 2), (2, 12))],
 "m": [((1, 12), (1, 5), (4, 5), (6, 7), (6, 12)),
       ((6, 7), (8, 5), (11, 5), (11, 12))],
 "n": [((1, 12), (1, 5), (3, 5), (8, 5), (10, 7), (10, 12))],
 "o": [((6, 5), (9, 6), (10, 8), (10, 10), (8, 12), (4, 12),
        (2, 10), (2, 8), (4, 5), (6, 5))],
 "p": [((1, 5), (1, 16)), ((1, 8), (4, 5), (8, 5), (10, 7),
        (10, 10), (8, 12), (4, 12), (1, 10))],
 "q": [((11, 5), (11, 16)), ((1, 8), (3, 5), (8, 5), (10, 7),
        (10, 10), (8, 12), (4, 12), (1, 10))],
 "r": [((1, 12), (1, 5)), ((1, 7), (3, 5), (7, 5), (9, 7))],
 "s": [((10, 6), (8, 5), (4, 5), (2, 7), (2, 8), (4, 9), (8, 9),
        (10, 11), (10, 12), (8, 12), (4, 12), (2, 11))],
 "t": [((5, 2), (5, 12)), ((2, 6), (8, 6)), ((4, 12), (7, 12))],
 "u": [((1, 5), (1, 11), (3, 12), (8, 12), (10, 11), (10, 5))],
 "v": [((1, 5), (5, 12), (9, 5))],
 "w": [((1, 5), (3, 12), (5, 8), (7, 12), (9, 5))],
 "x": [((1, 5), (9, 12)), ((9, 5), (1, 12))],
 "y": [((1, 5), (5, 11), (9, 5)), ((5, 11), (5, 15), (3, 16))],
 "z": [((1, 5), (9, 5), (1, 12), (9, 12))],
 "0": [((6, 2), (10, 3), (11, 6), (11, 9), (9, 12), (3, 12),
        (1, 9), (1, 5), (3, 2), (6, 2))],
 "1": [((4, 2), (4, 12)), ((2, 4), (4, 2)), ((2, 12), (7, 12))],
 "2": [((1, 4), (3, 2), (8, 2), (10, 4), (10, 6), (2, 12), (11, 12))],
 "3": [((1, 3), (3, 2), (8, 2), (10, 4), (10, 6), (8, 7), (6, 7)),
       ((6, 7), (9, 7), (11, 9), (11, 11), (9, 12), (3, 12), (1, 11))],
 "4": [((8, 2), (8, 12)), ((1, 8), (9, 8)), ((8, 2), (1, 9))],
 "5": [((11, 2), (1, 2), (1, 7), (8, 7), (10, 9), (10, 11), (8, 12), (2, 12))],
 "6": [((10, 3), (8, 2), (3, 2), (1, 5), (1, 10), (3, 12), (8, 12),
        (10, 10), (10, 8), (8, 7), (4, 7), (2, 9))],
 "7": [((1, 2), (11, 2), (5, 12))],
 "8": [((4, 2), (8, 2), (10, 4), (10, 6), (8, 8), (10, 10), (10, 11),
        (8, 12), (4, 12), (2, 11), (2, 10), (4, 8), (2, 6), (2, 4), (4, 2))],
 "9": [((2, 11), (4, 12), (9, 12), (11, 10), (11, 4), (9, 2), (4, 2),
        (2, 4), (2, 7), (4, 9), (9, 9), (11, 7))],
 ".": [((1, 11), (3, 12))],
 ",": [((3, 11), (3, 12)), ((3, 12), (1, 15))],
 ":": [((2, 5), (2, 6)), ((2, 11), (2, 12))],
 ";": [((2, 5), (2, 6)), ((2, 11), (2, 12)), ((2, 12), (0, 15))],
 "'": [((3, 2), (2, 5))],
 '"': [((1, 2), (0, 5)), ((5, 2), (4, 5))],
 "\u2013": [((1, 7), (11, 7))],
 "\u2014": [((0, 7), (12, 7))],
 "\u00b7": [((1, 7), (3, 8))],
 "%": [((1, 2), (11, 12)), ((2, 2), (6, 2), (6, 6), (2, 6), (2, 2)),
       ((6, 8), (10, 8), (10, 12), (6, 12), (6, 8))],
 "(": [((8, 2), (4, 5), (3, 7), (4, 10), (8, 12))],
 ")": [((2, 2), (6, 5), (7, 7), (6, 10), (2, 12))],
 "/": [((8, 2), (2, 12))],
 "&": [((10, 3), (8, 2), (4, 2), (2, 5), (2, 7), (5, 9), (11, 12)),
       ((4, 9), (8, 9))],
 "!": [((2, 2), (2, 9)), ((2, 11), (2, 12))],
 "?": [((2, 4), (4, 2), (8, 2), (10, 4), (10, 6), (8, 8), (6, 8)),
       ((6, 11), (6, 12))],
 "+": [((1, 7), (11, 7)), ((6, 2), (6, 12))],
 "=": [((1, 5), (11, 5)), ((1, 9), (11, 9))],
 "$": [((6, 1), (6, 13)), ((10, 4), (8, 2), (4, 2), (2, 4), (2, 6),
        (4, 7), (8, 7), (10, 9), (10, 11), (8, 12), (4, 12), (2, 10))],
 "-": [((1, 7), (11, 7))],
 "_": [((1, 12), (11, 12))],
 "*": [((6, 2), (6, 12)), ((1, 4), (11, 10)), ((11, 4), (1, 10))],
 "<": [((10, 2), (2, 7), (10, 12))],
 ">": [((2, 2), (10, 7), (2, 12))],
 "[": [((9, 2), (3, 2), (3, 12), (9, 12))],
 "]": [((3, 2), (9, 2), (9, 12), (3, 12))],
 "#": [((4, 2), (4, 12)), ((8, 2), (8, 12)), ((1, 5), (11, 5)), ((1, 9), (11, 9))],
}
ADV = {" ": 4, "i": 5, "l": 5, "j": 6, ".": 4.5, ",": 4.5, ":": 4.5, ";": 4.5,
       "!": 4.5, "'": 4.5, "\u00b7": 4.5, "f": 8, "t": 7.5, "r": 8,
       "(": 6.5, ")": 6.5, "-": 8.5, "/": 6.5, '"': 6.5, "M": 10.5,
       "W": 10.5, "I": 7.5, "J": 9, "m": 9.5, "w": 8.5, "%": 10.5,
       "\u2014": 10, "\u2013": 9, "$": 9.5, "&": 10.5, "#": 10.5, "1": 7,
       "a": 9, "b": 9.5, "c": 9, "d": 9.5, "e": 9, "g": 9, "h": 9, "k": 8.5,
       "n": 9, "o": 9, "p": 9.5, "q": 9.5, "s": 9, "u": 9, "v": 8.5,
       "x": 8.5, "y": 8.5, "z": 8.5}
ACC = {"\u00dc": ("U", "uml"), "\u00e9": ("e", "acu"), "\u00e1": ("a", "acu"),
       "\u00ed": ("i", "acu"), "\u00f6": ("o", "uml"), "\u00e7": ("c", "ced"),
       "\u00f1": ("n", "til"), "\u00e0": ("a", "grv")}
ACCST = {"uml": [((3, 0), (4, 1)), ((8, 0), (9, 1))],
         "acu": [((8, 0), (10, 3))], "grv": [((4, 0), (2, 3))],
         "til": [((3, 2), (5, 0), (7, 2), (9, 0))],
         "ced": [((6, 12), (5, 15), (7, 16))]}


def _adv(ch):
    return ADV.get(ch, 9.5)


def _strokes(ch):
    if ch in GL:
        return GL[ch]
    if ch in ACC:
        base, kind = ACC[ch]
        return GL[base] + ACCST[kind]
    return []


def text_width(t, size, tracking=0.0):
    sc = size / 16.0
    tot = 0.0
    for ch in t:
        tot += _adv(ch) * sc
    if len(t) > 1:
        tot += tracking * (len(t) - 1)
    return tot


def _alpha_poly(ab, aw, ah, pts):
    if len(pts) < 3:
        return
    ys = [p[1] for p in pts]
    lo = max(0, int(math.floor(min(ys))))
    hi = min(ah - 1, int(math.ceil(max(ys))))
    n = len(pts)
    for y in range(lo, hi + 1):
        yc = y + 0.5
        xs = []
        for i in range(n):
            ax, ay = pts[i]
            bx, by = pts[(i + 1) % n]
            if (ay <= yc < by) or (by <= yc < ay):
                tt = (yc - ay) / (by - ay)
                xs.append(ax + tt * (bx - ax))
        xs.sort()
        base = y * aw
        for k in range(0, len(xs) - 1, 2):
            xa = max(0, int(math.ceil(xs[k])))
            xb = min(aw - 1, int(math.floor(xs[k + 1])))
            for x in range(xa, xb + 1):
                v = ab[base + x] + 255
                ab[base + x] = 255 if v > 255 else v


def _alpha_disc(ab, aw, ah, cx, cy, rad):
    if rad <= 0:
        return
    for y in range(max(0, cy - rad), min(ah, cy + rad + 1)):
        dy = (y - cy) / rad
        rem = 1.0 - dy * dy
        if rem < 0:
            continue
        dx = int(rad * math.sqrt(rem))
        base = y * aw
        for x in range(max(0, cx - dx), min(aw - 1, cx + dx) + 1):
            ab[base + x] = 255


def _alpha_stroke(ab, aw, ah, pts, half):
    for i in range(len(pts) - 1):
        ax, ay = pts[i]
        bx, by = pts[i + 1]
        dx = bx - ax
        dy = by - ay
        ln = math.hypot(dx, dy)
        if ln == 0:
            continue
        nx = -dy / ln * half
        ny = dx / ln * half
        _alpha_poly(ab, aw, ah, [(ax + nx, ay + ny), (bx + nx, by + ny),
                                 (bx - nx, by - ny), (ax - nx, ay - ny)])
    rad = max(1, int(math.ceil(half)))
    for (px, py) in pts:
        _alpha_disc(ab, aw, ah, int(round(px)), int(round(py)), rad)


def draw_text(b, bw, bh, x, y, t, size, rgb, weight=1.0, align="left",
              tracking=0.0):
    if not t:
        return 0.0
    wpx = text_width(t, size, tracking)
    if align == "center":
        x = x - wpx / 2.0
    elif align == "right":
        x = x - wpx
    sc = size / 16.0
    ss = 4
    mg = 2.0
    aw = int((wpx + 2 * mg) * ss) + 4
    ah = int((size + 2 * mg) * ss) + 4
    ab = bytearray(aw * ah)
    half = max(1.0, 0.55 * sc * ss * weight)
    cx = mg
    for ch in t:
        for stroke in _strokes(ch):
            pts = [((cx + gx * sc * 0.75) * ss, (mg + gy * sc) * ss)
                   for (gx, gy) in stroke]
            _alpha_stroke(ab, aw, ah, pts, half)
        cx += _adv(ch) * sc + tracking
    r, g, bl = rgb
    ox0 = int(math.floor(x))
    oy0 = int(math.floor(y))
    outw = int(math.ceil(wpx)) + 2
    outh = int(math.ceil(size)) + 2
    for oy in range(outh):
        ay0 = int(round((oy + oy0 - y + mg) * ss))
        for ox in range(outw):
            ax0 = int(round((ox + ox0 - x + mg) * ss))
            tot = 0
            for yy in range(4):
                yy2 = ay0 + yy
                if yy2 < 0 or yy2 >= ah:
                    continue
                row = yy2 * aw
                for xx in range(4):
                    xx2 = ax0 + xx
                    if 0 <= xx2 < aw:
                        tot += ab[row + xx2]
            a = tot // 16
            if a == 0:
                continue
            tx = ox0 + ox
            ty = oy0 + oy
            if 0 <= tx < bw and 0 <= ty < bh:
                o = (ty * bw + tx) * 3
                b[o] = (r * a + b[o] * (255 - a)) // 255
                b[o + 1] = (g * a + b[o + 1] * (255 - a)) // 255
                b[o + 2] = (bl * a + b[o + 2] * (255 - a)) // 255
    return wpx


def fit_size(t, start, maxw, floor=6.0, tracking=0.0):
    s = start
    while s > floor and text_width(t, s, tracking) > maxw:
        s -= 0.5
    return s


def wrap_text(t, size, maxw, tracking=0.0):
    words = t.split(" ")
    lines = []
    cur = ""
    for wd in words:
        cand = wd if not cur else cur + " " + wd
        if text_width(cand, size, tracking) <= maxw or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def draw_block(b, bw, bh, x, y, lines, size, rgb, weight, leading,
               align="left", tracking=0.0):
    yy = y
    for ln in lines:
        draw_text(b, bw, bh, x, yy, ln, size, rgb, weight, align, tracking)
        yy += leading
    return yy

LEADS = [
    ("COP31 ends with no deal",
     ("1", "ANTALYA, T\u00dcRKIYE", "WORLD", "CLIMATE"),
     "EU + 130 nations reject a text with no fossil-fuel mention \u2014 the "
     "first COP since 2000 to end with no deal. Kurum: "
     "\u201cno agreement on this text.\u201d",
     "CONFIRMED", "UNFCCC / Reuters"),
    ("Ukraine sinks Russian corvette off Libya",
     ("2", "BENGHAZI, LIBYA", "AFRICA", "WAR"),
     "Zelenskyy: 7 naval drones sank the Merkury at Benghazi, 1,500 miles "
     "from the front. A Russian cargo ship was also hit. Libya asks the UN "
     "to investigate.",
     "CONFIRMED", "Reuters / Zelenskyy"),
    ("Democrats win biggest House majority in decades",
     ("3", "WASHINGTON, USA", "NORTH AMERICA", "POLITICS"),
     "Democrats hold at least 258 House seats \u2014 largest in decades. "
     "Trump moves to block oversight with an order limiting Congress\u2019s "
     "access to agency files.",
     "CONFIRMED", "AP / Reuters"),
]

SMALLS = [
    ("14 nations back Myanmar genocide ruling",
     ("4", "THE HAGUE", "WORLD", "WORLD COURT"),
     "14 countries back the ICJ ruling that Myanmar committed genocide. UK "
     "recognises it, sanctions 5 generals.",
     "CONFIRMED", "gov.uk / AP", "ICJ RULING", "court"),
    ("Asian chip stocks slide",
     ("5", "SEOUL", "EAST ASIA", "MARKETS"),
     "Kospi fell as much as 5.8%, closing down 3.3%. Samsung -3.1%, "
     "SK Hynix -2.5%.",
     "CONFIRMED", "AP / Al Jazeera", "KOSPI FALLS", "chart"),
    ("11 killed in Dymer drone strike",
     ("6", "DYMER, UKRAINE", "EUROPE", "WAR"),
     "A drone hit a five-storey block at 5am Sunday. A boy, 7, was pulled "
     "alive after 14 hours; 2 missing.",
     "CONFIRMED", "Reuters / Kyiv Post", "RESCUE IN DYMER", "rescue"),
    ("NATO holds emergency talks on Poland",
     ("7", "BRUSSELS", "EUROPE", "SECURITY"),
     "32 members meet after 3 Russian missiles and a drone entered Poland. "
     "Rutte: NATO will defend every inch.",
     "CONFIRMED", "Reuters / NATO", "NATO TALKS", "nato"),
    ("Iran war: Bahrain hit, blockade vowed",
     ("8", "MANAMA, BAHRAIN", "MIDDLE EAST", "IRAN"),
     "Iran hit a civilian site in Bahrain, 2 hurt, and struck US positions. "
     "Tehran vows to confront a US blockade.",
     "CLAIM", "Reuters / IRGC", "IRAN WAR", "dusk"),
    ('Gaza "toxic" on 99% of land',
     ("9", "GAZA", "MIDDLE EAST", "HEALTH"),
     "Toxic contamination covers more than 99% of Gaza \u2014 air, soil and "
     "water dangerous for decades to come.",
     "CONFIRMED", "Oxfam / Al Jazeera", "TOXIC GAZA", "toxic"),
    ('"El Chapo Isidro" captured',
     ("10", "SINALOA, MEXICO", "NORTH AMERICA", "CRIME"),
     "Fausto Isidro Meza Flores, one of the FBI\u2019s 10 most wanted, "
     "captured in Guasave. 4 soldiers, 7 gunmen killed.",
     "CONFIRMED", "Reuters / FBI", "CAPTURED", "cuffs"),
    ("Ebola response disrupted by fighting",
     ("11", "ITURI, DR CONGO", "AFRICA", "HEALTH"),
     "Heavy fighting near a hospital traps Ebola teams in a maternity ward. "
     "WHO warns the response is disrupted.",
     "CONFIRMED", "WHO / UN News", "EBOLA", "hospital"),
    ("Manchester concert evacuated",
     ("12", "MANCHESTER, UK", "EUROPE"),
     "12,000+ evacuated from a Don Toliver concert after an unknown "
     "substance, believed to be tear gas, was released.",
     "REPORTED", "Police / BBC", "EVACUATED", "concert"),
    ("FBI probes hack of police database",
     ("13", "WASHINGTON, USA", "NORTH AMERICA", "CYBER"),
     "The FBI is investigating an apparent hack of the National Crime "
     "Information Center, the police database.",
     "REPORTED", "FBI / Reuters", "HACK PROBE", "server"),
]

ALSO = [
    ('West Bank: Eisenkot calls settler arson "Jewish terrorism"', "Reuters"),
    ("Israel unity talks end with no deal; Likud and Yashar split", "Reuters"),
    ("NATO intel: Russia plans a nuclear-armed satellite launch this year",
     "German media"),
    ("Denmark: Russia plotted to kill rapper Kyivstoner; 3 stopped",
     "Danish police"),
    ("Tajikistan begins ICC withdrawal during Putin visit", "Reuters"),
    ("Nvidia reinstates Huang as CEO; SEC probe unconfirmed", "Reuters"),
    ("Armenia proposes a new constitution, a step to peace with Azerbaijan",
     "Reuters"),
    ("Bangladesh: Hasina to be jailed if she returns from India", "Reuters"),
    ("South Korea exam minister quits over AI cheating scandal", "AP"),
    ("Denmark to propose mobile phone ban in schools in 2027", "Reuters"),
    ("Istanbul: thousands march against the S\u00f6zc\u00fc TV seizure", "AP"),
    ("China warns citizens off Mount Fuji; $75,000 reward for a missing "
     "climber", "Reuters"),
    ("Delta outages in Atlanta; US intel chief warns of more tech failures",
     "AP"),
    ("Pacific despair at COP flop; Bowen told to quit", "Reuters"),
    ("Venezuela workers strike over pay", "AP"),
    ("Pope hit by a rosary in Peru, jokes it off", "AP"),
    ("Lula backs S\u00e1nchez in Spain\u2019s snap vote", "Reuters"),
    ("Fiji edge Italy 21-16 for a first Nations Championship win", "AP"),
    ("Anthropic -8.5% after IPO; Nvidia -14% on Friday", "AP"),
    ("Skubal: 9-year, $450m Mets deal, largest ever for a pitcher", "AP"),
    ("Singapore PM visits Canberra; Wong to defend US alliance", "SMH"),
    ("Goldblum honoured at the Marrakech Film Festival", "AP"),
    ("Trump open to capping credit-card interest rates", "Fox News"),
    ("Taiwan warns Canada on China trade; Pentagon presses Ottawa", "Reuters"),
    ("Guterres urges greater AI regulation at Barbados summit", "UN News"),
]

DATECHECK = [
    ("186 drones over Kyiv", "Sun 22 Nov"),
    ("Hong Kong turnout 98.79%", "Sun 22 Nov"),
    ("ICJ ruling on Myanmar", "Thu 19 Nov"),
    ("Sparta II ablaze, Gulf of Finland", "Sat 22 Nov"),
    ("Iran hits Bahrain site", "Sat 22 Nov"),
    ("Gaza truck strike, 3 killed", "Sat 22 Nov"),
    ("Kryvyi Rih: child killed", "Sat 22 Nov"),
    ("Verstappen wins Las Vegas GP", "Sat 22 Nov"),
    ("Nigeria boat capsizes, 24 dead", "Fri 21 Nov"),
    ("India 720/9 in Wellington", "Sat 22 Nov"),
    ("Anthropic IPO", "Thu 20 Nov"),
    ("Hegseth in Caracas", "Wed 18 Nov"),
    ("Wembanyama scores 50", "Sat 22 Nov"),
]

NUMBERS = [
    ("258", "HOUSE SEATS"),
    ("11", "KILLED IN DYMER"),
    ("5.8%", "KOSPI FALL, AT WORST"),
    ('99%', 'OF GAZA "TOXIC"'),
    ("14", "NATIONS BACK ICJ RULING"),
    ("7", "NAVAL DRONES SANK MERKURY"),
]

REGIONS = [
    ("EUROPE", 8), ("MIDDLE EAST", 4), ("NORTH AMERICA", 9),
    ("SOUTH AMERICA", 3), ("EAST ASIA", 4), ("SOUTH ASIA", 2),
    ("SOUTHEAST ASIA", 1), ("AFRICA", 3), ("OCEANIA", 3), ("WORLD", 1),
]

TIMELINE = [
    ("01:28", "WOMAN, 79, PULLED ALIVE IN DYMER"),
    ("02:33", "KOSPI SIDECAR HALT, SEOUL"),
    ("05:23", "DYMER TOLL REACHES 11"),
    ("14:43", "14 NATIONS BACK ICJ RULING"),
]

PINS = [
    (36.9, 30.7, -14, -6),
    (32.1, 20.1, -12, 10),
    (38.9, -77.0, 0, 0),
    (52.1, 4.3, -9, -7),
    (37.6, 127.0, 0, 0),
    (50.5, 30.5, 8, -5),
    (50.8, 4.4, 9, 6),
    (26.2, 50.6, 0, 0),
    (31.5, 34.5, 13, 8),
    (25.6, -108.5, 0, 0),
    (1.5, 29.5, 0, 0),
    (53.5, -2.2, -12, -5),
    (38.9, -77.0, 18, 10),
]

MASK = [
    "    #####   ###########  ###                    #########################     ",
    "   ##########################           #### ###############################  ",
    "      ###################          #  ####################################### ",
    "        #################           #######################################   ",
    "         ###############             ########  ######################## #     ",
    "         ############                #######  #######################  #      ",
    "         ######                      ############ ########### ######          ",
    "           ####                     ############### #####   #######           ",
    "                    ##########       #############   ##    #######            ",
    "                     #########         ##########           #  #  #           ",
    "                      #######           ########             #  #  #          ",
    "                       #####             ######                #######        ",
    "                        ###               ####     #           ########       ",
    "                         #                 ##                   ######        ",
    "                         #                  #                    ##      ##   ",
    "                         #                                                #   ",
    "                         #                                                    ",
    "",
]

def ill_cop():
    c = new_canvas(300, 105, (232, 213, 176))
    fill_rect(c, 300, 105, 18, 6, 62, 26, (250, 170, 90))
    fill_rect(c, 300, 105, 18, 6, 62, 10, (120, 70, 160))
    fill_rect(c, 300, 105, 220, 6, 62, 26, (250, 170, 90))
    fill_rect(c, 300, 105, 220, 6, 62, 10, (120, 70, 160))
    line(c, 300, 105, 18, 32, 80, 32, INK)
    line(c, 300, 105, 220, 32, 282, 32, INK)
    fill_ellipse(c, 300, 105, 150, 20, 10, 10, WHITE)
    ellipse_outline(c, 300, 105, 150, 20, 10, 10, INK, 2)
    line(c, 300, 105, 150, 20, 150, 13, INK)
    line(c, 300, 105, 150, 20, 155, 22, INK)
    fl = [(200, 60, 40), (30, 90, 160), (40, 140, 70), (220, 180, 40),
          (150, 60, 150)]
    for i, col in enumerate(fl):
        fx = 96 + i * 22
        fill_rect(c, 300, 105, fx, 10, 14, 9, col)
        line(c, 300, 105, fx + 7, 10, fx + 7, 6, INK)
    fill_rect(c, 300, 105, 0, 40, 300, 18, RED)
    draw_text(c, 300, 105, 150, 41, "NO DEAL", 15, WHITE, 1.3, "center")
    heads = [(35, 66), (85, 66), (135, 66), (185, 66), (235, 66), (275, 66)]
    suits = [(40, 60, 90), (90, 40, 40), (40, 90, 60), (120, 90, 30),
             (60, 60, 60), (90, 40, 90)]
    for (hx, hy), sc_ in zip(heads, suits):
        fill_ellipse(c, 300, 105, hx, hy + 12, 13, 9, sc_)
        fill_ellipse(c, 300, 105, hx, hy, 6, 6, (220, 180, 150))
    fill_rect(c, 300, 105, 8, 76, 284, 22, (120, 90, 55))
    for px in (30, 90, 150, 210, 260):
        fill_rect(c, 300, 105, px, 80, 26, 5, WHITE)
    return c


def ill_merkury():
    c = new_canvas(300, 105, (10, 20, 50))
    fill_rect(c, 300, 105, 0, 55, 300, 50, (8, 32, 72))
    for (sx, sy) in [(20, 10), (55, 22), (90, 8), (130, 16), (170, 6),
                     (205, 20), (240, 8), (285, 24), (150, 30), (40, 32)]:
        fill_rect(c, 300, 105, sx, sy, 2, 2, WHITE)
    fill_ellipse(c, 300, 105, 268, 16, 9, 9, (240, 240, 220))
    fill_ellipse(c, 300, 105, 272, 14, 8, 8, (10, 20, 50))
    fill_ellipse(c, 300, 105, 215, 42, 26, 14, (255, 140, 0))
    fill_ellipse(c, 300, 105, 215, 44, 16, 9, (255, 200, 60))
    fill_poly(c, 300, 105, [(200, 52), (215, 30), (230, 52)], (255, 120, 0))
    fill_poly(c, 300, 105, [(168, 78), (180, 62), (196, 62), (196, 78)],
              (140, 140, 145))
    fill_rect(c, 300, 105, 178, 56, 20, 8, (160, 160, 165))
    line(c, 300, 105, 188, 56, 188, 46, (160, 160, 165))
    fill_poly(c, 300, 105, [(150, 78), (262, 78), (252, 88), (162, 88)],
              (120, 120, 125))
    for bx, by in [(55, 84), (105, 92), (150, 82)]:
        fill_poly(c, 300, 105, [(bx, by), (bx + 16, by), (bx + 12, by + 5),
                                 (bx + 4, by + 5)], WHITE)
        line(c, 300, 105, bx - 8, by + 7, bx + 24, by + 7, (120, 170, 220))
    for wy in (95, 100):
        for wx in range(10, 290, 26):
            line(c, 300, 105, wx, wy, wx + 14, wy, (90, 140, 200))
    return c


def ill_capitol():
    c = new_canvas(300, 105, (190, 220, 240))
    fill_rect(c, 300, 105, 0, 82, 300, 23, (90, 160, 80))
    fill_ellipse(c, 300, 105, 272, 16, 10, 10, (255, 210, 60))
    fill_rect(c, 300, 105, 15, 58, 120, 24, WHITE)
    fill_poly(c, 300, 105, [(15, 58), (135, 58), (75, 44)], WHITE)
    fill_ellipse(c, 300, 105, 75, 44, 22, 12, WHITE)
    fill_rect(c, 300, 105, 72, 28, 6, 8, WHITE)
    fill_rect(c, 300, 105, 78, 24, 10, 6, RED)
    for cx in (28, 52, 76, 100, 124):
        fill_rect(c, 300, 105, cx, 60, 5, 20, (210, 210, 205))
    fill_rect(c, 300, 105, 20, 78, 110, 4, (200, 200, 195))
    draw_text(c, 300, 105, 229, 20, "258", 20, (30, 90, 180), 1.3, "center")
    fill_rect(c, 300, 105, 155, 44, 148, 12, (170, 170, 170))
    fill_rect(c, 300, 105, 155, 44, 88, 12, (30, 90, 180))
    draw_text(c, 300, 105, 229, 60, "HOUSE SEATS", 9, INK, 1.2, "center")
    dl = "DEMOCRATS \u00b7 LARGEST IN DECADES"
    ds = fit_size(dl, 9.5, 146)
    draw_text(c, 300, 105, 229, 72, dl, ds, GREEN, 1.3, "center")
    return c


def ill_thumb(kind):
    c = new_canvas(192, 45, PAPER)
    if kind == "court":
        fill_rect(c, 192, 45, 0, 0, 192, 45, (220, 205, 170))
        fill_poly(c, 192, 45, [(56, 6), (136, 6), (96, 18)], (200, 180, 140))
        for cx in (64, 84, 104, 124):
            fill_rect(c, 192, 45, cx, 18, 6, 18, WHITE)
        fill_rect(c, 192, 45, 56, 36, 80, 4, (180, 160, 120))
        fill_rect(c, 192, 45, 52, 40, 88, 4, (160, 140, 100))
        fill_rect(c, 192, 45, 88, 26, 16, 10, (90, 70, 50))
    elif kind == "chart":
        fill_rect(c, 192, 45, 0, 0, 192, 45, WHITE)
        line(c, 192, 45, 14, 6, 14, 40, INK)
        line(c, 192, 45, 14, 40, 182, 40, INK)
        polyline(c, 192, 45, [(20, 8), (60, 14), (110, 26), (168, 37)], 3, RED)
        fill_poly(c, 192, 45, [(168, 37), (158, 34), (164, 44)], RED)
        draw_text(c, 192, 45, 188, 4, "-5.8%", 12, RED, 1.3, "right")
    elif kind == "rescue":
        fill_rect(c, 192, 45, 0, 0, 192, 45, (40, 40, 50))
        fill_rect(c, 192, 45, 10, 5, 100, 40, (110, 110, 115))
        for wy in (10, 20, 30):
            for wx in (18, 40, 62, 84):
                fill_rect(c, 192, 45, wx, wy, 10, 6, (255, 210, 90))
        fill_ellipse(c, 192, 45, 160, 40, 30, 12, (255, 120, 0))
        fill_ellipse(c, 192, 45, 160, 42, 18, 7, (255, 190, 60))
        line(c, 192, 45, 128, 42, 168, 6, (200, 160, 90))
        line(c, 192, 45, 136, 42, 176, 6, (200, 160, 90))
        for t in (0.25, 0.5, 0.75):
            rx = int(128 + t * 40)
            ry = int(42 - t * 36)
            line(c, 192, 45, rx - 3, ry + 2, rx + 5, ry - 2, (200, 160, 90))
        fill_ellipse(c, 192, 45, 172, 5, 4, 4, (220, 180, 150))
    elif kind == "nato":
        fill_rect(c, 192, 45, 0, 0, 192, 45, (225, 230, 235))
        for fx in (14, 58, 102, 146):
            fill_rect(c, 192, 45, fx, 6, 30, 18, NAVY)
            for k in range(8):
                a = 2.0 * math.pi * k / 8
                dx = int(15 + 9 * math.cos(a))
                dy = int(15 + 6 * math.sin(a))
                fill_rect(c, 192, 45, fx + dx, dy, 2, 2, (255, 220, 60))
        fill_ellipse(c, 192, 45, 96, 34, 22, 9, RED)
        draw_text(c, 192, 45, 96, 28, "32", 12, WHITE, 1.3, "center")
    elif kind == "dusk":
        fill_rect(c, 192, 45, 0, 0, 192, 10, (60, 30, 90))
        fill_rect(c, 192, 45, 0, 10, 192, 10, (150, 60, 120))
        fill_rect(c, 192, 45, 0, 20, 192, 8, (240, 130, 50))
        polyline(c, 192, 45, [(10, 2), (50, 10), (86, 24)], 2, (255, 240, 200))
        polyline(c, 192, 45, [(40, 0), (80, 12), (112, 26)], 2, (255, 180, 90))
        fill_ellipse(c, 192, 45, 86, 24, 3, 3, (255, 240, 200))
        fill_ellipse(c, 192, 45, 112, 26, 3, 3, (255, 180, 90))
        fill_rect(c, 192, 45, 0, 28, 192, 12, (30, 25, 40))
        for bx, bw_ in [(8, 22), (34, 16), (54, 26), (84, 18), (106, 24),
                         (134, 16), (154, 26), (182, 10)]:
            fill_rect(c, 192, 45, bx, 28 - (bw_ // 3), bw_, 12 + bw_ // 3,
                      (25, 20, 35))
        for wx, wy in [(14, 32), (40, 30), (62, 34), (90, 31), (112, 33),
                       (140, 30), (162, 34)]:
            fill_rect(c, 192, 45, wx, wy, 3, 3, (255, 210, 90))
        fill_ellipse(c, 192, 45, 96, 30, 8, 5, (255, 140, 0))
        fill_rect(c, 192, 45, 0, 40, 192, 5, (10, 30, 70))
        fill_poly(c, 192, 45, [(150, 44), (156, 41), (168, 41), (172, 44)],
                  (15, 15, 20))
    elif kind == "toxic":
        fill_rect(c, 192, 45, 0, 0, 192, 45, (140, 120, 70))
        fill_poly(c, 192, 45, [(96, 4), (128, 40), (64, 40)], (250, 210, 40))
        fill_poly(c, 192, 45, [(96, 10), (122, 36), (70, 36)], (245, 190, 20))
        draw_text(c, 192, 45, 96, 14, "!", 18, BLACK, 1.3, "center")
    elif kind == "cuffs":
        fill_rect(c, 192, 45, 0, 0, 192, 45, (30, 30, 38))
        ellipse_outline(c, 192, 45, 70, 18, 20, 13, (200, 200, 205), 4)
        ellipse_outline(c, 192, 45, 122, 18, 20, 13, (200, 200, 205), 4)
        for lx in (88, 94, 100):
            fill_ellipse(c, 192, 45, lx, 18, 3, 3, (180, 180, 185))
        draw_text(c, 192, 45, 96, 33, "FBI TOP 10", 10, WHITE, 1.3, "center")
    elif kind == "hospital":
        fill_rect(c, 192, 45, 0, 0, 192, 45, (235, 240, 235))
        fill_rect(c, 192, 45, 56, 12, 80, 24, WHITE)
        fill_rect(c, 192, 45, 88, 16, 16, 4, RED)
        fill_rect(c, 192, 45, 94, 10, 4, 16, RED)
        fill_rect(c, 192, 45, 56, 36, 80, 3, (180, 180, 180))
        fill_poly(c, 192, 45, [(8, 42), (18, 30), (28, 42)], (40, 140, 90))
        fill_poly(c, 192, 45, [(164, 42), (174, 30), (184, 42)], (200, 80, 40))
        fill_rect(c, 192, 45, 34, 38, 16, 5, (220, 60, 60))
        fill_rect(c, 192, 45, 142, 38, 16, 5, (60, 120, 220))
    elif kind == "concert":
        fill_rect(c, 192, 45, 0, 0, 192, 45, (25, 20, 40))
        for bx, col in [(30, (200, 60, 120)), (70, (60, 160, 220)),
                        (120, (220, 180, 60)), (160, (120, 220, 90))]:
            fill_poly(c, 192, 45, [(bx, 2), (bx + 10, 2), (bx + 22, 30),
                                    (bx - 2, 30)], col)
        fill_rect(c, 192, 45, 56, 28, 80, 6, WHITE)
        for hx in range(8, 188, 12):
            fill_ellipse(c, 192, 45, hx, 42, 4, 4, (15, 12, 25))
    elif kind == "server":
        fill_rect(c, 192, 45, 0, 0, 192, 45, (20, 25, 30))
        for rx in (14, 70, 126):
            fill_rect(c, 192, 45, rx, 6, 52, 28, (50, 55, 60))
            for ry in (10, 18, 26):
                fill_rect(c, 192, 45, rx + 5, ry, 30, 3, (30, 35, 40))
                fill_rect(c, 192, 45, rx + 40, ry, 4, 4, (40, 220, 90))
                fill_rect(c, 192, 45, rx + 46, ry, 3, 3, (230, 200, 60))
        fill_ellipse(c, 192, 45, 184, 6, 4, 4, RED)
        draw_text(c, 192, 45, 96, 35, "NCIC", 10, RED, 1.3, "center")
    return c

WARN = []
TOP = ["THE WORLD IN ONE DAY", "38 STORIES", "10 REGIONS",
       "EVERY ONE DATED MONDAY 23 NOVEMBER 2026"]
TITLE = "Monday 23 November 2026"
SUB = ["No Deal in Antalya", "Corvette Sunk Off Libya",
       "258 Seats in Washington"]
REDLINE = ["COP31 ends with no deal",
           "Ukraine sinks a Russian warship in the Med",
           "Democrats take the House"]
LEAD_ILL = [ill_cop, ill_merkury, ill_capitol]


def draw_pieces(b, xc, y, pieces, size, weight=1.0):
    tot = 0.0
    for (t, _c) in pieces:
        tot += text_width(t, size)
    x = xc - tot / 2.0
    for (t, col) in pieces:
        draw_text(b, W, H, x, y, t, size, col, weight)
        x += text_width(t, size)


def fit_block(b, x, y, text, size, maxw, maxlines, rgb, weight, leading):
    s = size
    while s > 6.0:
        ls = wrap_text(text, s, maxw)
        if len(ls) <= maxlines:
            break
        s -= 0.5
    ls = wrap_text(text, s, maxw)
    if len(ls) > maxlines:
        WARN.append("overflow: " + text[:40])
        ls = ls[:maxlines]
    return draw_block(b, W, H, x, y, ls, s, rgb, weight, leading)


def build():
    b = new_canvas(W, H, PAPER)
    fill_rect(b, W, H, 0, 0, W, 25, NAVY)
    draw_pieces(b, 512, 6, [(TOP[0] + " \u00b7 ", WHITE),
                             (TOP[1] + " \u00b7 ", WHITE),
                             (TOP[2] + " \u00b7 ", WHITE),
                             (TOP[3], WHITE)], 13, 1.2)
    ts = fit_size(TITLE, 68, 990)
    draw_text(b, W, H, 512, 22, TITLE, ts, INK, 1.3, "center")
    sub = " \u00b7 ".join(SUB)
    ss = fit_size(sub, 26, 990)
    draw_text(b, W, H, 512, 100, sub, ss, INK, 1.3, "center")
    rl = " \u00b7 ".join(REDLINE)
    rs = fit_size(rl, 17.5, 990)
    draw_text(b, W, H, 512, 126, rl, rs, RED, 1.2, "center")
    cellw = 992.0 / 6.0
    for i, (num, lab) in enumerate(NUMBERS):
        cx = 16 + cellw * (i + 0.5)
        draw_text(b, W, H, cx, 144, num, 34, INK, 1.3, "center")
        ls = fit_size(lab, 11, cellw - 8)
        draw_text(b, W, H, cx, 180, lab, ls, INK_SOFT, 1.2, "center")
        if i > 0:
            fill_rect(b, W, H, int(16 + cellw * i), 142, 1, 46, RULE)
    fill_rect(b, W, H, 16, 192, 992, 1, RULE)
    pieces = []
    for j, (nm, n) in enumerate(REGIONS):
        if j > 0:
            pieces.append((" \u00b7 ", GREY))
        pieces.append((nm + " " + str(n), REGC[nm]))
    rs = 12.5
    while sum(text_width(t, rs) for (t, _c) in pieces) > 990 and rs > 8:
        rs -= 0.5
    draw_pieces(b, 512, 195, pieces, rs, 1.3)
    tl = [("THE DAY IN UTC", RED)]
    for (tm, tx) in TIMELINE:
        tl.append((" \u00b7 ", GREY))
        tl.append((tm, RED))
        tl.append((" " + tx, INK))
    ts = 12.5
    while sum(text_width(t, ts) for (t, _c) in tl) > 990 and ts > 8:
        ts -= 0.5
    draw_pieces(b, 512, 211, tl, ts, 1.3)
    fill_rect(b, W, H, 16, 227, 992, 1, RULE)
    for i, (head, kick, body, tag, src) in enumerate(LEADS):
        colx = (16, 348, 680)[i]
        if i > 0:
            fill_rect(b, W, H, colx - 2, 232, 1, 236, RULE)
        paste(b, W, H, LEAD_ILL[i](), 300, 105, colx + 14, 230)
        tagw = text_width(tag, 8) + 10
        tagx = colx + 328 - tagw
        fill_rect(b, W, H, int(tagx), 338, int(tagw), 12, TAGC[tag])
        draw_text(b, W, H, tagx + tagw / 2, 339, tag, 8, WHITE, 1.3, "center")
        kt = " \u00b7 ".join(kick)
        ks = fit_size(kt, 9.5, tagx - colx - 6)
        draw_text(b, W, H, colx, 340, kt, ks, INK, 1.2)
        y = fit_block(b, colx, 354, head, 25, 300, 2, INK, 1.3, 26)
        y = fit_block(b, colx, y + 6, body, 11.5, 300, 3, INK_SOFT, 1.0, 14)
        draw_text(b, W, H, colx, y + 4, src, 10, GREY, 1.0)
    for idx, (head, kick, body, tag, src, lab, kind) in enumerate(SMALLS):
        row = idx // 5
        col = idx % 5
        x = 16 + col * 200
        y0 = 470 + row * 152
        fill_rect(b, W, H, x, y0, 192, 11, TAGC[tag])
        draw_text(b, W, H, x + 3, y0 + 1, lab, 8, WHITE, 1.3)
        draw_text(b, W, H, x + 189, y0 + 1, tag, 8, WHITE, 1.3, "right")
        paste(b, W, H, ill_thumb(kind), 192, 45, x, y0 + 11)
        kt = " \u00b7 ".join(kick)
        ks = fit_size(kt, 8.5, 192)
        draw_text(b, W, H, x, y0 + 58, kt, ks, INK, 1.2)
        y = fit_block(b, x, y0 + 68, head, 15, 192, 2, INK, 1.3, 16)
        y = fit_block(b, x, y + 4, body, 10, 192, 3, INK_SOFT, 1.0, 11.5)
        draw_text(b, W, H, x, y + 3, src, 9.5, RED, 1.0)
    draw_text(b, W, H, 16, 775,
              "ALSO ON MONDAY 23 NOVEMBER \u2014 25 MORE STORIES",
              14, INK, 1.3)
    fill_rect(b, W, H, 16, 792, 992, 1, RULE)
    for k, (head, src) in enumerate(ALSO):
        n = 14 + k
        cx = 16 if k < 13 else 524
        ry = 796 + (k if k < 13 else k - 13) * 9.0
        draw_text(b, W, H, cx, ry, str(n) + ". " + head + " \u2014 " + src,
                  9.0, INK, 1.0)
    draw_text(b, W, H, 16, 914,
              "WHERE IT HAPPENED \u00b7 PINS MATCH STORY NUMBERS",
              11, INK, 1.3)
    dx_ = 520.0 / 78.0
    dy_ = 72.0 / 18.0
    for r in range(18):
        row = MASK[r].ljust(78)
        for cc in range(78):
            if row[cc] == "#":
                fill_ellipse(b, W, H, int(16 + (cc + 0.5) * dx_),
                             int(928 + (r + 0.5) * dy_), 1, 1, MAP_DOT)
    for i, (lat, lon, ox, oy) in enumerate(PINS):
        px = 16 + (lon + 180.0) / 360.0 * 520.0 + ox
        py = 928 + (75.0 - lat) / 136.0 * 72.0 + oy
        fill_ellipse(b, W, H, int(px), int(py), 6, 6, RED)
        ellipse_outline(b, W, H, int(px), int(py), 6, 6, WHITE, 1)
        draw_text(b, W, H, px, py - 4, str(i + 1), 9, WHITE, 1.3, "center")
    fill_rect(b, W, H, 544, 914, 464, 2, RED)
    fill_rect(b, W, H, 544, 1000, 464, 2, RED)
    fill_rect(b, W, H, 544, 914, 2, 88, RED)
    fill_rect(b, W, H, 1006, 914, 2, 88, RED)
    dh = "DATE CHECK \u2014 left out on purpose: these happened on other days"
    ds = fit_size(dh, 11, 456)
    draw_text(b, W, H, 776, 918, dh, ds, RED, 1.3, "center")
    fill_rect(b, W, H, 548, 932, 456, 1, RED)
    for k, (tx, day) in enumerate(DATECHECK):
        cx = 550 if k < 7 else 778
        ry = 935 + (k if k < 7 else k - 7) * 9.2
        item = "\u2022 " + tx + " \u2014 " + day
        isz = fit_size(item, 9.5, 224, 8.5)
        draw_text(b, W, H, cx, ry, item, isz, INK, 1.0)
    draw_text(b, W, H, 512, 1003,
              "Sources: Reuters, BBC, AP, AFP, Al Jazeera, The Guardian, "
              "UN News, Kyiv Post, gov.uk", 9.5, INK_SOFT, 1.0, "center")
    draw_text(b, W, H, 512, 1013,
              "CONFIRMED verified by multiple sources \u00b7 CLAIM not "
              "verified \u00b7 REPORTED single-source report \u00b7 Wires "
              "read to press time 23:48 UTC", 9.5, INK_SOFT, 1.0, "center")
    return b


def main():
    img = build()
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "entry.png")
    with open(path, "wb") as f:
        f.write(encode_png(img, W, H))
    print(path)
    print("stories %d regions %d datecheck %d numbers %d timeline %d pins %d"
          % (3 + len(SMALLS) + len(ALSO),
             sum(n for (_nm, n) in REGIONS),
             len(DATECHECK), len(NUMBERS), len(TIMELINE), len(PINS)))
    if WARN:
        for w_ in WARN:
            print("warning: " + w_)
    else:
        print("no layout warnings")


if __name__ == "__main__":
    main()
