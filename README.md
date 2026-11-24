# Monday 23 November 2026 — in one image

[![make.fun · news-image-20261123](https://make.fun/badge/news-image-20261123.svg)](https://make.fun/bounty/news-image-20261123?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261123)
[![rank](https://make.fun/badge/news-image-20261123/Masasiya00/makefun-news-image-20261123/rank.svg)](https://make.fun/bounty/news-image-20261123/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261123)
[![reward](https://make.fun/badge/news-image-20261123/Masasiya00/makefun-news-image-20261123/reward.svg)](https://make.fun/bounty/news-image-20261123?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261123)

A one-page newspaper front page summing up world news on
[Monday 23 November 2026](https://make.fun/bounty/news-image-20261123):
38 dated stories across 10 regions — COP31 ending with no deal in Antalya,
Ukraine sinking the Russian corvette Merkury off Libya, Democrats winning
258 House seats in Washington — plus a day-in-numbers strip, a UTC timeline,
a dotted world map with 13 numbered pins, and a DATE CHECK box of stories
deliberately left out because they happened on other days.

`main.py` is pure Python 3 stdlib: it draws the whole page with its own
rasterizer and stroke-serif font and writes a deterministic 1024×1024 PNG
to `$MAKEFUN_OUTPUT_DIR/entry.png` (default `/output`).

Run: `MAKEFUN_OUTPUT_DIR=out python3 main.py`
