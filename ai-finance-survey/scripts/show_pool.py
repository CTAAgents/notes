# -*- coding: utf-8 -*-
"""打印来源池, 便于人工筛选。"""
import json
import sys

pool = json.load(open(r"d:\Finance\AI金融交易综述\outputs\pool.json", encoding="utf-8"))

mode = sys.argv[1] if len(sys.argv) > 1 else "journal"
kw = sys.argv[2].lower() if len(sys.argv) > 2 else None

rows = [x for x in pool if x["kind"] == mode]
if kw:
    rows = [x for x in rows if kw in (x.get("title") or "").lower()]

if mode == "journal":
    rows.sort(key=lambda x: -(x.get("cited_by") or 0))
else:
    rows.sort(key=lambda x: -(int(x.get("year") or 0)))

for i, x in enumerate(rows):
    if mode == "journal":
        cite = x.get("cited_by")
        print(f'{i:3d} | {x.get("year")} | c={cite:<6} | {(x.get("title") or "")[:82]} | {x.get("doi")}')
    else:
        print(f'{i:3d} | {x.get("year")} | {(x.get("title") or "")[:82]} | {x.get("arxiv_id")}')
print(f"--- {len(rows)} rows ---")
