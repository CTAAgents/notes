# -*- coding: utf-8 -*-
"""第三轮补核验：仅针对仍不确定的引用键, 放慢请求避免限流。"""
import json
import time

import requests

H = {"User-Agent": "ai-fin-trading-survey/1.0 (mailto:research@example.com)"}

WANT3 = {
    "sullivan1999": "Data-Snooping, Technical Trading Rule Performance, and the Bootstrap Journal of Finance",
    "jame2016": "The Value of Crowdsourced Earnings Forecasts Journal of Accounting Research",
    "katona2018": "On the Capital Market Consequences of Alternative Data Evidence from Outer Space",
    "huang2022finbert": "FinBERT A Large Language Model for Extracting Information from Financial Text Contemporary Accounting Research",
    "chenkellyxiu2022": "Expected Returns and Large Language Models Chen Kelly Xiu",
    "takahashi2019": "Modeling financial time-series with generative adversarial networks Physica A",
    "sawhney2020": "Deep Attentive Learning for Stock Movement Prediction from Social Media Text and Company Correlations EMNLP",
    "lopezdeprado2018": "Advances in Financial Machine Learning Lopez de Prado Wiley",
    "cartea2015": "Algorithmic and High-Frequency Trading Cartea Jaimungal Penalva Cambridge",
    "grossmanstiglitz1980": "On the Impossibility of Informationally Efficient Markets American Economic Review Grossman Stiglitz",
    "zhu2019": "Big Data as a Governance Mechanism Review of Financial Studies",
    "mcleanpontiff2016": "Does Academic Research Destroy Stock Return Predictability Journal of Finance",
    "wiese2020quantgan": "Quant GANs deep generation of financial time series Quantitative Finance Wiese",
    "nevmyvaka2006": "Reinforcement Learning for Optimized Trade Execution Nevmyvaka Feng Kearns",
    "almgren2005": "Direct Estimation of Equity Market Impact Risk Almgren Thum",
    "yoon2019timegan": "Time-series Generative Adversarial Networks Yoon Jarrett van der Schaar",
}


def crossref(q, rows=3):
    for _ in range(3):
        try:
            r = requests.get("https://api.crossref.org/works", headers=H, timeout=40, params={
                "query.bibliographic": q, "rows": rows,
                "select": "title,DOI,published,issued,container-title,author,type"})
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(4)
    else:
        return ["FAILED"]
    out = []
    for w in r.json().get("message", {}).get("items", []):
        yr = None
        for k in ("published", "published-print", "issued"):
            if w.get(k, {}).get("date-parts"):
                yr = w[k]["date-parts"][0][0]
                break
        au = w.get("author") or []
        a1 = au[0].get("family") if au else ""
        out.append(f'{yr} | {a1} | {(w.get("title") or [""])[0][:74]} | {w.get("DOI")} | {(w.get("container-title") or [""])[0][:36]} | {w.get("type")}')
    return out


if __name__ == "__main__":
    res = {}
    for k, q in WANT3.items():
        c = crossref(q)
        res[k] = c
        print(f"\n[{k}]")
        for x in c:
            print("   " + str(x))
        time.sleep(2.5)
    json.dump(res, open(r"d:\Finance\AI金融交易综述\outputs\refs_round3.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
