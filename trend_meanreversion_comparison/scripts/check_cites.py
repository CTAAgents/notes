# -*- coding: utf-8 -*-
"""校验正文 \cite 键与登记表的一致性。"""
import re
import glob
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("g", "scripts/gen_refs.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
reg = {s[0] for s in m.S}

used = set()
for f in glob.glob("sections/*.tex"):
    t = Path(f).read_text(encoding="utf-8")
    for mm in re.finditer(r"\\cite\{([^}]*)\}", t):
        for k in mm.group(1).split(","):
            used.add(k.strip())

missing = sorted(used - reg)
unused = sorted(reg - used)
print("cited_keys =", len(used), " registry =", len(reg))
print("MISSING (cited but not in registry):", missing)
print("UNUSED (in registry but not cited):", len(unused))
print(unused)
