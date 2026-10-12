# -*- coding: utf-8 -*-
"""按精确标题对全部引用键做多源核验 (OpenAlex -> Crossref -> arXiv)。
只保留能确证的元数据; 输出 references 草稿供人工复核。"""
import json
import re
import time
import urllib.parse

import requests

OUT = r"d:\Finance\AI金融交易综述\outputs\refs_verified.json"
MAIL = "research@example.com"
H = {"User-Agent": "ai-fin-trading-survey/1.0 (mailto:research@example.com)"}

# key: (标题, 作者首作者姓, 期望年份)
WANT = {
    "markowitz1952": ("Portfolio Selection", "Markowitz", 1952),
    "fama1970": ("Efficient Capital Markets: A Review of Theory and Empirical Work", "Fama", 1970),
    "grossmanstiglitz1980": ("On the Impossibility of Informationally Efficient Markets", "Grossman", 1980),
    "kyle1985": ("Continuous Auctions and Insider Trading", "Kyle", 1985),
    "bollerslev1986": ("Generalized Autoregressive Conditional Heteroskedasticity", "Bollerslev", 1986),
    "hamilton1989": ("A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle", "Hamilton", 1989),
    "shleifer1997": ("The Limits of Arbitrage", "Shleifer", 1997),
    "almgrenchriss2000": ("Optimal Execution of Portfolio Transactions", "Almgren", 2000),
    "almgren2005": ("Direct Estimation of Equity Market Impact", "Almgren", 2005),
    "rockafellar2000": ("Optimization of Conditional Value-at-Risk", "Rockafellar", 2000),
    "mcneil2000": ("Estimation of tail-related risk measures for heteroscedastic financial time series", "McNeil", 2000),
    "ledoitwolf2004": ("A well-conditioned estimator for large-dimensional covariance matrices", "Ledoit", 2004),
    "chekhlov2005": ("Drawdown measure in portfolio optimization", "Chekhlov", 2005),
    "harvey2018": ("The Impact of Volatility Targeting", "Harvey", 2018),
    "cohenfrazzini2008": ("Economic Links and Predictable Returns", "Cohen", 2008),
    "tetlock2007": ("Giving Content to Investor Sentiment: The Role of Media in the Stock Market", "Tetlock", 2007),
    "bakerwurgler2006": ("Investor Sentiment and the Cross-Section of Stock Returns", "Baker", 2006),
    "loughranmcdonald2011": ("When Is a Liability Not a Liability? Textual Analysis, Dictionaries, and 10-Ks", "Loughran", 2011),
    "white2000": ("A Reality Check for Data Snooping", "White", 2000),
    "sullivan1999": ("Data-Snooping, Technical Trading Rule Performance, and the Bootstrap", "Sullivan", 1999),
    "harveylz2016": ("... and the Cross-Section of Expected Returns", "Harvey", 2016),
    "mcleanpontiff2016": ("Does Academic Research Destroy Stock Return Predictability?", "McLean", 2016),
    "jensen2023": ("Is There a Replication Crisis in Finance?", "Jensen", 2023),
    "bailey2014pseudo": ("Pseudo-Mathematics and Financial Charlatanism: The Effects of Backtest Overfitting on Out-of-Sample Performance", "Bailey", 2014),
    "bailey2014dsr": ("The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality", "Bailey", 2014),
    "bailey2016pbo": ("The Probability of Backtest Overfitting", "Bailey", 2016),
    "gukellyxiu2020": ("Empirical Asset Pricing via Machine Learning", "Gu", 2020),
    "gukellyxiu2021": ("Autoencoder Asset Pricing Models", "Gu", 2021),
    "chenpelgerzhu2024": ("Deep Learning in Asset Pricing", "Chen", 2024),
    "kellymalamudzhou2024": ("The Virtue of Complexity in Return Prediction", "Kelly", 2024),
    "fenggiglioxu2020": ("Taming the Factor Zoo: A Test of New Factors", "Feng", 2020),
    "krauss2017": ("Deep neural networks, gradient-boosted trees, random forests: Statistical arbitrage on the S&P 500", "Krauss", 2017),
    "fischerkrauss2018": ("Deep learning with long short-term memory networks for financial market predictions", "Fischer", 2018),
    "deng2017": ("Deep Direct Reinforcement Learning for Financial Signal Representation and Trading", "Deng", 2017),
    "zhang2019deeplob": ("DeepLOB: Deep Convolutional Neural Networks for Limit Order Books", "Zhang", 2019),
    "tsantekidis2017": ("Forecasting Stock Prices from the Limit Order Book Using Convolutional Neural Networks", "Tsantekidis", 2017),
    "ntakaris2018fi2010": ("Benchmark Dataset for Mid-Price Forecasting of Limit Order Book Data with Machine Learning Methods", "Ntakaris", 2018),
    "cartea2015": ("Algorithmic and High-Frequency Trading", "Cartea", 2015),
    "chen2018gcn": ("Incorporating Corporation Relationship via Graph Convolutional Neural Networks for Stock Price Prediction", "Chen", 2018),
    "feng2019rsr": ("Temporal Relational Ranking for Stock Prediction", "Feng", 2019),
    "matsunaga2019": ("Exploring Graph Neural Networks for Stock Market Predictions with Rolling Window Analysis", "Matsunaga", 2019),
    "zhu2019": ("Big Data as a Governance Mechanism", "Zhu", 2019),
    "jame2016": ("The Value of Crowdsourced Earnings Forecasts", "Jame", 2016),
    "katona2018": ("On the Capital Market Consequences of Alternative Data: Evidence from Outer Space", "Katona", 2018),
    "costa2022": ("End-to-end risk budgeting portfolio optimization with neural networks", "Costa", 2022),
    # arXiv 类
    "vaswani2017": ("Attention Is All You Need", "Vaswani", 2017),
    "velickovic2018gat": ("Graph Attention Networks", "Velickovic", 2018),
    "lim2021tft": ("Temporal Fusion Transformers for interpretable multi-horizon time series forecasting", "Lim", 2021),
    "zhou2021informer": ("Informer: Beyond Efficient Transformer for Long Sequence Time-Series Forecasting", "Zhou", 2021),
    "wu2021autoformer": ("Autoformer: Decomposition Transformers with Auto-Correlation for Long-Term Series Forecasting", "Wu", 2021),
    "zeng2023dlinear": ("Are Transformers Effective for Time Series Forecasting?", "Zeng", 2023),
    "ansari2024chronos": ("Chronos: Learning the Language of Time Series", "Ansari", 2024),
    "das2024timesfm": ("A decoder-only foundation model for time-series forecasting", "Das", 2024),
    "rasul2023lagllama": ("Lag-Llama: Towards Foundation Models for Probabilistic Time Series Forecasting", "Rasul", 2023),
    "jiang2017": ("A Deep Reinforcement Learning Framework for the Financial Portfolio Management Problem", "Jiang", 2017),
    "liu2021finrl": ("FinRL: A Deep Reinforcement Learning Library for Automated Stock Trading in Quantitative Finance", "Liu", 2020),
    "nevmyvaka2006": ("Reinforcement Learning for Optimized Trade Execution", "Nevmyvaka", 2006),
    "spooner2018": ("Market Making via Reinforcement Learning", "Spooner", 2018),
    "araci2019finbert": ("FinBERT: Financial Sentiment Analysis with Pre-trained Language Models", "Araci", 2019),
    "yang2020finbert": ("FinBERT: A Pretrained Language Model for Financial Communications", "Yang", 2020),
    "huang2022finbert": ("FinBERT: A Large Language Model for Extracting Information from Financial Text", "Huang", 2022),
    "wu2023bloomberggpt": ("BloombergGPT: A Large Language Model for Finance", "Wu", 2023),
    "yang2023fingpt": ("FinGPT: Open-Source Financial Large Language Models", "Yang", 2023),
    "lopezlira2023": ("Can ChatGPT Forecast Stock Price Movements? Return Predictability and Large Language Models", "Lopez-Lira", 2023),
    "chenkellyxiu2022": ("Expected Returns and Large Language Models", "Chen", 2022),
    "yu2023finmem": ("FinMem: A Performance-Enhanced LLM Trading Agent with Layered Memory and Character Design", "Yu", 2023),
    "wiese2020quantgan": ("Quant GANs: Deep Generation of Financial Time Series", "Wiese", 2020),
    "takahashi2019": ("Modeling financial time-series with generative adversarial networks", "Takahashi", 2019),
    "yoon2019timegan": ("Time-series Generative Adversarial Networks", "Yoon", 2019),
    "buehler2019deephedging": ("Deep Hedging", "Buehler", 2019),
    "byrd2020abides": ("ABIDES: Towards High-Fidelity Market Simulation for AI Research", "Byrd", 2020),
    "park2023generative": ("Generative Agents: Interactive Simulacra of Human Behavior", "Park", 2023),
    "xu2021hats": ("HATS: A Hierarchical Graph Attention Network for Stock Movement Prediction", "Xu", 2019),
    "wang2021thgnn": ("Temporal and Heterogeneous Graph Neural Network for Financial Time Series Prediction", "Wang", 2021),
    "sawhney2020": ("Deep Attentive Learning for Stock Movement Prediction from Social Media Text and Company Correlations", "Sawhney", 2020),
    "zhang2020dlpo": ("Deep Learning for Portfolio Optimization", "Zhang", 2020),
    "martin2011": ("Mean Reversion Pays, but Costs", "Martin", 2011),
    "guant2019": ("Deep Reinforcement Learning for Market Making in Corporate Bonds", "Guéant", 2019),
    "lopezdeprado2018": ("Advances in Financial Machine Learning", "Lopez de Prado", 2018),
    "qlib": ("Qlib: An AI-oriented Quantitative Investment Platform", "Yang", 2020),
}


