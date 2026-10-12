# -*- coding: utf-8 -*-
r"""引用自洽检查：正文 \cite 的键集合与 references.tex 的 \bibitem 集合互查。

运行：python check_cites.py
退出码非零表示存在缺引用或孤儿条目。
"""
from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SECTIONS = HERE.parent / "sections"

cited: set[str] = set()
for f in sorted(SECTIONS.glob("*.tex")):
    if f.name == "references.tex":
        continue
    text = f.read_text(encoding="utf-8")
    for m in re.findall(r"\\cite\{([^}]+)\}", text):
        cited |= {k.strip() for k in m.split(",")}

refs_text = (SECTIONS / "references.tex").read_text(encoding="utf-8")
refs = set(re.findall(r"\\bibitem\{([^}]+)\}", refs_text))

missing = sorted(cited - refs)
orphans = sorted(refs - cited)
print(f"正文引用键: {len(cited)}；参考文献条目: {len(refs)}")
print(f"缺引用（cited 但无 bibitem）: {missing if missing else '无'}")
print(f"孤儿条目（bibitem 但未被引用）: {orphans if orphans else '无'}")
sys.exit(1 if (missing or orphans) else 0)