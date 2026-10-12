# -*- coding: utf-8 -*-
"""根据多源核验结果生成 references.tex 与 evidence.tex。
所有 DOI/arXiv/链接均来自接口真实返回或经 Crossref DOI 确证, 未编造。
"""
import json

OUT_REF = r"d:\Finance\AI金融交易综述\sections\references.tex"
OUT_EVI = r"d:\Finance\AI金融交易综述\sections\evidence.tex"
OUT_MX = r"d:\Finance\AI金融交易综述\sections\matrix.tex"
OUT_META = r"d:\Finance\AI金融交易综述\outputs\final_refs.json"

# key: (authors, title, venue, year, link, kind, family, role, status)
F = {
    "markowitz1952": ("H.~Markowitz", "Portfolio Selection", "The Journal of Finance", 1952,
                      "https://doi.org/10.1111/j.1540-6261.1952.tb01525.x", "journal", "原理/边界", "现代组合理论起点", "已核验"),
    "fama1970": ("E.~F.~Fama", "Efficient Capital Markets: A Review of Theory and Empirical Work", "The Journal of Finance", 1970,
                 "https://doi.org/10.1111/j.1540-6261.1970.tb00518.x", "journal", "原理/边界", "有效市场三档定义", "已核验"),
    "grossmanstiglitz1980": ("S.~J.~Grossman, J.~E.~Stiglitz", "On the Impossibility of Informationally Efficient Markets", "American Economic Review", 1980,
                             "https://doi.org/10.7916/d8765r99", "journal", "原理/边界", "信息效率悖论（OA 版本链接）", "已核验"),
    "kyle1985": ("A.~S.~Kyle", "Continuous Auctions and Insider Trading", "Econometrica", 1985,
                 "https://doi.org/10.2307/1913210", "journal", "原理/边界", "价格冲击系数 λ 与信息租金耗散", "已核验"),
    "shleifer1997": ("A.~Shleifer, R.~W.~Vishny", "The Limits of Arbitrage", "The Journal of Finance", 1997,
                     "https://doi.org/10.1111/j.1540-6261.1997.tb03807.x", "journal", "原理/边界", "套利限制", "已核验"),
    "bollerslev1986": ("T.~Bollerslev", "Generalized Autoregressive Conditional Heteroskedasticity", "Journal of Econometrics", 1986,
                       "https://doi.org/10.1016/0304-4076(86)90063-1", "journal", "组合/执行/风控", "GARCH 波动率模型", "已核验"),
    "hamilton1989": ("J.~D.~Hamilton", "A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle", "Econometrica", 1989,
                     "https://doi.org/10.2307/1912559", "journal", "组合/执行/风控", "制度切换模型", "已核验"),
    "almgrenchriss2000": ("R.~Almgren, N.~Chriss", "Optimal Execution of Portfolio Transactions", "Journal of Risk", 2000,
                          "https://doi.org/10.21314/jor.2001.041", "journal", "组合/执行/风控", "最优执行解析解", "已核验"),
    "almgren2005": ("R.~Almgren, C.~Thum, E.~Hauptmann, H.~Li", "Direct Estimation of Equity Market Impact", "Risk", 2005,
                    "", "journal", "组合/执行/风控", "平方根冲击律的经验估计", "已核验"),
    "rockafellar2000": ("R.~T.~Rockafellar, S.~Uryasev", "Optimization of Conditional Value-at-Risk", "Journal of Risk", 2000,
                        "https://doi.org/10.21314/jor.2000.038", "journal", "组合/执行/风控", "CVaR 优化", "已核验"),
    "mcneil2000": ("A.~J.~McNeil, R.~Frey", "Estimation of Tail-Related Risk Measures for Heteroscedastic Financial Time Series", "Journal of Empirical Finance", 2000,
                   "https://doi.org/10.1016/s0927-5398(00)00012-8", "journal", "组合/执行/风控", "极值理论尾部风险", "已核验"),
    "ledoitwolf2004": ("O.~Ledoit, M.~Wolf", "A Well-Conditioned Estimator for Large-Dimensional Covariance Matrices", "Journal of Multivariate Analysis", 2004,
                       "https://doi.org/10.1016/s0047-259x(03)00096-4", "journal", "组合/执行/风控", "协方差收缩估计", "已核验"),
    "chekhlov2005": ("A.~Chekhlov, S.~Uryasev, M.~Zabarankin", "Drawdown Measure in Portfolio Optimization", "International Journal of Theoretical and Applied Finance", 2005,
                     "https://doi.org/10.1142/s0219024905002767", "journal", "组合/执行/风控", "回撤约束优化", "已核验"),
    "harvey2018": ("C.~R.~Harvey, E.~Hoyle, R.~Korgaonkar, S.~Rattray, M.~Sargaison, O.~Van Hemert", "The Impact of Volatility Targeting", "The Journal of Portfolio Management", 2018,
                   "https://doi.org/10.3905/jpm.2018.45.1.014", "journal", "组合/执行/风控", "波动率目标化", "已核验"),
    "cohenfrazzini2008": ("L.~Cohen, A.~Frazzini", "Economic Links and Predictable Returns", "The Journal of Finance", 2008,
                          "https://doi.org/10.1111/j.1540-6261.2008.01379.x", "journal", "图网络", "供应链动量传导", "已核验"),
    "tetlock2007": ("P.~C.~Tetlock", "Giving Content to Investor Sentiment: The Role of Media in the Stock Market", "The Journal of Finance", 2007,
                    "https://doi.org/10.1111/j.1540-6261.2007.01232.x", "journal", "NLP/LLM", "媒体情绪与价格", "已核验"),
    "bakerwurgler2006": ("M.~Baker, J.~Wurgler", "Investor Sentiment and the Cross-Section of Stock Returns", "The Journal of Finance", 2006,
                         "https://doi.org/10.1111/j.1540-6261.2006.00885.x", "journal", "NLP/LLM", "情绪指数", "已核验"),
    "loughranmcdonald2011": ("T.~Loughran, B.~McDonald", "When Is a Liability Not a Liability? Textual Analysis, Dictionaries, and 10-Ks", "The Journal of Finance", 2011,
                             "https://doi.org/10.1111/j.1540-6261.2010.01625.x", "journal", "NLP/LLM", "金融情感词典", "已核验"),
    "white2000": ("H.~White", "A Reality Check for Data Snooping", "Econometrica", 2000,
                  "https://doi.org/10.1111/1468-0262.00152", "journal", "评测方法", "Reality Check 数据窥探检验", "已核验"),
    "sullivan1999": ("R.~Sullivan, A.~Timmermann, H.~White", "Data-Snooping, Technical Trading Rule Performance, and the Bootstrap", "The Journal of Finance", 1999,
                     "https://doi.org/10.1111/0022-1082.00163", "journal", "评测方法", "近八千条规则联合检验", "已核验"),
    "harveylz2016": ("C.~R.~Harvey, Y.~Liu, H.~Zhu", "... and the Cross-Section of Expected Returns", "The Review of Financial Studies", 2016,
                     "https://doi.org/10.1093/rfs/hhv059", "journal", "评测方法", "多重检验 t>3 门槛", "已核验"),
    "mcleanpontiff2016": ("R.~D.~McLean, J.~Pontiff", "Does Academic Research Destroy Stock Return Predictability?", "The Journal of Finance", 2016,
                          "https://doi.org/10.1111/jofi.12365", "journal", "评测方法", "发表后收益衰减", "已核验"),
    "jensen2023": ("T.~I.~Jensen, B.~T.~Kelly, L.~H.~Pedersen", "Is There a Replication Crisis in Finance?", "The Journal of Finance", 2023,
                   "https://doi.org/10.1111/jofi.13249", "journal", "评测方法", "因子复现危机", "已核验"),
    "bailey2014pseudo": ("D.~H.~Bailey, J.~M.~Borwein, M.~L\\'opez de Prado, Q.~J.~Zhu", "Pseudo-Mathematics and Financial Charlatanism: The Effects of Backtest Overfitting on Out-of-Sample Performance", "Notices of the AMS", 2014,
                         "https://doi.org/10.1090/noti1105", "journal", "评测方法", "回测过拟合批判", "已核验"),
    "bailey2014dsr": ("D.~H.~Bailey, M.~L\\'opez de Prado", "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality", "The Journal of Portfolio Management", 2014,
                      "https://doi.org/10.3905/jpm.2014.40.5.094", "journal", "评测方法", "缩水夏普 DSR", "已核验"),
    "bailey2016pbo": ("D.~H.~Bailey, J.~M.~Borwein, M.~L\\'opez de Prado, Q.~J.~Zhu", "The Probability of Backtest Overfitting", "Journal of Computational Finance", 2016,
                      "https://doi.org/10.21314/jcf.2016.322", "journal", "评测方法", "过拟合概率 PBO（CSCV）", "已核验"),
    "lopezdeprado2018": ("M.~L\\'opez de Prado", "Advances in Financial Machine Learning", "Wiley", 2018,
                         "", "book", "评测方法", "金融机器学习评测纪律专著", "已核验"),
    "gukellyxiu2020": ("S.~Gu, B.~Kelly, D.~Xiu", "Empirical Asset Pricing via Machine Learning", "The Review of Financial Studies", 2020,
                       "https://doi.org/10.1093/rfs/hhaa009", "journal", "监督学习", "机器学习资产定价基准", "已核验"),
    "gukellyxiu2021": ("S.~Gu, B.~Kelly, D.~Xiu", "Autoencoder Asset Pricing Models", "Journal of Econometrics", 2021,
                       "https://doi.org/10.1016/j.jeconom.2020.07.009", "journal", "监督学习", "自编码条件因子模型", "已核验"),
    "chenpelgerzhu2024": ("L.~Chen, M.~Pelger, J.~Zhu", "Deep Learning in Asset Pricing", "Management Science", 2024,
                          "https://doi.org/10.1287/mnsc.2023.4695", "journal", "监督学习", "无套利结构注入网络", "已核验"),
    "kellymalamudzhou2024": ("B.~Kelly, S.~Malamud, K.~Zhou", "The Virtue of Complexity in Return Prediction", "The Journal of Finance", 2024,
                             "https://doi.org/10.1111/jofi.13298", "journal", "监督学习", "复杂性红利（争议）", "已核验"),
    "fenggiglioxu2020": ("G.~Feng, S.~Giglio, D.~Xiu", "Taming the Factor Zoo: A Test of New Factors", "The Journal of Finance", 2020,
                         "https://doi.org/10.1111/jofi.12883", "journal", "监督学习", "双重选择 Lasso", "已核验"),
    "krauss2017": ("C.~Krauss, X.~Do, N.~Huck", "Deep Neural Networks, Gradient-Boosted Trees, Random Forests: Statistical Arbitrage on the S&P 500", "European Journal of Operational Research", 2017,
                   "https://doi.org/10.1016/j.ejor.2016.10.031", "journal", "监督学习", "三类模型统计套利对照", "已核验"),
    "fischerkrauss2018": ("T.~Fischer, C.~Krauss", "Deep Learning with Long Short-Term Memory Networks for Financial Market Predictions", "European Journal of Operational Research", 2018,
                          "https://doi.org/10.1016/j.ejor.2017.11.054", "journal", "深度学习", "LSTM 方向预测与回测", "已核验"),
    "deng2017": ("Y.~Deng, F.~Bao, Y.~Kong, Z.~Ren, Q.~Dai", "Deep Direct Reinforcement Learning for Financial Signal Representation and Trading", "IEEE Transactions on Neural Networks and Learning Systems", 2017,
                 "https://doi.org/10.1109/tnnls.2016.2522401", "journal", "强化学习", "直接 RL 信号与交易", "已核验"),
    "zhang2019deeplob": ("Z.~Zhang, S.~Zohren, T.~Roberts", "DeepLOB: Deep Convolutional Neural Networks for Limit Order Books", "IEEE Transactions on Signal Processing", 2019,
                         "https://doi.org/10.1109/tsp.2019.2907260", "journal", "深度学习", "订单簿 CNN-LSTM", "已核验"),
    "tsantekidis2017": ("A.~Tsantekidis, N.~Passalis, A.~Tefas, J.~Kanniainen, M.~Gabbouj, A.~Iosifidis", "Forecasting Stock Prices from the Limit Order Book Using Convolutional Neural Networks", "IEEE Conference on Business Informatics", 2017,
                        "https://doi.org/10.1109/cbi.2017.23", "conf", "深度学习", "订单簿 CNN", "已核验"),
    "ntakaris2018fi2010": ("A.~Ntakaris, M.~Magris, J.~Kanniainen, M.~Gabbouj, A.~Iosifidis", "Benchmark Dataset for Mid-Price Forecasting of Limit Order Book Data with Machine Learning Methods", "Journal of Forecasting", 2018,
                           "https://doi.org/10.1002/for.2543", "journal", "深度学习", "FI-2010 公开订单簿基准", "已核验"),
    "sirignano2019lob": ("J.~Sirignano", "Deep Learning for Limit Order Books", "Quantitative Finance", 2019,
                         "https://doi.org/10.1080/14697688.2018.1546053", "journal", "深度学习", "空间-订单簿深度网络", "已核验"),
    "cartea2015": ("Á.~Cartea, S.~Jaimungal, J.~Penalva", "Algorithmic and High-Frequency Trading", "Cambridge University Press", 2015,
                   "", "book", "组合/执行/风控", "算法与高频交易理论专著", "已核验"),
    "vaswani2017": ("A.~Vaswani, et al.", "Attention Is All You Need", "NeurIPS", 2017,
                    "https://arxiv.org/abs/1706.03762", "conf", "深度学习", "注意力机制", "已核验"),
    "velickovic2018gat": ("P.~Veli\\v{c}kovi\\'c, G.~Cucurull, A.~Casanova, A.~Romero, P.~Liò, Y.~Bengio", "Graph Attention Networks", "ICLR", 2018,
                          "https://arxiv.org/abs/1710.10903", "conf", "图网络", "图注意力网络", "已核验"),
    "lim2021tft": ("B.~Lim, S.~Ö.~Arık, N.~Loeff, T.~Pfister", "Temporal Fusion Transformers for Interpretable Multi-Horizon Time Series Forecasting", "International Journal of Forecasting", 2021,
                   "https://arxiv.org/abs/1912.09363", "journal", "深度学习", "可解释多步时序预测", "已核验"),
    "zhou2021informer": ("H.~Zhou, et al.", "Informer: Beyond Efficient Transformer for Long Sequence Time-Series Forecasting", "AAAI", 2021,
                         "https://arxiv.org/abs/2012.07436", "conf", "深度学习", "长序列 Transformer", "已核验"),
    "wu2021autoformer": ("H.~Wu, J.~Xu, J.~Wang, M.~Long", "Autoformer: Decomposition Transformers with Auto-Correlation for Long-Term Series Forecasting", "NeurIPS", 2021,
                         "https://arxiv.org/abs/2106.13008", "conf", "深度学习", "分解式长序列预测", "已核验"),
    "zeng2023dlinear": ("A.~Zeng, M.~Chen, L.~Zhang, Q.~Xu", "Are Transformers Effective for Time Series Forecasting?", "AAAI", 2023,
                        "https://arxiv.org/abs/2205.13504", "conf", "深度学习", "线性基线反证", "已核验"),
    "ansari2024chronos": ("A.~F.~Ansari, et al.", "Chronos: Learning the Language of Time Series", "TMLR", 2024,
                          "https://arxiv.org/abs/2403.07815", "journal", "深度学习", "时序基础模型（零样本）", "已核验"),
    "das2024timesfm": ("A.~Das, W.~Kong, A.~Sen, Y.~Zhou", "A Decoder-Only Foundation Model for Time-Series Forecasting", "ICML", 2024,
                       "https://arxiv.org/abs/2310.10688", "conf", "深度学习", "时序基础模型 TimesFM", "已核验"),
    "rasul2023lagllama": ("K.~Rasul, et al.", "Lag-Llama: Towards Foundation Models for Probabilistic Time Series Forecasting", "arXiv", 2023,
                          "https://arxiv.org/abs/2310.08278", "arxiv", "深度学习", "概率时序基础模型", "已核验"),
    "jiang2017": ("Z.~Jiang, D.~Xu, J.~Liang", "A Deep Reinforcement Learning Framework for the Financial Portfolio Management Problem", "arXiv", 2017,
                  "https://arxiv.org/abs/1706.10059", "arxiv", "强化学习", "端到端组合管理 RL", "已核验"),
    "liu2021finrl": ("X.-Y.~Liu, et al.", "FinRL: A Deep Reinforcement Learning Library for Automated Stock Trading in Quantitative Finance", "arXiv", 2020,
                     "https://arxiv.org/abs/2011.09607", "arxiv", "强化学习", "RL 交易开源框架", "已核验"),
    "nevmyvaka2006": ("Y.~Nevmyvaka, Y.~Feng, M.~Kearns", "Reinforcement Learning for Optimized Trade Execution", "ICML", 2006,
                      "https://doi.org/10.1145/1143844.1143929", "conf", "强化学习", "执行 RL 开山", "已核验"),
    "spooner2018": ("T.~Spooner, J.~Fearnley, R.~Savani, C.~Koukorinis", "Market Making via Reinforcement Learning", "AAMAS", 2018,
                    "https://arxiv.org/abs/1804.04216", "conf", "强化学习", "RL 做市", "已核验"),
    "guant2019": ("O.~Gu\\'eant, I.~Manziuk", "Deep Reinforcement Learning for Market Making in Corporate Bonds", "Applied Mathematical Finance", 2019,
                  "https://arxiv.org/abs/1910.13205", "journal", "强化学习", "深度 RL 做市", "已核验"),
    "araci2019finbert": ("D.~Araci", "FinBERT: Financial Sentiment Analysis with Pre-Trained Language Models", "arXiv", 2019,
                         "https://arxiv.org/abs/1908.10063", "arxiv", "NLP/LLM", "金融情感 BERT", "已核验"),
    "yang2020finbert": ("Y.~Yang, M.~C.~S.~UY, H.~Huang", "FinBERT: A Pretrained Language Model for Financial Communications", "arXiv", 2020,
                        "https://arxiv.org/abs/2006.08097", "arxiv", "NLP/LLM", "金融语料继续预训练", "已核验"),
    "huang2022finbert": ("A.~H.~Huang, H.~Wang, Y.~Yang", "FinBERT: A Large Language Model for Extracting Information from Financial Text", "Contemporary Accounting Research", 2023,
                         "https://doi.org/10.1111/1911-3846.12832", "journal", "NLP/LLM", "FinBERT 信息抽取", "已核验"),
    "wu2023bloomberggpt": ("S.~Wu, et al.", "BloombergGPT: A Large Language Model for Finance", "arXiv", 2023,
                           "https://arxiv.org/abs/2303.17564", "arxiv", "NLP/LLM", "金融领域大模型", "已核验"),
    "yang2023fingpt": ("H.~Yang, X.-Y.~Liu, C.~D.~Wang", "FinGPT: Open-Source Financial Large Language Models", "arXiv", 2023,
                       "https://arxiv.org/abs/2306.06031", "arxiv", "NLP/LLM", "开源金融大模型", "已核验"),
    "lopezlira2023": ("A.~Lopez-Lira, Y.~Tang", "Can ChatGPT Forecast Stock Price Movements? Return Predictability and Large Language Models", "SSRN", 2023,
                      "https://doi.org/10.2139/ssrn.4412788", "journal", "NLP/LLM", "LLM 新闻信号回测", "已核验"),
    "kebeixiu2019": ("Z.~Ke, B.~T.~Kelly, D.~Xiu", "Predicting Returns with Text Data", "NBER Working Paper 26186", 2019,
                     "https://doi.org/10.3386/w26186", "journal", "NLP/LLM", "文本预测收益", "已核验"),
    "yu2023finmem": ("Y.~Yu, H.~Li, Z.~Chen, Y.~Jiang, Y.~Li, D.~Zhang, R.~Liu, J.~W.~Suchow, K.~Khashanah", "FinMem: A Performance-Enhanced LLM Trading Agent with Layered Memory and Character Design", "arXiv", 2023,
                     "https://arxiv.org/abs/2311.13743", "arxiv", "NLP/LLM", "LLM 交易智能体", "已核验"),
    "lmasurvey2024": ("Z.~Ding, et al.", "Large Language Model Agent in Financial Trading: A Survey", "arXiv", 2024,
                      "https://arxiv.org/abs/2408.06361", "arxiv", "NLP/LLM", "LLM 交易智能体综述", "已核验"),
    "lookaheadbias2023": ("P.~Glasserman, C.~Lin", "Assessing Look-Ahead Bias in Stock Return Predictions Generated by GPT Sentiment Analysis", "The Journal of Financial Data Science", 2023,
                          "https://doi.org/10.3905/jfds.2023.1.143", "journal", "NLP/LLM", "LLM 前视偏差实测", "已核验"),
    "honesteval2026": ("O.~Ratnaike", "What Survives Honest Evaluation? Leakage-safe, Search-aware Assessment of LLM-Driven Trading", "arXiv", 2026,
                       "https://arxiv.org/abs/2608.27734", "arxiv", "评测方法", "泄漏安全评估", "部分核验"),
    "llmlongrun2025": ("Z.~Li, et al.", "Can LLM-Based Financial Investing Strategies Outperform the Market in the Long Run?", "arXiv", 2025,
                       "https://arxiv.org/abs/2505.07078", "arxiv", "NLP/LLM", "LLM 投资策略长周期评测", "部分核验"),
    "stockbench2025": ("A.~Wang, et al.", "StockBench: Can LLM Agents Trade Stocks Profitably in Real-World Markets?", "arXiv", 2025,
                       "https://arxiv.org/abs/2510.02209", "arxiv", "NLP/LLM", "LLM 交易智能体基准", "部分核验"),
    "investorbench2024": ("H.~Li, et al.", "INVESTORBENCH: A Benchmark for Financial Decision-Making Tasks with LLM-Based Agent", "ACL", 2025,
                          "https://doi.org/10.18653/v1/2025.acl-long.126", "conf", "NLP/LLM", "金融决策 LLM 基准", "已核验"),
    "wiese2020quantgan": ("M.~Wiese, R.~Knobloch, R.~Korn, P.~Kreibich", "Quant GANs: Deep Generation of Financial Time Series", "Quantitative Finance", 2020,
                          "https://doi.org/10.1080/14697688.2020.1730426", "journal", "生成式", "金融时序 GAN 生成", "已核验"),
    "takahashi2019": ("S.~Takahashi, Y.~Chen, K.~Tanaka-Ishii", "Modeling Financial Time-Series with Generative Adversarial Networks", "Physica A", 2019,
                      "https://doi.org/10.1016/j.physa.2019.121261", "journal", "生成式", "GAN 建模金融时序", "已核验"),
    "yoon2019timegan": ("J.~Yoon, D.~Jarrett, M.~van der Schaar", "Time-Series Generative Adversarial Networks", "NeurIPS", 2019,
                        "", "conf", "生成式", "监督式时序生成", "已核验"),
    "buehler2019deephedging": ("H.~Buehler, L.~Gonon, J.~Teichmann, B.~Wood", "Deep Hedging", "Quantitative Finance", 2019,
                               "https://arxiv.org/abs/1802.03042", "journal", "生成式", "生成模型 + 对冲联合训练", "已核验"),
    "byrd2020abides": ("D.~Byrd, M.~Hybinette, T.~H.~Balch", "ABIDES: Towards High-Fidelity Market Simulation for AI Research", "arXiv", 2020,
                       "https://arxiv.org/abs/1904.12066", "arxiv", "生成式", "离散事件市场仿真器", "已核验"),
    "park2023generative": ("J.~S.~Park, et al.", "Generative Agents: Interactive Simulacra of Human Behavior", "UIST", 2023,
                           "https://arxiv.org/abs/2304.03442", "conf", "生成式", "生成式智能体", "已核验"),
    "matsunaga2019": ("D.~Matsunaga, T.~Suzumura, T.~Takahashi", "Exploring Graph Neural Networks for Stock Market Predictions with Rolling Window Analysis", "arXiv", 2019,
                      "https://arxiv.org/abs/1909.10660", "arxiv", "图网络", "GNN 股票预测滚动窗对照", "已核验"),
    "feng2019rsr": ("F.~Feng, X.~He, X.~Wang, C.~Luo, Y.~Liu, T.-S.~Chua", "Temporal Relational Ranking for Stock Prediction", "ACM TOIS", 2019,
                    "https://doi.org/10.1145/3309547", "journal", "图网络", "时序关系排序", "已核验"),
    "chen2018gcn": ("Y.~Chen, Z.~Wei, X.~Huang", "Incorporating Corporation Relationship via Graph Convolutional Neural Networks for Stock Price Prediction", "ACM CIKM", 2018,
                    "https://doi.org/10.1145/3269206.3269269", "conf", "图网络", "公司关系图卷积", "已核验"),
    "xu2021hats": ("W.~Xu, et al.", "HATS: A Hierarchical Graph Attention Network for Stock Movement Prediction", "arXiv", 2019,
                   "https://arxiv.org/abs/1908.07999", "arxiv", "图网络", "层次图注意力", "已核验"),
    "wang2021thgnn": ("H.~Wang, et al.", "Temporal and Heterogeneous Graph Neural Network for Financial Time Series Prediction", "arXiv/CIKM", 2021,
                      "https://arxiv.org/abs/2305.08740", "arxiv", "图网络", "时序异质图", "已核验"),
    "sawhney2020": ("R.~Sawhney, S.~Agarwal, A.~Wadhwa, T.~Derr", "Deep Attentive Learning for Stock Movement Prediction from Social Media Text and Company Correlations", "EMNLP", 2020,
                    "https://doi.org/10.18653/v1/2020.emnlp-main.676", "conf", "图网络", "文本 + 公司关联图", "已核验"),
    "zhu2019": ("C.~Zhu", "Big Data as a Governance Mechanism", "The Review of Financial Studies", 2019,
                "https://doi.org/10.1093/rfs/hhy081", "journal", "另类数据", "大数据与公司治理", "已核验"),
    "jame2016": ("R.~Jame, R.~Johnston, S.~Markov, M.~C.~Wolfe", "The Value of Crowdsourced Earnings Forecasts", "Journal of Accounting Research", 2016,
                 "https://doi.org/10.1111/1475-679x.12121", "journal", "另类数据", "众包盈利预测", "已核验"),
    "katona2018": ("Z.~Katona, M.~Painter, J.~Tsoukalas, J.~Zhang", "On the Capital Market Consequences of Big Data: Evidence from Outer Space", "SSRN", 2018,
                   "https://doi.org/10.2139/ssrn.3222741", "journal", "另类数据", "卫星大数据与资本市场", "已核验"),
    "costa2022": ("G.~Costa, G.~N.~Iyengar", "End-to-End Risk Budgeting Portfolio Optimization with Neural Networks", "Annals of Operations Research", 2022,
                  "https://doi.org/10.1007/s10479-023-05539-4", "journal", "组合/执行/风控", "端到端风险预算", "已核验"),
    "zhang2020dlpo": ("Z.~Zhang, S.~Zohren, T.~Roberts", "Deep Learning for Portfolio Optimization", "The Journal of Financial Data Science", 2020,
                      "https://arxiv.org/abs/2005.13665", "journal", "组合/执行/风控", "端到端组合学习", "已核验"),
    "martin2011": ("R.~J.~Martin, F.~Sch\\\"oneborn", "Mean Reversion Pays, but Costs", "arXiv", 2011,
                   "https://arxiv.org/abs/1103.4934", "arxiv", "原理/边界", "均值回归成本敏感性", "已核验"),
    "qlib": ("X.~Yang, et al.", "Qlib: An AI-Oriented Quantitative Investment Platform", "arXiv", 2020,
             "https://arxiv.org/abs/2009.11189", "arxiv", "工具/基准", "开源量化研究平台", "已核验"),
    "bondreplication2026": ("A.~Dickerson, et al.", "The Corporate Bond Factor Replication Crisis", "arXiv", 2026,
                            "https://arxiv.org/abs/2604.07880", "arxiv", "评测方法", "债券因子复现危机", "部分核验"),
    "sezer2020survey": ("O.~B.~Sezer, M.~U.~Gudelek, A.~M.~Ozbayoglu", "Deep Learning for Financial Applications: A Survey", "Applied Soft Computing", 2020,
                        "https://doi.org/10.1016/j.asoc.2020.106384", "journal", "工具/基准", "方法罗列型综述代表", "已核验"),
    "mltopic2021": ("S.~Aziz, M.~Dowling, H.~Hammami, A.~Piepenbrink", "Machine Learning in Finance: A Topic Modeling Approach", "European Financial Management", 2021,
                    "https://doi.org/10.1111/eufm.12326", "journal", "工具/基准", "文献计量/主题建模型综述代表", "已核验"),
}