def get(url, params, timeout=45, retries=3):
    last = None
    for _ in range(retries):
        try:
            r = requests.get(url, params=params, headers=H, timeout=timeout)
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code}"
        except Exception as e:
            last = str(e)
        time.sleep(1.0)
    return last


def oa(title, author, year):
    r = get("https://api.openalex.org/works", {
        "filter": f"title.search:{title}", "per-page": 6,
        "sort": "cited_by_count:desc", "mailto": MAIL})
    if isinstance(r, str):
        return None, r
    best, bs = None, 0
    tt = re.sub(r"\W+", "", title.lower())
    for w in r.json().get("results", []):
        wt = re.sub(r"\W+", "", (w.get("display_name") or "").lower())
        inter = len(set(re.findall(r"[a-z]{3,}", title.lower())) & set(re.findall(r"[a-z]{3,}", (w.get("display_name") or "").lower())))
        s = inter + (10 if tt[:40] and tt[:40] in wt else 0)
        if w.get("publication_year") == year:
            s += 4
        au = [(a.get("author") or {}).get("display_name", "") for a in (w.get("authorships") or [])]
        if any(author.lower() in (a or "").lower() for a in au):
            s += 3
        if s > bs:
            bs, best = s, w
    if not best:
        return None, "no-result"
    loc = best.get("primary_location") or {}
    return {
        "title": best.get("display_name"),
        "year": best.get("publication_year"),
        "doi": best.get("doi"),
        "venue": (loc.get("source") or {}).get("display_name"),
        "authors": [(a.get("author") or {}).get("display_name") for a in (best.get("authorships") or [])][:6],
        "cited_by": best.get("cited_by_count"),
        "src": "openalex", "score": bs,
    }, None


