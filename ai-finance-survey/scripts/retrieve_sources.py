# -*- coding: utf-8 -*-
"""
批量检索"AI 在金融交易中的应用"综述文献。
来源: OpenAlex (经典金融/计量期刊) + arXiv API (q-fin 预印本) + Crossref (补核验)。
只保存接口真实返回的元数据, 绝不编造 DOI/年份/标题。
"""
import json
import re
import time
import urllib.parse

import requests

OUT = r"d:\Finance\AI金融交易综述\outputs\sources.json"
MAIL = "research@example.com"
HEADERS = {"User-Agent": "ai-fin-trading-survey/1.0 (mailto:research@example.com)"}


def get(url, params, timeout=60, retries=3):
    last = None
    for _ in range(retries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code}"
        except Exception as e:  # noqa
            last = str(e)
        time.sleep(1.2)
    return last


def openalex_search(title_query, per_page=4):
    r = get("https://api.openalex.org/works", {
        "filter": f"title.search:{title_query}",
        "per-page": per_page,
        "sort": "cited_by_count:desc",
        "mailto": MAIL,
    })
    if isinstance(r, str):
        return {"error": r}
    out = []
    for w in r.json().get("results", []):
        loc = w.get("primary_location") or {}
        src = (loc.get("source") or {}).get("display_name")
        out.append({
            "title": w.get("display_name"),
            "year": w.get("publication_year"),
            "doi": w.get("doi"),
            "venue": src,
            "cited_by": w.get("cited_by_count"),
            "oa": (w.get("open_access") or {}).get("is_oa"),
            "oa_url": (w.get("open_access") or {}).get("oa_url"),
            "source": "openalex",
        })
    return out


def arxiv_search(query, max_results=10, sort="relevance"):
    r = get("http://export.arxiv.org/api/query", {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance" if sort == "relevance" else "submittedDate",
        "sortOrder": "descending",
    })
    if isinstance(r, str):
        return {"error": r}
    out = []
    for m in re.finditer(r"<entry>(.*?)</entry>", r.text, re.S):
        e = m.group(1)
        t = re.search(r"<title>(.*?)</title>", e, re.S)
        i = re.search(r"<id>(.*?)</id>", e)
        p = re.search(r"<published>(.*?)</published>", e)
        s = re.search(r"<summary>(.*?)</summary>", e, re.S)
        if not (t and i):
            continue
        cats = re.findall(r'term="([^"]+)"', e)
        out.append({
            "title": re.sub(r"\s+", " ", t.group(1)).strip(),
            "year": p.group(1)[:4] if p else None,
            "arxiv_id": i.group(1).split("/abs/")[-1],
            "url": i.group(1),
            "abstract": re.sub(r"\s+", " ", s.group(1)).strip()[:600] if s else "",
            "cats": cats,
            "source": "arxiv",
        })
    return out


def crossref_search(query, rows=3):
    r = get("https://api.crossref.org/works", {
        "query.bibliographic": query,
        "rows": rows,
        "select": "title,DOI,published,container-title,is-referenced-by-count,author",
    })
    if isinstance(r, str):
        return {"error": r}
    out = []
    for w in r.json().get("message", {}).get("items", []):
        yr = None
        for k in ("published", "published-print", "published-online", "issued"):
            if w.get(k) and w[k].get("date-parts"):
                yr = w[k]["date-parts"][0][0]
                break
        out.append({
            "title": (w.get("title") or [None])[0],
            "year": yr,
            "doi": w.get("DOI"),
            "venue": (w.get("container-title") or [None])[0],
            "cited_by": w.get("is-referenced-by-count"),
            "source": "crossref",
        })
    return out


