# -*- coding: utf-8 -*-
"""汇总 sources.json 为去重后的来源池, 统计数量并导出便于人工筛选。"""
import json
import re

SRC = r"d:\Finance\AI金融交易综述\outputs\sources.json"
OUT = r"d:\Finance\AI金融交易综述\outputs\pool.json"


def norm(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def main():
    data = json.load(open(SRC, encoding="utf-8"))
    pool = {}

    for _q, hits in data.get("openalex", {}).items():
        if not isinstance(hits, list):
            continue
        for h in hits:
            if not h.get("title"):
                continue
            key = ("doi:" + h["doi"].lower()) if h.get("doi") else ("ttl:" + norm(h["title"]))
            pool.setdefault(key, {
                "title": h["title"], "year": h.get("year"), "doi": h.get("doi"),
                "venue": h.get("venue"), "cited_by": h.get("cited_by"),
                "url": h.get("oa_url"), "kind": "journal",
            })

    for _q, hits in data.get("crossref", {}).items():
        if not isinstance(hits, list):
            continue
        for h in hits:
            if not h.get("title"):
                continue
            key = ("doi:" + h["doi"].lower()) if h.get("doi") else ("ttl:" + norm(h["title"]))
            if key in pool:
                continue
            pool.setdefault(key, {
                "title": h["title"], "year": h.get("year"), "doi": h.get("doi"),
                "venue": h.get("venue"), "cited_by": h.get("cited_by"),
                "url": None, "kind": "journal",
            })

    for _q, hits in data.get("arxiv", {}).items():
        if not isinstance(hits, list):
            continue
        for h in hits:
            if not h.get("title"):
                continue
            key = "ax:" + h["arxiv_id"].split("v")[0]
            if key in pool:
                continue
            pool[key] = {
                "title": h["title"], "year": h.get("year"), "arxiv_id": h["arxiv_id"],
                "url": h.get("url"), "cats": h.get("cats"), "abstract": h.get("abstract"),
                "kind": "arxiv",
            }

    out = list(pool.values())
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    nj = sum(1 for x in out if x["kind"] == "journal")
    na = sum(1 for x in out if x["kind"] == "arxiv")
    print(f"总来源: {len(out)}  期刊/Crossref: {nj}  arXiv: {na}")
    print(f"已保存: {OUT}")


if __name__ == "__main__":
    main()