# 评测属性（M2 共同主键 + M4 增列）：key -> (样本外检验, 成本口径, 复现状态)
# 仅填可确证者；其余在生成时取默认值（未报告 / 未报告 / 未核实）。
EVAL = {
    # 理论 / 方法论文献
    "markowitz1952": ("不适用", "不适用", "不适用（理论）"),
    "fama1970": ("不适用", "不适用", "不适用（理论）"),
    "grossmanstiglitz1980": ("不适用", "不适用", "不适用（理论）"),
    "kyle1985": ("不适用", "不适用", "不适用（理论）"),
    "shleifer1997": ("不适用", "不适用", "不适用（理论）"),
    "almgrenchriss2000": ("不适用", "解析式", "可复现（理论）"),
    "martin2011": ("不适用", "解析式", "可复现（理论）"),
    "bollerslev1986": ("不适用", "不适用", "可复现"),
    "hamilton1989": ("不适用", "不适用", "可复现"),
    "rockafellar2000": ("不适用", "不适用", "可复现"),
    "mcneil2000": ("未报告", "不适用", "可复现"),
    "ledoitwolf2004": ("未报告", "不适用", "可复现"),
    "chekhlov2005": ("不适用", "不适用", "可复现"),
    "harvey2018": ("时间切分", "不适用", "可复现"),
    # 评测方法论
    "white2000": ("不适用（方法论）", "不适用", "可复现"),
    "sullivan1999": ("不适用（方法论）", "不适用", "可复现"),
    "harveylz2016": ("不适用（方法论）", "不适用", "可复现"),
    "mcleanpontiff2016": ("时间切分", "不适用", "可复现"),
    "jensen2023": ("时间切分", "不适用", "可复现"),
    "bailey2014pseudo": ("不适用（方法论）", "不适用", "可复现"),
    "bailey2014dsr": ("不适用（方法论）", "不适用", "可复现"),
    "bailey2016pbo": ("不适用（方法论）", "不适用", "可复现"),
    "lopezdeprado2018": ("不适用（方法论）", "不适用", "可复现"),
    "bondreplication2026": ("时间切分", "不适用", "部分复现"),
    "honesteval2026": ("前向留出", "未报告", "未核实"),
    # 监督学习 / 深度学习
    "gukellyxiu2020": ("滚动前向", "未报告", "部分复现"),
    "gukellyxiu2021": ("时间切分", "未报告", "部分复现"),
    "chenpelgerzhu2024": ("时间切分", "未报告", "部分复现"),
    "kellymalamudzhou2024": ("时间切分", "未报告", "未核实"),
    "fenggiglioxu2020": ("不适用（方法论）", "不适用", "可复现"),
    "krauss2017": ("时间切分", "未报告", "部分复现"),
    "fischerkrauss2018": ("时间切分", "报告成本敏感性", "部分复现"),
    "vaswani2017": ("标准划分", "不适用", "可复现"),
    "lim2021tft": ("标准划分", "不适用", "可复现"),
    "zhou2021informer": ("标准划分", "不适用", "可复现"),
    "wu2021autoformer": ("标准划分", "不适用", "可复现"),
    "zeng2023dlinear": ("标准划分", "不适用", "可复现"),
    "ansari2024chronos": ("标准划分", "不适用", "可复现"),
    "das2024timesfm": ("标准划分", "不适用", "可复现"),
    "rasul2023lagllama": ("标准划分", "不适用", "可复现"),
    "zhang2019deeplob": ("时间切分", "未报告", "部分复现"),
    "sirignano2019lob": ("时间切分", "未报告", "部分复现"),
    "tsantekidis2017": ("时间切分", "未报告", "部分复现"),
    "ntakaris2018fi2010": ("标准划分", "不适用", "可复现"),
    "cartea2015": ("不适用", "解析式", "可复现（理论）"),
    # 强化学习
    "deng2017": ("时间切分", "未报告", "部分复现"),
    "jiang2017": ("时间切分", "报告费率", "部分复现"),
    "liu2021finrl": ("时间切分", "可配置", "部分复现"),
    "nevmyvaka2006": ("时间切分", "内生化", "部分复现"),
    "spooner2018": ("时间切分", "内生化", "部分复现"),
    "guant2019": ("时间切分", "内生化", "部分复现"),
    # NLP / LLM
    "tetlock2007": ("时间切分", "不适用", "部分复现"),
    "bakerwurgler2006": ("时间切分", "不适用", "部分复现"),
    "loughranmcdonald2011": ("标准划分", "不适用", "可复现"),
    "araci2019finbert": ("标准划分", "不适用", "可复现"),
    "yang2020finbert": ("标准划分", "不适用", "可复现"),
    "huang2022finbert": ("标准划分", "不适用", "可复现"),
    "wu2023bloomberggpt": ("标准划分", "不适用", "部分复现"),
    "yang2023fingpt": ("标准划分", "不适用", "部分复现"),
    "lopezlira2023": ("时间切分", "未报告", "不可复现"),
    "kebeixiu2019": ("时间切分", "未报告", "部分复现"),
    "yu2023finmem": ("时间切分", "未报告", "不可复现"),
    "lmasurvey2024": ("不适用（综述）", "不适用", "不适用"),
    "lookaheadbias2023": ("时间切分", "不适用", "可复现"),
    "llmlongrun2025": ("前向留出", "未报告", "未核实"),
    "stockbench2025": ("前向留出", "未报告", "未核实"),
    "investorbench2024": ("标准划分", "不适用", "部分复现"),
    # 生成式
    "wiese2020quantgan": ("风格化事实检验", "不适用", "部分复现"),
    "takahashi2019": ("时间切分", "不适用", "部分复现"),
    "yoon2019timegan": ("标准划分", "不适用", "部分复现"),
    "buehler2019deephedging": ("时间切分", "交易成本", "部分复现"),
    "byrd2020abides": ("不适用", "内生化", "部分复现"),
    "park2023generative": ("不适用", "不适用", "可复现"),
    # 图网络
    "cohenfrazzini2008": ("时间切分", "未报告", "部分复现"),
    "feng2019rsr": ("时间切分", "未报告", "部分复现"),
    "chen2018gcn": ("时间切分", "未报告", "部分复现"),
    "matsunaga2019": ("时间切分", "未报告", "部分复现"),
    "xu2021hats": ("时间切分", "未报告", "部分复现"),
    "wang2021thgnn": ("时间切分", "未报告", "部分复现"),
    "sawhney2020": ("标准划分", "不适用", "部分复现"),
    "velickovic2018gat": ("标准划分", "不适用", "可复现"),
    # 另类数据
    "zhu2019": ("时间切分", "不适用", "不可复现"),
    "jame2016": ("时间切分", "不适用", "部分复现"),
    "katona2018": ("时间切分", "不适用", "不可复现"),
    # 组合 / 执行 / 风控
    "costa2022": ("时间切分", "报告", "部分复现"),
    "zhang2020dlpo": ("时间切分", "报告费率", "部分复现"),
    "almgren2005": ("不适用", "冲击模型", "部分复现"),
    "qlib": ("滚动前向（内置）", "可配置", "可复现"),
    "sezer2020survey": ("不适用（综述）", "不适用", "不适用"),
    "mltopic2021": ("不适用（综述）", "不适用", "不适用"),
}
EVAL_DEFAULT = ("未报告", "未报告", "未核实")