# ---- 经典/锚点论文 (OpenAlex 标题检索) ----
OPENALEX_TITLES = [
    # 机器学习 × 资产定价 (锚点)
    "Empirical Asset Pricing via Machine Learning",
    "Autoencoder Asset Pricing Models",
    "Deep Learning in Asset Pricing",
    "Characteristics are Covariances",
    "The Virtue of Complexity in Return Prediction",
    "Machine Learning for Factor Investing",
    "Random Forests and the Cross-Section of Stock Returns",
    "Nonlinearity in the Cross-Section of Stock Returns",
    "Is There a Replication Crisis in Finance",
    # 有效市场/预测边界
    "Efficient Capital Markets: A Review of Theory and Empirical Work",
    "On the Impossibility of Informationally Efficient Markets",
    "Continuous Auctions and Insider Trading",
    "Trading and Exchanges",
    "The Econometrics of Financial Markets",
    # 最优执行
    "Optimal Execution of Portfolio Transactions",
    "Optimal Trading with Stochastic Liquidity and Volatility",
    "Algorithmic and High-Frequency Trading",
    "High-Frequency Trading in a Limit Order Book",
    # RL 交易
    "Deep Reinforcement Learning for Trading",
    "A Deep Reinforcement Learning Framework for the Financial Portfolio Management",
    "FinRL: A Deep Reinforcement Learning Library for Automated Stock Trading",
    # NLP
    "FinBERT: Financial Sentiment Analysis with Pre-trained Language Models",
    "Giving Content to Investor Sentiment",
    "Investor Sentiment and the Cross-Section of Stock Returns",
    "News and Stock Prices",
    # 生成式
    "Generative Adversarial Networks",
    "Generating Realistic Stock Market Order Streams",
    "Stock Market Simulation Using Generative Adversarial Networks",
    # GNN
    "Temporal Relational Ranking for Stock Prediction",
    "HATS: A Hierarchical Graph Attention Network for Stock Movement Prediction",
    # 评测方法论
    "A Reality Check for Data Snooping",
    "The Probability of Backtest Overfitting",
    "... and the Cross-Section of Expected Returns",
    "Pseudo-Mathematics and Financial Charlatanism",
    "Backtesting",
    "The Deflated Sharpe Ratio",
    # 市场微观结构 / 深度学习
    "Deep Learning for Market Microstructure",
    "DeepLOB: Deep Convolutional Neural Networks for Limit Order Books",
    "Predicting the direction of stock market prices using machine learning",
    # 组合与风险
    "Deep Learning for Portfolio Optimization",
    "End-to-End Portfolio Optimization",
    "Machine Learning for Risk Management",
    # 综述
    "Machine Learning in Finance: A Topic Modeling Approach",
    "Machine Learning for Trading",
    "Deep Learning for Financial Applications: A Survey",
    "Artificial Intelligence in Finance: A Review",
    "Big Data and Machine Learning in Quantitative Investment",
]

