# AI 在金融交易中的应用：研究综述（AI in Financial Trading Survey）

一份聚焦“可落地复现”的研究综述。以“信息 → 定价偏差 → 可交易缝隙”为主线，用「方法族 × 交易环节」双轴框架，系统梳理 AI 在金融交易中的应用，并对每条关键结论给出评测口径、复现状态与失效边界。

作者：叨客宁宁

## 内容概览

| 部分 | 章节 | 内容 |
|---|---|---|
| 前置 | 摘要 / 第 1 章 | 检索口径（多源交叉核验）、范围界定、读法 |
| I 原理 | 第 2 章 | 交易的信息论基础与 AI 的作用位置（EMH、Grossman–Stiglitz、Kyle、低信噪比、可交易缝隙判据） |
| II 双轴综述 | 第 3–11 章 | 双轴框架；监督学习 / 深度序列 / 强化学习 / NLP 与大模型 / 生成式 / 图神经网络六族；另类数据与微观结构；交易环节横向整合 |
| III 落地 | 第 12–17 章 | 证据表（≥80 来源）、统一比较矩阵、评测污染审计、复现状态核验表、可复现实验方案 P0–P3、开源生态 |
| IV 结论 | 第 18–21 章 | 结论置信度分级、局限性摘要与反方证据、研究现状与路线图、复核清单 |

## 目录结构

```
AI金融交易综述/
├── README.md                       # 本文档
├── main.tex                        # 主文档（ctexart，xelatex 编译）
├── AI金融交易综述.pdf               # 编译成品（70 页）
├── docs/                           # 衍生交付（LaTeX + 编译 PDF）
│   ├── peer_review.tex / peer_review.pdf          # 同行评审报告（5 视角，9 页）
│   ├── peer_review_round2.tex / .pdf              # 第二轮评审报告（修订稿复核 + 修订状态，8 页）
│   ├── peer_review_round3.tex / .pdf              # 第三轮评审报告（成本代表性、DSR 理由、指代错位，8 页）
│   ├── implementation_plan.tex / .pdf             # 落地实施计划（Phase 0--4，7 页）
│   ├── investor_brief.tex / investor_brief.pdf    # 面向非技术投资者的摘要（约 3100 字，4 页）
│   ├── change_summary.tex / change_summary.pdf    # 复权因子与交易制度掩码变更摘要（6 页，含后续两轮指引）
│   └── change_summary_round2.tex / .pdf           # 成本口径修正与统计披露补齐变更摘要（6 页）
│   └── illiquidity_note.tex / .pdf                # 非流动性线索跟进分析（4 页）
│   └── size_control_plan.tex / .pdf               # 剥离规模因子的补充方案（5 页）
│   └── share_source_note.tex / .pdf               # 股本单一来源风险补充说明（4 页）
├── sections/                       # 章节文件（由 main.tex \input 引用）
│   ├── abstract.tex / intro.tex / foundations.tex / framework.tex
│   ├── supervised.tex / deep.tex / rl.tex / nlp_llm.tex
│   ├── generative.tex / gnn.tex / altdata.tex / integration.tex
│   ├── evidence.tex / matrix.tex / audit.tex / repro_audit.tex
│   ├── repro_protocol.tex / ecosystem.tex
│   ├── confidence.tex / limitations.tex / future.tex / checklist.tex
│   └── references.tex
├── code/                           # 可复现实验协议参考实现（P0--P2）
│   ├── data.py / real_data.py / costs.py / eval.py / baseline.py / run.py
│   ├── diag_ls_lo.py               # 单特征多空 vs 仅多头（可实施）对照
│   ├── diag_adjust_effect.py       # 复权口径对截面 IC 的影响对照
│   ├── audit_cost_caliber.py       # 成本口径审计（ADV 假设 vs 样本实际成交额）
│   ├── diag_alpha_beta.py          # 市场基准与 beta/alpha 分解、rand10 与量比关系
│   ├── audit_significance.py       # IC 序列相关与 Newey–West 调整、候选池有效试验数
│   ├── audit_cost_by_candidate.py  # 候选级换手与成本敏感性（成本结论代表性问题）
│   ├── audit_illiquidity.py        # 非流动性跟进：分层、子期、可投资子集、竞品相关、压力期、成本稳健
│   ├── audit_size_neutral.py       # 规模中性化：双重排序、回归取残差、层内多空合成
│   ├── audit_share_source.py       # 股本数据来源风险：序列形态五项自检
├── scripts/                        # 检索、核验、审计脚本
│   ├── retrieve_sources.py / build_pool.py / show_pool.py
│   ├── match_keys.py / verify_refs.py / audit_repro.py / verify_adjust.py
└── outputs/                        # 中间产物（来源池、核验结果、审计结果）
    ├── sources.json / pool.json / refs_verified.json / repro_audit.json
    ├── hfq_factors.json            # AKShare 后复权因子缓存（首次运行抓取，之后离线复用）
    ├── adjust_check.json           # 复权交叉核验的参考价缓存（全量 400 只）
    ├── real_universe.json          # 第 21 章实证冻结的 400 只代码清单与逐股 ADV
    ├── outstanding_shares.json     # 逐日流通股本缓存（规模中性化用，首次联网后离线复用）
```