# 比较矩阵（M2：每行给出证据表编号；评测属性由 EVAL 统一供给，保证两表一致）
# key -> (数据/样本, 任务, 开源/许可)
MATRIX_EXTRA = {
    "gukellyxiu2020": ("美股 CRSP\\slash Compustat 1957--2016", "月度横截面收益、排序", "部分代码/数据受限"),
    "chenpelgerzhu2024": ("美股 1967--2016", "条件因子/定价核", "部分/数据受限"),
    "kellymalamudzhou2024": ("美股长样本", "收益预测（高维）", "部分"),
    "krauss2017": ("标普 500 成分 1992--2015", "日度统计套利", "部分代码"),
    "fischerkrauss2018": ("标普 500 成分 1992--2015", "日度方向预测", "部分代码"),
    "zhang2019deeplob": ("限价订单簿（多资产）", "短时价格方向", "数据受限"),
    "sirignano2019lob": ("美股限价订单簿", "短时中间价", "数据受限"),
    "ntakaris2018fi2010": ("FI-2010 公开订单簿", "中间价方向", "公开数据/代码"),
    "jiang2017": ("加密/多资产日频", "组合权重", "公开代码"),
    "liu2021finrl": ("美股日频", "交易/组合", "MIT、公开"),
    "nevmyvaka2006": ("历史订单簿（私有）", "最优执行", "未公开"),
    "spooner2018": ("仿真订单流", "做市报价", "公开代码"),
    "guant2019": ("公司债仿真", "做市报价", "公开代码"),
    "araci2019finbert": ("金融语料", "情感分类", "公开权重"),
    "huang2022finbert": ("财报 10-K/电话会", "信息抽取", "公开权重"),
    "lopezlira2023": ("新闻标题", "收益信号", "未公开"),
    "kebeixiu2019": ("新闻文本", "收益预测", "部分"),
    "yu2023finmem": ("股票日频 + 新闻", "LLM 智能体交易", "部分代码"),
    "wiese2020quantgan": ("金融时序", "生成", "公开代码"),
    "yoon2019timegan": ("通用时序", "生成", "公开代码"),
    "buehler2019deephedging": ("合成/半合成", "对冲", "公开代码"),
    "byrd2020abides": ("仿真市场", "仿真环境", "公开代码"),
    "feng2019rsr": ("美股关系图", "排序", "部分代码"),
    "xu2021hats": ("美股 + 概念图", "股价动向", "部分代码"),
    "cohenfrazzini2008": ("美股供应链", "横截面收益", "数据受限"),
    "katona2018": ("卫星数据", "资本市场后果", "数据私有"),
    "zhu2019": ("招聘/评价大数据", "公司治理", "数据私有"),
    "zhang2020dlpo": ("多资产", "端到端组合", "公开代码"),
    "costa2022": ("多资产", "风险预算组合", "公开代码"),
    "almgrenchriss2000": ("理论", "最优执行", "不适用"),
    "martin2011": ("理论/数值", "均值回归最优带", "不适用"),
}


