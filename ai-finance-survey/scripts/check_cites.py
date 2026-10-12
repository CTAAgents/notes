# -*- coding: utf-8 -*-
"""核验引用完整性: 正文 \cite 与 references \bibitem 是否一一对应。"""
import re
from pathlib import Path

SEC = Path(r"d:\Finance\AI金融交易综述\sections")
cited = set()
for p in SEC.glob("*.tex"):
    if p.name in {"references.tex", "evidence.tex"}:
        continue
    t = p.read_text(encoding="utf-8")
    for m in re.finditer(r"\\cite\{([^}]+)\}", t):
        for k in m.group(1).split(","):
            cited.add(k.strip())

bib = set()
rb = (SEC / "references.tex").read_text(encoding="utf-8")
for m in re.finditer(r"\\bibitem\{([^}]+)\}", rb):
    bib.add(m.group(1).strip())

print(f"正文引用键: {len(cited)}")
print(f"参考文献条目: {len(bib)}")
print("\n[孤儿条目] 在参考文献但未被正文引用:")
for k in sorted(bib - cited):
    print("  -", k)
print("\n[悬空引用] 被正文引用但无参考文献条目:")
for k in sorted(cited - bib):
    print("  -", k)
