# -*- coding: utf-8 -*-
"""扫描 sections 中的 ASCII 直引号、直角引号与常见 AI 味模板词。"""
import glob
import re
from pathlib import Path

D = Path(r"d:\Finance\AI金融交易综述\sections")
files = [p for p in D.glob("*.tex") if p.name != "references.tex"]

TEMPLATE_WORDS = ["首先", "其次", "最后", "综上所述", "总而言之", "值得注意的是",
                  "综上所述", "赋能", "抓手", "闭环", "生态位", "敬请期待",
                  "让我们", "众所周知", "毫无疑问", "不言而喻"]

tot_dq = tot_sq = tot_corner = 0
for p in files:
    t = p.read_text(encoding="utf-8")
    dq = t.count('"')
    sq = len(re.findall(r"(?<!\\)'", t))
    corner = len(re.findall(r"[「」『』]", t))
    hits = {w: t.count(w) for w in TEMPLATE_WORDS if t.count(w)}
    if dq or sq or corner or hits:
        print(f"{p.name}: \"={dq} '={sq} corners={corner} {hits}")
    tot_dq += dq
    tot_sq += sq
    tot_corner += corner
print(f"--- TOTAL: double={tot_dq} straight_apostrophe={tot_sq} corner={tot_corner} ---")
