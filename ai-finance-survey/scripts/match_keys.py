# -*- coding: utf-8 -*-
"""为每个引用键在来源池中匹配最可能的来源; 输出匹配报告与候选 references 条目。"""
import json
import re

POOL = json.load(open(r"d:\Finance\AI金融交易综述\outputs\pool.json", encoding="utf-8"))

# key -> 用于匹配的标题关键词
WANT = {
    "almgren2005": "Direct Estimation of Equity Market Impact",
    "almgrenchriss2000": "Optimal Execution of Portfolio Transactions",
    "ansari2024chronos": "Chronos Learning the Language of Time Series",
    "araci2019finbert": "FinBERT Financial Sentiment Analysis with Pre-trained Language Models",
    "bailey2014dsr": "The Deflated Sharpe Ratio Correcting for Selection Bias",
    "bailey2014pseudo": "Pseudo-Mathematics and Financial Charlatanism",
    "bailey2016pbo": "The probability of backtest overfitting",
    "bakerwurgler2006": "Investor Sentiment and the Cross-Section of Stock Returns",
    "bollerslev1986": "Generalized autoregressive conditional heteroskedasticity",
    "buehler2019deephedging": "Deep Hedging",
    "byrd2020abides": "ABIDES Towards High-Fidelity Market Simulation",
    "cartea2015": "Algorithmic and High-Frequency Trading",
    "chekhlov2005": "Drawdown measure in portfolio optimization",
    "chen2018gcn": "Incorporating Corporation Relationship via Graph Convolutional Neural Networks",
    "chenkellyxiu2022": "Expected Returns and Large Language Models",
    "chenpelgerzhu2024": "Deep Learning in Asset Pricing",
    "cohenfrazzini2008": "Economic Links and Predictable Returns",
    "costa2022": "End-to-end risk budgeting portfolio optimization with neural networks",
    "das2024timesfm": "decoder-only foundation model for time-series forecasting",
    "deng2017": "Deep Direct Reinforcement Learning for Financial Signal Representation and Trading",
    "fama1970": "Efficient Capital Markets A Review of Theory and Empirical Work",
    "feng2019rsr": "Temporal Relational Ranking for Stock Prediction",
    "fenggiglioxu2020": "Taming the Factor Zoo",
    "fischerkrauss2018": "Deep learning with long short-term memory networks for financial market predictions",
    "grossmanstiglitz1980": "On the Impossibility of Informationally Efficient Markets",
    "guant2019": "Deep Reinforcement Learning for Market Making in Corporate Bonds",
    "gukellyxiu2020": "Empirical Asset Pricing via Machine Learning",
    "hamilton1989": "A New Approach to the Economic Analysis of Nonstationary Time Series",
    "harvey2018": "The Impact of Volatility Targeting",
    "harveylz2016": "and the Cross-Section of Expected Returns",
    "huang2022finbert": "FinBERT A Large Language Model for Extracting Information from Financial Text",
    "jame2016": "The Value of Crowdsourced Earnings Forecasts",
    "jiang2017": "A Deep Reinforcement Learning Framework for the Financial Portfolio Management Problem",
    "katona2018": "On the Capital Market Consequences of Alternative Data",
    "kellymalamudzhou2024": "The Virtue of Complexity in Return Prediction",
    "krauss2017": "Deep neural networks gradient-boosted trees random forests Statistical arbitrage",
    "kyle1985": "Continuous Auctions and Insider Trading",
    "ledoitwolf2004": "A well-conditioned estimator for large-dimensional covariance matrices",
    "lim2021tft": "Temporal Fusion Transformers for interpretable multi-horizon time series forecasting",
    "liu2021finrl": "FinRL A Deep Reinforcement Learning Library for Automated Stock Trading",
    "lopezdeprado2018": "Advances in Financial Machine Learning",
    "lopezlira2023": "Can ChatGPT Forecast Stock Price Movements",
    "loughranmcdonald2011": "When Is a Liability Not a Liability Textual Analysis Dictionaries",
    "markowitz1952": "Portfolio Selection",
    "martin2011": "Mean reversion pays but costs",
    "matsunaga2019": "Exploring Graph Neural Networks for Stock Market Predictions",
    "mcleanpontiff2016": "Does Academic Research Destroy Stock Return Predictability",
    "mcneil2000": "Estimation of tail-related risk measures for heteroscedastic financial time series",
    "nevmyvaka2006": "Reinforcement Learning for Optimized Trade Execution",
    "ntakaris2018fi2010": "Benchmark dataset for mid-price forecasting of limit order book",
    "park2023generative": "Generative Agents Interactive Simulacra of Human Behavior",
    "qlib": "Qlib An AI-oriented Quantitative Investment Platform",
    "rasul2023lagllama": "Lag-Llama Towards Foundation Models for Probabilistic Time Series Forecasting",
    "rockafellar2000": "Optimization of Conditional Value-at-Risk",
    "sawhney2020": "Deep Attentive Learning for Stock Movement Prediction from Social Media Text",
    "spooner2018": "Market Making via Reinforcement Learning",
    "sullivan1999": "Data-Snooping Technical Trading Rule Performance and the Bootstrap",
    "takahashi2019": "Modeling financial time-series with generative adversarial networks",
    "tetlock2007": "Giving Content to Investor Sentiment",
    "tsantekidis2017": "Forecasting Stock Prices from the Limit Order Book Using Convolutional Neural Networks",
    "vaswani2017": "Attention is All you Need",
    "velickovic2018gat": "Graph Attention Networks",
    "wang2021thgnn": "Temporal and Heterogeneous Graph Neural Network for Financial Time Series Prediction",
    "white2000": "A Reality Check for Data Snooping",
    "wiese2020quantgan": "Quant GANs deep generation of financial time series",
    "wu2021autoformer": "Autoformer Decomposition Transformers with Auto-Correlation",
    "wu2023bloomberggpt": "BloombergGPT A Large Language Model for Finance",
    "xu2021hats": "HATS A Hierarchical Graph Attention Network for Stock Movement Prediction",
    "yang2020finbert": "FinBERT A Pretrained Language Model for Financial Communications",
    "yang2023fingpt": "FinGPT Open-Source Financial Large Language Models",
    "yoon2019timegan": "Time-series Generative Adversarial Networks",
    "yu2023finmem": "FinMem A Performance-Enhanced LLM Trading Agent",
    "zeng2023dlinear": "Are Transformers Effective for Time Series Forecasting",
    "zhang2019deeplob": "DeepLOB Deep Convolutional Neural Networks for Limit Order Books",
    "zhang2020dlpo": "Deep Learning for Portfolio Optimization",
    "zhou2021informer": "Informer Beyond Efficient Transformer for Long Sequence Time-Series Forecasting",
    "zhu2019": "Big Data as a Governance Mechanism",
}


