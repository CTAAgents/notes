# -*- coding: utf-8 -*-
"""补跑 arXiv 开放接口（Atom XML 解析），结果合并回 raw_hits.json['arxiv']。
修复点：原 search_lit.py 用 JSON 解析器读取 XML，导致 0 命中。"""
import json, time, urllib.request, urllib.parse, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw_hits.json")

EN_QUERIES = [
    "all:psychoanalysis AND all:finance",
    "all:psychoanalysis AND all:market",
    "all:psychoanalysis AND all:money",
    "all:psychoanalysis AND all:economics",
    "all:emotional AND all:finance",
    "all:unconscious AND all:finance",
    "all:unconscious AND all:market",
    "all:Lacan AND all:economy",
    "all:Lacan AND all:capitalism",
    "all:psychoanalytic AND all:trading",
    "all:gambling AND all:trading",
    "all:trading AND all:emotion",
    "all:investor AND all:psychology",
    "all:behavioral AND all:finance",
    "all:neurofinance",
    "all:herding AND all:market",
    "all:sentiment AND all:market",
    "all:money AND all:psychology",
    "all:financial AND all:anxiety",
    "all:greed AND all:market",
]


def arxiv_raw(query, n=30, retries=3):
    url = ("http://export.arxiv.org/api/query?search_query=" +
           urllib.parse.quote(query) + f"&start=0&max_results={n}")
    last = None
    for _ in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "lit-review/1.0 (mailto:research@example.com)"})
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
            time.sleep(4)
    return {"__error__": last}


def parse_atom(xml):
    out = []
    for entry in xml.split("<entry>")[1:]:
        def grab(tag):
            s = entry.find(f"<{tag}>")
            if s == -1:
                return ""
            s += len(tag) + 2
            e = entry.find(f"</{tag}>", s)
            return entry[s:e].strip()
        title = " ".join(grab("title").split())
        if not title:
            continue
        authors = []
        for a in entry.split("<author>")[1:]:
            s = a.find("<name>"); e = a.find("</name>")
            if s != -1 and e != -1:
                authors.append(a[s + 6:e].strip())
        link = ""
        for m in re.finditer(r'<link[^>]*href="([^"]+)"[^>]*rel="alternate"', entry):
            link = m.group(1)
            break
        if not link:
            link = grab("id")
        out.append({
            "title": title,
            "authors": authors[:8],
            "year": grab("published")[:4] or None,
            "venue": "arXiv",
            "abstract": " ".join(grab("summary").split()),
            "url": link or None,
            "doi": None,
            "source": "arXiv",
        })
    return out


def main():
    with open(RAW, encoding="utf-8") as f:
        data = json.load(f)
    hits = []
    errors = []
    for i, q in enumerate(EN_QUERIES):
        xml = arxiv_raw(q)
        if isinstance(xml, dict):
            errors.append({"query": q, "error": xml["__error__"]})
            print(f"[{i+1}/{len(EN_QUERIES)}] ERR {q} -> {xml['__error__']}", flush=True)
        else:
            items = parse_atom(xml)
            for it in items:
                it["query"] = q
            hits.extend(items)
            print(f"[{i+1}/{len(EN_QUERIES)}] OK {q} -> {len(items)}", flush=True)
        time.sleep(3.2)
    data["arxiv"] = hits + errors
    data["arxiv_note"] = ("arXiv 接口返回 Atom XML；本轮已按 XML 解析。"
                          "命中仅代表标题/摘要含检索短语，标题相关不代表主题相关，引用前需人工核验。")
    with open(RAW, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"SAVED. arxiv hits={len(hits)} errors={len(errors)}")


if __name__ == "__main__":
    main()