# 均值回归策略研究综述（Mean Reversion Strategy Survey）

有史以来至今的均值回归交易策略文献证据、评测口径与可复现性综述。系统梳理经典反转效应、统计套利/配对交易、时序均值回归模型、期货与波动率均值回归、机器学习与强化学习前沿五大方法族，并以「评测维度适配矩阵」对超过 30 篇核心来源逐篇核验。

## 内容概览

| 章节 | 内容 |
|---|---|
| 1 | 引言与综述口径（检索策略、八维核验矩阵适配） |
| 2 | 理论根基（OU 过程、方差比检验、协整、行为金融解释） |
| 3 | 分方法族综述（经典反转 / 统计套利 / 时序模型 / 期货与波动率 / ML 前沿） |
| 4 | 证据表（R1–R47 + I1–I5，全部链接 DOI/arXiv/官方仓库） |
| 5 | 统一比较矩阵（样本 / 信号 / 样本外 / 概率预测 / 成本 / 许可 / 基准 / 污染审计） |
| 6 | 结论置信度分级 |
| 7 | 评测数据污染与不可比设定审计 |
| 8 | 可复现实验建议（P0–P3） |
| 9 | 结论与边界 |
| 10 | 复核清单：已执行结果与剩余待办 |
| 11 | 均值回归策略当前局限性摘要 |
| 12 | 当前研究现状、遗留课题、未来方向（含量化指标体系、可执行实验方案、研究路线图） |

## 目录结构

```
mean_reversion_survey/
├── README.md                          # 本文档
├── main.tex                           # 主文档（ctexart，xelatex 编译）
├── mean_reversion_survey.pdf          # 编译成品（30 页）
└── sections/                          # 章节文件（由 main.tex \input 引用）
    ├── evidence.tex                   # 第 4 章 证据表
    ├── matrix.tex                     # 第 5 章 统一比较矩阵
    ├── checklist.tex                  # 第 10 章 复核清单
    ├── limitations.tex                # 第 11 章 局限性摘要
    ├── future.tex                     # 第 12 章 现状/遗留/路线图
    └── references.tex                 # 参考文献（thebibliography，全部带链接）
```

## 编译方法

```powershell
xelatex -interaction=nonstopmode main.tex   # 连续执行三次以生成目录与交叉引用
```

依赖：TeX Live / MiKTeX（`ctexart`、`booktabs`、`longtable`、`hyperref` 等）。

## 来源与核验状态

- 元数据经多源交叉核验：OpenAlex / arXiv API / Crossref / Semantic Scholar / 出版社官方页 / GitHub API / Web 检索（检索与核验脚本见 `d:\Finance\均值回归文献综述\scripts\`）。
- 证据表全部条目状态为「已核验」（元数据层）；R15、R21、I4、I5、R34–R47 已于 2026-10-06 深度复核升级，论文内部参数细节仍留待全文复核（见第 10 章清单）。
- 引用计数与链接核验截止于 2026-10-06。

## 许可

本文档内容仅供研究与学习使用。引用的论文、数据（CRSP/WRDS 等）与代码仓库（Microsoft Qlib 等）归各自版权方所有，使用需遵守相应许可协议。