def toks(s):
    return set(re.findall(r"[a-z]{3,}", (s or "").lower()))


def best(q, n=3):
    qt = toks(q)
    scored = []
    for x in POOL:
        t = toks(x.get("title"))
        if not t:
            continue
        inter = len(qt & t)
        # 精确子串优先
        bonus = 2 if re.sub(r"\W", "", q.lower()) in re.sub(r"\W", "", (x.get("title") or "").lower()) else 0
        s = inter + bonus * 3
        if s > 0:
            scored.append((s, x))
    scored.sort(key=lambda z: -z[0])
    return scored[:n]


found, missing = [], []
for k, q in WANT.items():
    c = best(q)
    if c and c[0][0] >= 2:
        s, x = c[0]
        found.append((k, x, [c2[1] for c2 in c]))
    else:
        missing.append((k, q, c))

print(f"== 匹配到 {len(found)} / 共 {len(WANT)} ==")
for k, x, alts in found:
    print(f"[{k}] {x['year']} | {(x.get('title') or '')[:70]} | {x.get('doi') or x.get('arxiv_id')}")
print(f"\n== 未匹配 {len(missing)} ==")
for k, q, c in missing:
    print(f"[{k}] want: {q}")
    for _s, x in c:
        print(f"     cand: {x['year']} | {(x.get('title') or '')[:70]}")