# ---- arXiv 检索 (q-fin / cs) ----
ARXIV_QUERIES = [
    # 监督学习 / alpha
    'abs:"alpha" AND abs:"factor" AND cat:q-fin.PM',
    'abs:"cross-sectional" AND abs:"stock return" AND abs:"machine learning"',
    'abs:"stock selection" AND abs:"deep learning"',
    'abs:"return prediction" AND cat:q-fin.ST',
    'abs:"factor mining" AND abs:"neural"',
    # 深度学习 / 序列
    'abs:"LSTM" AND abs:"stock prediction"',
    'abs:"transformer" AND abs:"financial time series"',
    'abs:"temporal fusion transformer" AND cat:q-fin',
    'abs:"time series foundation model" AND cat:q-fin',
    'abs:"foundation model" AND abs:"finance"',
    # 强化学习
    'abs:"reinforcement learning" AND abs:"portfolio"',
    'abs:"reinforcement learning" AND abs:"optimal execution"',
    'abs:"reinforcement learning" AND abs:"market making"',
    'abs:"deep reinforcement learning" AND abs:"trading"',
    'abs:"multi-agent reinforcement learning" AND abs:"market"',
    # NLP / LLM
    'abs:"large language model" AND abs:"stock" AND abs:"trading"',
    'abs:"LLM agent" AND abs:"financial"',
    'abs:"financial sentiment" AND abs:"deep learning"',
    'abs:"ChatGPT" AND abs:"stock return"',
    'abs:"financial large language model"',
    'abs:"earnings call" AND abs:"natural language"',
    # 生成式
    'abs:"generative adversarial" AND abs:"stock" AND abs:"market"',
    'abs:"diffusion model" AND abs:"financial time series"',
    'abs:"synthetic financial data" AND abs:"generation"',
    'abs:"market simulator" AND abs:"agent-based" AND abs:"learning"',
    # GNN
    'abs:"graph neural network" AND abs:"stock"',
    'abs:"graph" AND abs:"relational" AND abs:"stock prediction"',
    'abs:"hypergraph" AND abs:"financial"',
    # 微观结构 / 订单簿 / HFT
    'abs:"limit order book" AND abs:"deep learning"',
    'abs:"high frequency trading" AND abs:"machine learning"',
    'abs:"market microstructure" AND abs:"neural"',
    # 另类数据
    'abs:"alternative data" AND abs:"trading"',
    'abs:"satellite imagery" AND abs:"economic"',
    # 执行 / 组合 / 风险
    'abs:"optimal execution" AND abs:"reinforcement learning"',
    'abs:"portfolio optimization" AND abs:"deep learning"',
    'abs:"risk management" AND abs:"machine learning" AND cat:q-fin.RM',
    'abs:"drawdown" AND abs:"reinforcement"',
    # 评测方法论 / 过拟合
    'abs:"backtest overfitting" AND cat:q-fin',
    'abs:"data snooping" AND abs:"trading"',
    'abs:"deflated Sharpe"',
    'abs:"replication" AND abs:"asset pricing"',
    'abs:"low signal-to-noise" AND abs:"finance"',
    # LLM 智能体交易 / 前沿
    'abs:"LLM" AND abs:"trading agent"',
    'abs:"agent" AND abs:"financial market" AND abs:"simulation"',
    'abs:"explainable" AND abs:"trading" AND abs:"deep learning"',
]

# ---- Crossref 补核验 ----
CROSSREF_QUERIES = [
    "Empirical Asset Pricing via Machine Learning",
    "Deep Learning for Limit Order Books",
    "Deep Reinforcement Learning for Trading",
    "FinBERT financial sentiment",
    "Optimal Execution of Portfolio Transactions",
    "The Deflated Sharpe Ratio",
    "Temporal Relational Ranking for Stock Prediction",
    "Generating Realistic Stock Market Order Streams",
    "Can ChatGPT Forecast Stock Price Movements",
    "Machine learning cross-section stock returns",
]

if __name__ == "__main__":
    result = {"openalex": {}, "arxiv": {}, "crossref": {}}

    print("== OpenAlex 标题检索 ==")
    for t in OPENALEX_TITLES:
        hits = openalex_search(t)
        result["openalex"][t] = hits
        if isinstance(hits, dict) and "error" in hits:
            print(f"  [ERR] {t}: {hits['error']}")
        else:
            for h in hits:
                print(f"  {h['year']} | {h['title'][:70]} | {h['doi']} | cited={h['cited_by']}")
        time.sleep(0.25)

    print("== arXiv 检索 ==")
    for q in ARXIV_QUERIES:
        hits = arxiv_search(q)
        result["arxiv"][q] = hits
        if isinstance(hits, dict) and "error" in hits:
            print(f"  [ERR] {q}: {hits['error']}")
        else:
            for h in hits:
                print(f"  {h['year']} | {h['title'][:70]} | {h['arxiv_id']}")
        time.sleep(3.0)

    print("== Crossref 补核验 ==")
    for q in CROSSREF_QUERIES:
        hits = crossref_search(q)
        result["crossref"][q] = hits
        if isinstance(hits, dict) and "error" in hits:
            print(f"  [ERR] {q}: {hits['error']}")
        else:
            for h in hits:
                print(f"  {h['year']} | {str(h['title'])[:70]} | {h['doi']}")
        time.sleep(0.5)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n已保存: {OUT}")