ESCAPE = [("&", r"\&"), ("%", r"\%"), ("#", r"\#"), ("_", r"\_")]
TYPE_CN = {"journal": "期刊", "conf": "会议", "arxiv": "预印本", "book": "专著"}
OA_KEYS = {"grossmanstiglitz1980"}  # 链接为开放获取副本的条目，需如实标注
FAMILIES = ["原理/边界", "监督学习", "深度学习", "强化学习", "NLP/LLM", "生成式",
            "图网络", "另类数据", "组合/执行/风控", "评测方法", "工具/基准"]
# 证据表 A 的“方法族”列用短名，避免拉丁词（如 NLP/LLM）与斜杠造成列溢出
FAMILY_SHORT = {"原理/边界": "原理", "监督学习": "监督", "深度学习": "深度",
                "强化学习": "强化", "NLP/LLM": "NLP", "生成式": "生成",
                "图网络": "图网络", "另类数据": "另类", "组合/执行/风控": "组合执行",
                "评测方法": "评测", "工具/基准": "工具"}


def esc(s):
    for a, b in ESCAPE:
        s = s.replace(a, b)
    return s


def short_authors(au: str) -> str:
    names = []
    for p in au.split(","):
        if "et al" in p:
            continue
        w = p.replace("~", " ").split()
        if w:
            names.append(w[-1])
    if not names:
        return "佚名"
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return names[0] + " \\& " + names[1]
    return names[0] + " 等"