## 编译方法

```powershell
xelatex -interaction=nonstopmode main.tex   # 连续执行三次以生成目录与交叉引用
```

依赖：TeX Live / MiKTeX（`ctexart`、`booktabs`、`longtable`、`hyperref` 等）。

## 运行参考实现（P0--P2）

```powershell
cd code
python run.py            # 合成时点面板（默认），依赖：numpy
python run.py --real     # 通达信真实日线最小实证（后复权 + 交易制度掩码）
python diag_ls_lo.py     # 单特征多空 vs 仅多头（可实施）对照
python diag_adjust_effect.py   # 复权与否对截面 IC 的影响
python diag_alpha_beta.py      # 市场基准与 beta/alpha 分解
python audit_cost_caliber.py   # 成本口径审计（ADV 假设 vs 样本实际成交额）
```

输出：候选池的样本内/样本外指标、成本三档对比、缩水夏普（DSR）、回测过拟合概率（PBO）与试验账本 `trial_ledger.json`（`--real` 输出 `trial_ledger_real.json`）。

数据说明：

- 默认 `data.py` 生成的是**合成时点面板**，仅用于验证评测流程，不代表任何真实市场结论。
- `--real` 由 `real_data.py` 读取**本地通达信 vipdoc 日线**（自动发现目录，可用 `vipdoc=` 参数指定），特征与收益基于后复权价；涨跌停按封板价精确判定（5/10/20/30\% 自动区分）、一字板与停牌不可成交、新股上市初期剔除。完整口径与边界见 `real_data.py` 文件头与论文第 21 章。
- **复权因子的外部依赖（如实标注）**：通达信本地权息文件 `gbbq` 在本机为加密存储、无法解析，故复权因子取自 AKShare（第三方兜底），缓存于 `outputs/hfq_factors.json`，首次运行需联网、之后离线复用。该拼装链经 `scripts/verify_adjust.py` 交叉核验（通达信原始价 × 因子 vs AKShare 后复权价，最大相对偏差 $7.8\times10^{-4}$）。

## 来源与核验状态

- 元数据经多源交叉核验：OpenAlex / arXiv API / Crossref / GitHub API。
- 去重后来源池 528 条（期刊/Crossref 178，arXiv 350）；检索与核验脚本见 `scripts/`，结果见 `outputs/`。
- 复现状态核验表的仓库信息经 GitHub API 实测（2026-10-09）。
- 证据表逐条标注核验状态：已核验 / 部分核验 / 待复核。

## 许可

本文档内容仅供研究与学习使用。引用的论文、数据（CRSP/WRDS 等）与代码仓库（Microsoft Qlib、FinRL 等）归各自版权方所有，使用需遵守相应许可协议。
