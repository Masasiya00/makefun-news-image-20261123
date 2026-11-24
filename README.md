# Monday 23 November 2026 — The World in One Day

[![make.fun · news-image-20261123](https://make.fun/badge/news-image-20261123.svg)](https://make.fun/bounty/news-image-20261123?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261123)
[![rank](https://make.fun/badge/news-image-20261123/Masasiya00/makefun-news-image-20261123/rank.svg)](https://make.fun/bounty/news-image-20261123/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261123)
[![reward](https://make.fun/badge/news-image-20261123/Masasiya00/makefun-news-image-20261123/reward.svg)](https://make.fun/bounty/news-image-20261123?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261123)

One newspaper front page that sums up a single day of world news:
Monday 23 November 2026, in a single 1024×1024 image.

The page carries 38 dated stories across 10 regions — three lead stories
with hand-drawn illustrations, ten smaller stories with thumbnails, 25 more
one-line items, a six-number day-in-numbers strip, a UTC timeline, a dotted
world map with 13 numbered pins, and a DATE CHECK box that lists the big
stories deliberately left out because they happened on other days.

Everything is drawn by `main.py` with the Python standard library only
(no Pillow, no third-party packages, no network at runtime). The program
builds its own rasterizer and PNG encoder, its own stroke-based font, and
all thirteen illustrations from flat colour shapes. Run it with
`MAKEFUN_OUTPUT_DIR=out python3 main.py` and it writes `out/entry.png`;
running it twice gives byte-identical output.

Entry for the bounty at https://make.fun/bounty/news-image-20261123.
