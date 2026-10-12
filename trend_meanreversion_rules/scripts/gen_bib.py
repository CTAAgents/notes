# -*- coding: utf-8 -*-
"""从综述的文献登记表生成规则文档的参考文献（仅含被引用的条目）。"""
import glob
import importlib.util
import re
from pathlib import Path

RULES = Path(r"d:\Finance\趋势跟踪与均值回归交易规则")
PAPER_GEN = Path(r"d:\Finance\趋势跟踪与均值回归对比综述\scripts\gen_refs.py")

spec = importlib.util.spec_from_file_location("paper_refs", PAPER_GEN)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
REG = {s[0]: s for s in m.S}

cited = []
for f in glob.glob(str(RULES / "sections" / "*.tex")):
    if Path(f).name == "90_bibliography.tex":
        continue
    t = Path(f).read_text(encoding="utf-8")
    for mm in re.finditer(r"\\cite\{([^}]*)\}", t):
        for k in mm.group(1).split(","):
            k = k.strip()
            if k and k not in cited:
                cited.append(k)

missing = [k for k in cited if k not in REG]
if missing:
    raise SystemExit(f"以下引用键不在登记表中，请先补齐: {missing}")


def esc(s: str) -> str:
    s = s.replace("&", r"\&").replace("_", r"\_").replace("%", r"\%").replace("#", r"\#")
    return s.replace("arXiv:", r"arXiv:\allowbreak ")


lines = [r"\section*{参考文献}", r"\addcontentsline{toc}{section}{参考文献}",
         r"\begin{thebibliography}{99}", r"\small"]
for k in cited:
    _, label, cat, title, author, venue, url, status = REG[k]
    lines.append(f"\\bibitem{{{k}}} {esc(author)}. \\emph{{{esc(title)}}}. "
                 f"{esc(venue)}. \\href{{{url}}}{{{url}}}.")
lines.append(r"\end{thebibliography}")

(RULES / "sections" / "90_bibliography.tex").write_text("\n".join(lines), encoding="utf-8")
print(f"正文引用 {len(cited)} 条；已生成 90_bibliography.tex")