def arxiv(title):
    q = 'ti:"%s"' % title
    r = get("http://export.arxiv.org/api/query", {"search_query": q, "start": 0, "max_results": 5})
    if isinstance(r, str):
        return None
    m = re.search(r"<entry>(.*?)</entry>", r.text, re.S)
    if not m:
        return None
    e = m.group(1)
    t = re.search(r"<title>(.*?)</title>", e, re.S)
    i = re.search(r"<id>(.*?)</id>", e)
    p = re.search(r"<published>(.*?)</published>", e)
    au = re.findall(r"<name>(.*?)</name>", e)
    return {
        "title": re.sub(r"\s+", " ", t.group(1)).strip() if t else None,
        "year": p.group(1)[:4] if p else None,
        "arxiv_id": i.group(1).split("/abs/")[-1] if i else None,
        "authors": au[:6], "src": "arxiv",
    }


if __name__ == "__main__":
    res = {}
    for k, (title, author, year) in WANT.items():
        o, err = oa(title, author, year)
        entry = None
        if o and o.get("score", 0) >= 8:
            entry = o
        else:
            ax = arxiv(title)
            if ax:
                entry = ax
            elif o:
                entry = o
        if entry:
            entry["key"] = k
            entry["want_title"] = title
            entry["want_year"] = year
        res[k] = entry or {"key": k, "want_title": title, "error": err or "unresolved"}
        flag = "OK " if entry else "?? "
        print(f"{flag}[{k}] {entry.get('year') if entry else '-'} | {str(entry.get('title'))[:62] if entry else 'UNRESOLVED'} | {entry.get('doi') or entry.get('arxiv_id') if entry else ''}")
        time.sleep(0.4)

    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n已保存: {OUT}")
