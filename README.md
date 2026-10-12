# 量化投研写作仓库

这里存放我（叨客宁宁）在量化交易方向的写作，分为研究综述、系统教程、策略方法论与交易规则、理论研究四类。多数文章同时提供 LaTeX 源文件与编译好的 PDF；涉及实证的项目会附上扫描或回测代码、输出数据，便于逐页核对与重新复现。

## 研究综述

| 文件夹 | 内容 | 形态 |
|---|---|---|
| [vix_survey](vix_survey) | VIX 研究的两个版本，围绕信息含量、方差风险溢价、期限结构、衍生品定价与交易策略，梳理近二十年文献 | tex + pdf（两版） |
| [trend_following_survey](trend_following_survey) | 《趋势跟踪：从直觉到失效的边界》，面向普通读者的完全指南，把趋势跟踪拆成理论根源、实证依据、组合构建、机器学习、尾部风险与微观结构分别讨论 | tex + pdf |
| [mean_reversion_survey](mean_reversion_survey) | 均值回归策略研究综述，覆盖经典反转、统计套利、时序均值回归、期货与波动率、机器学习五个方法族，三十余篇核心来源逐篇核验评测口径 | tex + pdf |
| [ai-finance-survey](ai-finance-survey) | 《AI 在金融交易中的应用：研究综述》，以“信息→定价偏差→可交易缝隙”为主线，用方法族与交易环节双轴组织，逐条标注评测口径、复现状态与失效边界 | tex + pdf + 代码/数据 |
| [ai_flavor_survey](ai_flavor_survey) | 生成式文本“AI 味”的成因、表现、检测与去除方法综述，附核心证据表与统一比较矩阵 | tex + pdf + html + 图表 |
| [期货交易策略深度综述](期货交易策略深度综述) | 按利润来源把期货策略重构为趋势、均值回归、Carry、截面四支主干，正文约两万字，附可复现实验建议 | tex + pdf + 分页图 |
| [期货基本面分析综述](期货基本面分析综述) | 按信息载体把期货基本面分析归为供需平衡、期限结构、成本曲线、事件与政策四类，商品期货与金融期货并重，100 条文献逐条核验元数据 | tex + pdf |
| [精神分析金融交易综述](精神分析金融交易综述) | 精神分析视角在金融交易行为研究中的文献综述，含普通版与深度版两个成稿及文献检索脚本 | docx（两版）+ 脚本 |
| [kakeya_4d_survey](kakeya_4d_survey) | 《OpenAI 四维挂谷猜想工作综述》：核验两篇 OpenAI 手稿的事实状态与依赖链，重建四维证明的技术骨架，以四分类法梳理核心技术的继承、门内改造与跨门派借入，附装置精确定义与极值原理对比附录 | tex + pdf + 修改说明 |

## 系统教程

| 文件夹 | 内容 | 形态 |
|---|---|---|
| [alpha_beta_tutorial](alpha_beta_tutorial) | 从 Alpha/Beta 分解出发，走完因子构建、行业与市值中性化、标准化的完整因子量化链路（深度版） | tex + pdf |
| [market_regime_tutorial](market_regime_tutorial) | 从平稳性失效这一本质问题出发，覆盖变点检测、状态空间、前沿方法、验证体系、策略耦合与工程映射；含 11 个章节文件、图表与独立文献库 | tex + pdf + bib |
| [mean_reversion_tutorial](mean_reversion_tutorial) | 以收益自相关为入口，建立与动量对偶的均值回归因子链路（深度版） | tex + pdf |

## 策略方法论与交易规则

| 文件夹 | 内容 | 形态 |
|---|---|---|
| [trend_following_strategy_evaluation](trend_following_strategy_evaluation) | 论证趋势跟踪收益的右偏乘法结构，指出 Sharpe 等对称指标的系统性误判，给出单笔质量、资金曲线、极端尾部三层评价工作台 | pdf |
| [trend_position_management](trend_position_management) | 把趋势溢价落到可执行的仓位纪律，涵盖信号、仓位、加减仓与止盈止损（深度·自含·实证） | tex + pdf |
| [mean_reversion_position_management](mean_reversion_position_management) | 从负自相关载体出发，建立均值回归与统计套利可运行的仓位纪律（深度·自含·实证） | tex + pdf |
| [trend_meanreversion_comparison](trend_meanreversion_comparison) | 把趋势跟踪与均值回归放在同一自相关结构下比较本质异同与执行分野，并用统一口径在 A 股做全景实证 | tex + pdf + 代码/输出 |
| [trend_meanreversion_rules](trend_meanreversion_rules) | 把上述比较的实证结论翻译为可执行交易规则，附回测引擎、协整配对筛选与上线前多重检验校正代码 | tex + pdf + 代码/测试 |
| [quant_supply_demand_report](quant_supply_demand_report) | 全国量化基金人才需求与供给的调查笔记，数据均来自官方与可查证的公开渠道 | tex + pdf |

## 理论研究

| 文件夹 | 内容 | 形态 |
|---|---|---|
| [交易缝隙理论](交易缝隙理论) | 《交易缝隙的观测理论》，区分“能预测”与“能赚钱”，在时间尺度与参照系下建立可交易性判据，附真实数据扫描代码与输出 | tex + pdf + 代码/输出 |

## 编译说明

- 除特别说明外，进入对应目录用 XeLaTeX 连续编译两遍，目录与交叉引用在第二遍收敛：

      xelatex -interaction=nonstopmode main
      xelatex -interaction=nonstopmode main

- `market_regime_tutorial` 使用 biblatex 与 biber，编译顺序为：

      xelatex market_regime_tutorial
      biber market_regime_tutorial
      xelatex market_regime_tutorial
      xelatex market_regime_tutorial

- 统一编译环境为 XeLaTeX 加 ctex 宏包，纸张 A4，不适用 pdflatex。
- `kakeya_4d_survey` 另附 `build.ps1`（PowerShell 7）：多遍 XeLaTeX 自动收敛、日志体检（零错误、零 Overfull、零缺字、零书签告警）与 `-Clean` 中间文件清理；手工编译时主文件名为 `OpenAI四维挂谷猜想工作综述`。
- `精神分析金融交易综述` 为 docx 成品，没有 LaTeX 源文件；`ai_flavor_survey` 另提供可直接阅读的 HTML 版本。

## 使用与引用

- 只想阅读时，直接打开各文件夹内的 PDF（或 docx、html）。
- 引用其中观点请以各文文末的参考文献为准，本 README 的一句话介绍不作为出处。
- 文件夹内自带 README 的（如 `ai-finance-survey`、`mean_reversion_survey`），细节以该文件为准。
- `code/`、`scripts/`、`outputs/` 等目录是对应文章的实证材料，口径与文章绑定，不作为独立软件维护。

作者：叨客宁宁