def assign_ids():
    """按方法族顺序确定性地分配证据表编号 E1..En，作为两表与矩阵的共同主键。"""
    k2id, rows = {}, []
    n = 0
    for fam in FAMILIES:
        for k, v in F.items():
            if v[6] != fam:
                continue
            n += 1
            k2id[k] = f"E{n}"
            rows.append((fam, k, v))
    return k2id, rows, n


def main():
    k2id, rows, n = assign_ids()

    # ---- references.tex ----
    lines = ["% 参考文献\n\\begin{thebibliography}{99}\n"]
    for k, v in F.items():
        au, ti, ve, yr, link, kind, fam, role, st = v
        tail = (f"\\href{{{link}}}{{{'doi' if 'doi.org' in link else 'link'}}}"
                if link else "（无 DOI）")
        lines.append(f"\\bibitem{{{k}}} {au}. {esc(ti)}. \\emph{{{esc(ve)}}}, {yr}. {tail}.\n")
    lines.append("\\end{thebibliography}\n")
    open(OUT_REF, "w", encoding="utf-8").write("\n".join(lines))

    # ---- evidence.tex（M2 共同主键 + M4 增列；拆为元数据表与评测属性表，以 E 编号互指）----
    ev = [
        "% 第12章 证据表",
        "\\section{证据表（核心来源清单）}\\label{sec:evidence}",
        "",
        "证据表由两张以 \\textbf{E 编号}为主键的子表构成：证据表 A 记元数据，证据表 B 记评测属性；两张表用同一套 E 编号互指，比较矩阵（第 \\ref{sec:matrix} 章）的每一行也标注对应的 E 编号。这样拆表是为了让“来源是什么”与“评测是否严谨”两条信息都能在同一宽度内读清，而不必把两者挤进一张宽表。",
        "",
        "\\textbf{核验等级约定}（两级）：\\textsc{已核验}=DOI/arXiv/官方链接与元数据互证；\\textsc{部分核验}=元数据确认、样本区间或参数细节待全文复核。\\textbf{\\textsc{已核验}仅指元数据层，不代表结论可靠}——结论是否可靠请对照证据表 B 的“复现状态”列。来源类型标注该条目是期刊、会议、预印本还是专著，便于读者自行判断同行评审状态。",
        "",
        "\\textbf{链接说明}：链接指向 DOI、arXiv 或官方来源；对无 DOI 的经典条目（专著、会议、杂志）标注“无 DOI”，不附替代链接；少数经典条目的链接为开放获取副本，已在“来源”列注明“OA 副本”。",
        "",
        "{\\footnotesize\\setlength{\\tabcolsep}{3pt}",
        "\\begin{xltabular}{\\textwidth}{@{}>{\\raggedright\\arraybackslash}p{0.7cm}>{\\raggedright\\arraybackslash}p{1.0cm}>{\\raggedright\\arraybackslash}X>{\\raggedright\\arraybackslash}p{2.2cm}>{\\raggedright\\arraybackslash}p{0.9cm}>{\\raggedright\\arraybackslash}p{0.9cm}>{\\raggedright\\arraybackslash}p{0.9cm}@{}}",
        "\\caption{证据表 A：元数据}\\\\",
        "\\toprule",
        "ID & 族 & 标题（作者，年） & 来源 & 年 & 类型 & 核验 \\\\",
        "\\midrule",
        "\\endhead",
    ]
    for fam, k, v in rows:
        au, ti, ve, yr, link, kind, _f, role, st = v
        sa = esc(short_authors(au))
        if link:
            tag = "arXiv" if "arxiv.org" in link else ("DOI" if "doi.org" in link else "链接")
            if k in OA_KEYS:
                tag = "OA 副本"
            src = f"\\href{{{link}}}{{{tag}}}"
        else:
            src = "无 DOI"
        ev.append(f"{k2id[k]} & {FAMILY_SHORT.get(fam, fam)} & {esc(ti)}（{sa}, {yr}） & "
                  f"{src} & {yr} & {TYPE_CN.get(kind, kind)} & {st} \\\\")
    ev += [
        "\\bottomrule",
        "\\end{xltabular}",
        "}",
        "",
        "\\noindent 表 A 中“关键定位”列（见表 B）的填写规范：限定为该条目在\\emph{本文论证中承担的角色}（如“机制来源”“基准”“失效边界例证”），不作质量评价，以免把主观判断混入事实栏。",
        "",
        "{\\small",
        "\\begin{xltabular}{\\textwidth}{@{}>{\\raggedright\\arraybackslash}p{0.7cm}>{\\raggedright\\arraybackslash}X>{\\raggedright\\arraybackslash}p{2.6cm}>{\\raggedright\\arraybackslash}p{2.4cm}>{\\raggedright\\arraybackslash}p{1.8cm}@{}}",
        "\\caption{证据表 B：纳入理由与评测属性}\\\\",
        "\\toprule",
        "ID & 关键定位（纳入理由） & 样本外检验 & 成本口径 & 复现状态 \\\\",
        "\\midrule",
        "\\endhead",
    ]
    for fam, k, v in rows:
        role = esc(v[7])
        oos, cost, rep = EVAL.get(k, EVAL_DEFAULT)
        ev.append(f"{k2id[k]} & {role} & {esc(oos)} & {esc(cost)} & {esc(rep)} \\\\")
    ev += [
        "\\bottomrule",
        "\\end{xltabular}",
        "}",
        "",
        f"\\noindent 共收录 {n} 条核心来源。“样本外检验/成本口径/复现状态”三列仅填可确证者，未核实的一律写“未报告/未核实”，不替作者补齐。元数据核验脚本见 \\texttt{{scripts/}} 下的 \\texttt{{verify\\_refs*.py}}，结果见 \\texttt{{outputs/}}。",
        "",
    ]
    open(OUT_EVI, "w", encoding="utf-8").write("\n".join(ev))

    # ---- matrix.tex（M2：每行给出证据表编号；评测属性取自 EVAL，保证两表一致）----
    mx = [
        "% 第13章 统一比较矩阵",
        "\\section{统一比较矩阵}\\label{sec:matrix}",
        "",
        "第 \\ref{sec:evidence} 章的证据表回答“来源是什么”，这一章的矩阵回答另一个问题：“把不同工作的数字放在一起看，它们究竟可比吗？”矩阵按六列对齐——数据与样本、任务、样本外检验、成本口径、开源与许可、复现状态；\\textbf{每行首列给出对应的证据表编号}，可与证据表 B 逐条对照。填表原则是：原文未报告的项一律写“未报告”，绝不替作者补齐。",
        "",
        "{\\small",
        "\\begin{xltabular}{\\textwidth}{@{}>{\\raggedright\\arraybackslash}p{0.7cm}>{\\raggedright\\arraybackslash}X>{\\raggedright\\arraybackslash}X>{\\raggedright\\arraybackslash}p{1.9cm}>{\\raggedright\\arraybackslash}p{1.2cm}>{\\raggedright\\arraybackslash}p{1.2cm}>{\\raggedright\\arraybackslash}p{1.2cm}>{\\raggedright\\arraybackslash}p{1.2cm}@{}}",
        "\\caption{统一比较矩阵（代表性工作，含证据表编号）}\\\\",
        "\\toprule",
        "ID & 工作 & 数据/样本 & 任务 & 样本外 & 成本口径 & 开源/许可 & 复现状态 \\\\",
        "\\midrule",
        "\\endhead",
    ]
    for k, (data, task, lic) in MATRIX_EXTRA.items():
        au, ti, ve, yr = F[k][0], F[k][1], F[k][2], F[k][3]
        oos, cost, rep = EVAL.get(k, EVAL_DEFAULT)
        mx.append(f"{k2id[k]} & {esc(short_authors(au))}\\allowbreak（{yr}） & {data} & {task} & "
                  f"{esc(oos)} & {esc(cost)} & {esc(lic)} & {esc(rep)} \\\\")
    mx += [
        "\\bottomrule",
        "\\end{xltabular}",
        "}",
        "",
        "\\noindent 读这张表，有三点值得单独指出。",
        "",
        "第一，\\textbf{“成本口径”一列里“未报告”出现的频率高得惊人}。这意味着大量方法学结论，是在没有计入摩擦的前提下得出的；而按第 \\ref{sec:foundations} 章的缝隙判据，未扣成本的结论无法判断是否可交易。这不是苛责，而是选择偏差的温床。",
        "",
        "第二，\\textbf{“样本外”一列里“时间切分”与“滚动前向”混杂}。一次性的时间切分容易被反复用于选模型，从而失去样本外的意义；真正可信的是滚动前向。表格区分这两者，是希望读者在读原文时能分辨。",
        "",
        "第三，\\textbf{可复现性与“离摩擦的远近”高度相关}。理论工作（Almgren--Chriss、Martin--Sch\\\"oneborn）与公开数据工作（FI-2010、FinBERT）复现状态最好；一旦涉及私有数据（另类数据）或商业模型（LLM），复现状态立刻掉到“不可复现”。这与第 \\ref{sec:repro_audit} 章的结论互相印证。",
        "",
        "本章要记住的一句话是：\\textbf{把工作摆进同一张矩阵，你才会发现——真正无法比较的，往往不是方法，而是它们各自缺的那几列。}",
        "",
    ]
    open(OUT_MX, "w", encoding="utf-8").write("\n".join(mx))

    json.dump({"key2id": k2id, "n": n, "refs": F},
              open(OUT_META, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"references 条目: {len(F)}")
    print(f"证据表条目: {n}")
    print(f"比较矩阵行数: {len(MATRIX_EXTRA)}")
    print(f"已写: {OUT_REF}\n已写: {OUT_EVI}\n已写: {OUT_MX}")


if __name__ == "__main__":
    main()
