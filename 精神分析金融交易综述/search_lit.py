# -*- coding: utf-8 -*-
"""多源文献检索：Giiisp + arXiv + OpenAlex + Crossref + Semantic Scholar。
只做检索与归一化落盘，不做任何结论推断。"""
import json, time, urllib.request, urllib.parse, sys, os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw_hits.json")

EN_QUERIES = [
    "psychoanalysis and financial markets",
    "emotional finance investor",
    "psychoanalytic study of money",
    "psychoanalysis money defence mechanism",
    "trading psychology emotion regulation",
    "financial markets unconscious",
    "Lacanian psychoanalysis finance market",
    "group psychology stock market investors",
    "gambling addiction trading behavior",
    "behavioral finance emotion risk decision",
    "anxiety financial decision making",
    "loss aversion psychology investor",
    "market sentiment crowd psychology",
    "neurofinance emotion trading",
    "repetition compulsion finance",
    "fantasy financial markets speculation",
    "projective identification organization finance",
    "phased unphased investment emotional finance",
]

CN_QUERIES = [
    "精神分析 金融 市场",
    "情绪金融 投资者",
    "交易心理 精神分析",
    "股市 群体心理 投资",
    "投资者 潜意识 心理",
    "行为金融 情绪 决策",
]

def fetch(url, headers=None, timeout=40):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "lit-review/1.0 (mailto:research@example.com)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        ct = r.headers.get("Content-Type", "")
        raw = r.read()
    return ct, raw.decode("utf-8", "ignore")

def try_json(url, headers=None, timeout=40):
    try:
        ct, txt = fetch(url, headers, timeout)
        return True, json.loads(txt)
    except Exception as e:
        return False, {"error": f"{type(e).__name__}: {e}"}

# ---------- Giiisp ----------
def giiisp(mode, query, page=1, size=10):
    paths = {
        "oa": ("/first/oaPaper/searchArticlesByQuery1", {"titleAndAbs": [query]}),
        "arxiv-title": ("/first/paper/searchArxivByTitle", {"key": query, "pageNum": page, "pageSize": size}),
        "arxiv-abstract": ("/first/paper/searchArxivByAbstract", {"key": query, "pageNum": page, "pageSize": size}),
        "arxiv": ("/first/paper/searchArxiv", {"key": query, "pageNum": page, "pageSize": size}),
    }
    path, body = paths[mode]
    try:
        req = urllib.request.Request("https://giiisp.com" + path,
                                     data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json", "Accept": "application/json"},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}

# ---------- arXiv ----------
def arxiv(query, n=20):
    q = urllib.parse.quote(f'all:"{query}"')
    ok, data = try_json(f"http://export.arxiv.org/api/query?search_query={q}&start=0&max_results={n}")
    if not ok:
        return data
    out = []
    for entry in data.split("<entry>")[1:]:
        def grab(tag):
            s = entry.find(f"<{tag}>")
            if s == -1: return ""
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
                authors.append(a[s+6:e].strip())
        out.append({
            "title": title,
            "authors": authors,
            "year": grab("published")[:4] or None,
            "venue": "arXiv",
            "abstract": " ".join(grab("summary").split()),
            "url": grab("id") or None,
            "doi": None,
            "source": "arXiv",
        })
    return out

# ---------- OpenAlex ----------
def openalex(query, n=25):
    url = ("https://api.openalex.org/works?search=" + urllib.parse.quote(query) +
           f"&per-page={n}&mailto=research@example.com")
    ok, data = try_json(url)
    if not ok:
        return data
    out = []
    for w in data.get("results", []):
        out.append({
            "title": (w.get("title") or "").strip(),
            "authors": [a.get("author", {}).get("display_name") for a in w.get("authorships", [])][:8],
            "year": w.get("publication_year"),
            "venue": (w.get("primary_location") or {}).get("source", {}).get("display_name") if (w.get("primary_location") or {}).get("source") else None,
            "abstract": None,
            "url": w.get("doi") or w.get("id"),
            "doi": (w.get("doi") or "").replace("https://doi.org/", "") or None,
            "citations": w.get("cited_by_count"),
            "source": "OpenAlex",
        })
    return out

# ---------- Crossref ----------
def crossref(query, n=20):
    url = ("https://api.crossref.org/works?query.bibliographic=" + urllib.parse.quote(query) +
           f"&rows={n}&mailto=research@example.com")
    ok, data = try_json(url)
    if not ok:
        return data
    out = []
    for it in data.get("message", {}).get("items", []):
        title = (it.get("title") or [""])[0]
        out.append({
            "title": title.strip(),
            "authors": [f"{a.get('given','')} {a.get('family','')}".strip() for a in it.get("author", [])][:8],
            "year": (it.get("issued", {}).get("date-parts", [[None]])[0] or [None])[0],
            "venue": (it.get("container-title") or [None])[0],
            "abstract": (it.get("abstract") or None),
            "url": it.get("URL"),
            "doi": it.get("DOI"),
            "source": "Crossref",
        })
    return out

# ---------- Semantic Scholar ----------
def s2(query, n=20):
    url = ("https://api.semanticscholar.org/graph/v1/paper/search?query=" + urllib.parse.quote(query) +
           f"&limit={n}&fields=title,authors,year,venue,abstract,externalIds,url,citationCount")
    ok, data = try_json(url)
    if not ok:
        return data
    out = []
    for p in data.get("data", []):
        ext = p.get("externalIds") or {}
        out.append({
            "title": (p.get("title") or "").strip(),
            "authors": [a.get("name") for a in p.get("authors", [])][:8],
            "year": p.get("year"),
            "venue": p.get("venue"),
            "abstract": p.get("abstract"),
            "url": p.get("url"),
            "doi": ext.get("DOI"),
            "citations": p.get("citationCount"),
            "source": "SemanticScholar",
        })
    return out

def main():
    results = {"giiisp": [], "arxiv": [], "openalex": [], "crossref": [], "s2": []}
    # Giiisp 多模式探测
    for m in ["arxiv-title", "arxiv-abstract", "arxiv", "oa"]:
        results["giiisp"].append({"mode": m, "query": "emotional finance", "resp": giiisp(m, "emotional finance")})
        time.sleep(0.5)
    for i, q in enumerate(EN_QUERIES):
        print(f"[{i+1}/{len(EN_QUERIES)}] {q}", flush=True)
        for key, fn in [("arxiv", arxiv), ("openalex", openalex), ("crossref", crossref), ("s2", s2)]:
            r = fn(q)
            if isinstance(r, list):
                for item in r:
                    item["query"] = q
                results[key].extend(r)
            else:
                results[key].append({"query": q, "error": r})
            time.sleep(1.2)
    for q in CN_QUERIES:
        print(f"[CN] {q}", flush=True)
        for key, fn in [("openalex", openalex), ("crossref", crossref), ("s2", s2)]:
            r = fn(q)
            if isinstance(r, list):
                for item in r:
                    item["query"] = q
                results[key].extend(r)
            else:
                results[key].append({"query": q, "error": r})
            time.sleep(1.2)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print("SAVED", OUT)
    for k, v in results.items():
        n = len([x for x in v if isinstance(x, dict) and "title" in x])
        print(f"  {k}: {n} hits")

if __name__ == "__main__":
    main()