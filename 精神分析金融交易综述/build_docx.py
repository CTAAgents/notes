# -*- coding: utf-8 -*-
"""生成《精神分析在金融交易中的研究》深度综述 docx。
纯内容拼装，无外部依赖（除 python-docx）。
"""
import os
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "精神分析在金融交易中的研究_综述.docx")

CN_BODY = "宋体"
CN_HEAD = "黑体"
EN_BODY = "Times New Roman"
EN_HEAD = "Arial"


def _font(run, cn=CN_BODY, en=EN_BODY, size=10.5, bold=False, italic=False, color=None):
    run.font.name = en
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    if color:
        run.font.color.rgb = RGBColor(*color)
    rpr = run._element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.append(rf)
    rf.set(qn("w:eastAsia"), cn)
    rf.set(qn("w:ascii"), en)
    rf.set(qn("w:hAnsi"), en)


def para(doc, text, size=10.5, bold=False, italic=False, align="both", first_indent=True,
         cn=CN_BODY, en=EN_BODY, space_before=0, space_after=6, line=1.5, color=None):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing = line
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    if align == "both":
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    elif align == "center":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif align == "left":
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    if first_indent:
        pf.first_line_indent = Pt(size * 2)
    # 支持 **加粗** 内联
    parts = text.split("**")
    for i, seg in enumerate(parts):
        if not seg:
            continue
        r = p.add_run(seg)
        _font(r, cn=cn, en=en, size=size, bold=(bold or i % 2 == 1), italic=italic, color=color)
    return p


def h(doc, text, level=1):
    sizes = {1: 16, 2: 13.5, 3: 12}
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(14 if level == 1 else 10)
    pf.space_after = Pt(8 if level == 1 else 6)
    pf.line_spacing = 1.3
    pf.keep_with_next = True
    r = p.add_run(text)
    _font(r, cn=CN_HEAD, en=EN_HEAD, size=sizes[level], bold=True)
    return p


def bullet(doc, text, size=10.5):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing = 1.5
    pf.space_after = Pt(3)
    pf.left_indent = Pt(21)
    pf.first_line_indent = Pt(-10.5)
    r = p.add_run("— " + text)
    _font(r, size=size)
    return p


def set_cell(cell, text, size=9.5, bold=False, align="left"):
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.space_before = Pt(2)
    if align == "center":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text)
    _font(r, size=size, bold=bold)


def table(doc, headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, htxt in enumerate(headers):
        set_cell(t.rows[0].cells[i], htxt, size=9.5, bold=True, align="center")
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            set_cell(cells[i], str(v), size=9)
    if widths:
        for r_ in t.rows:
            for i, w in enumerate(widths):
                r_.cells[i].width = Cm(w)
    para(doc, "", first_indent=False, space_after=2)
    return t


def build():
    doc = Document()
    # 页边距 A4
    sec = doc.sections[0]
    sec.page_width = Cm(21.0)
    sec.page_height = Cm(29.7)
    sec.left_margin = Cm(3.0)
    sec.right_margin = Cm(3.0)
    sec.top_margin = Cm(2.5)
    sec.bottom_margin = Cm(2.5)

    # ---------- 封面 ----------
    para(doc, "", first_indent=False, space_after=60)
    para(doc, "精神分析在金融交易中的研究", size=24, bold=True, align="center",
         first_indent=False, cn=CN_HEAD, en=EN_HEAD, space_after=10)
    para(doc, "——从弗洛伊德到情绪金融，再到拉康式政治经济学",
         size=13.5, align="center", first_indent=False, cn=CN_HEAD, en=EN_HEAD, space_after=40)
    para(doc, "一份批判性综述", size=14, align="center", first_indent=False, space_after=90)
    para(doc, "叨客宁宁", size=12, align="center", first_indent=False, space_after=0)
    doc.add_page_break()

    # ---------- 摘要 ----------
    h(doc, "摘要", 1)
    para(doc, "金融交易长期被两种叙事支配：一种是教科书里的理性人，一种是行为金融里"
              "“有偏差的人”。两者共享一个前提——情绪与无意识即便被承认，也只被当作需要被识别、"
              "被纠正的噪音。本文梳理第三条路径：以精神分析的无意识理论来解释交易与市场行为。"
              "它不满足于罗列偏差，而是追问欲望从哪里来、为什么明知故犯、为什么亏损会反复。"
              "文章沿五条研究路线展开：金钱的精神分析学（弗洛伊德、亚伯拉罕、费伦齐一脉）、"
              "群体心理学与泡沫的情感轨迹（勒庞、弗洛伊德、比昂）、情绪金融这一独立范式"
              "（Tuckett 与 Taffler）、交易者病理（贪婪、成瘾与赌博的重合）、以及拉康取向的政治经济学"
              "（Žižek、Pignot、Bjerg）。在此之上，本文把精神分析的主张与行为金融、神经金融的证据"
              "并置，逐条评估其可检验性与证据强度，并给出可复现实验建议。结论是克制的："
              "精神分析在“机制解释”上提供了别处没有的深度，在“预测能力”上仍弱于行为金融，"
              "它的价值取决于能否把临床概念翻译成可测量、可反驳的命题。")
    para(doc, "**关键词**：精神分析；金融交易；无意识；情绪金融；幻觉客体；拉康；交易成瘾；行为金融", first_indent=False)
    para(doc, "**说明**：本文为文献综述，作者系综述撰写者，非原创研究者；所引文献均在文末列出，"
              "证据等级在附录 C 逐条标注。检索于 2026 年 10 月完成。", size=9.5, first_indent=False, color=(90, 90, 90))
    doc.add_page_break()

    # ---------- 1 引言 ----------
    h(doc, "一、引言：为什么金融交易值得精神分析来看一眼", 1)
    para(doc, "先摆出一个不太好回答的现象。绝大多数主动交易者在长期是亏钱的，这一点被反复"
              "验证（巴西期货市场的研究显示，坚持交易超过 300 个交易日的人里 97% 最终亏损[36]）；"
              "同一个亏钱的人，第二天还会打开交易软件。理性人假设解释不了这个动作，行为金融把它"
              "归因于认知偏差，可偏差清单越列越长，也没有回答一个更朴素的问题：**为什么知道了偏差，"
              "仍然照犯不误？**")

    h(doc, "1.1 理性人假设的两道裂缝", 2)
    para(doc, "有效市场假说与组合理论把价格当作信息的函数，把投资者当作效用最大化的计算器[31]。"
              "这套框架在解释资产定价的平均行为上极其成功，但它有两个地方一直没法自洽。第一，"
              "它无法解释系统性偏离的持续存在——泡沫不是随机噪声，而是有模式、有节奏、有情绪温度的过程。"
              "第二，它把“不确定性”和“风险”混为一谈：概率分布已知的叫风险，未来的不可知叫不确定性；"
              "而真实交易面对的，几乎全是后者。凯恩斯早就用“动物精神”提醒过市场的非理性驱动[30]，"
              "罗闻全后来用适应性市场假说主张理性与非理性会随环境变迁[32]，"
              "这些声音长期被主流定价模型当作背景噪音。")
    para(doc, "行为金融补上了第一道裂缝。卡尼曼与特沃斯基的前景理论证明，人对得失的评价不对称，"
              "损失的痛感大约是同等收益快感的 2.25 倍[27]，参考点决定选择，风险偏好会随盈亏翻转。"
              "此后锚定、羊群、过度自信、心理账户被一一纳入模型，投资者从“理性人”变成了"
              "“可预测的犯错者”[40]。在资产定价一侧，丹尼尔、赫什莱费尔与苏布拉马尼亚姆"
              "进一步把投资者心理直接写进定价模型，用过度反应与反应不足来解释动量与反转[47]，"
              "赫什莱费尔则系统整理了“投资者心理与资产定价”的路线图[48]。可是第二道裂缝仍在：行为金融默认偏差是可以被意识、被学习、"
              "被克服的，只要你知道自己有偏差。市场里的经验却相反——知道得越清楚的人，有时亏得更狠。")

    h(doc, "1.2 精神分析切入的，是“知道却做不到”这一层", 2)
    para(doc, "精神分析提供的是一条不同的解释线。它假定人的大部分心理活动在意识之外运行，"
              "欲望与恐惧并不总是能被自我看穿；因此“知道偏差”和“不再犯偏差”之间，隔着一整套"
              "无意识的防御与幻想机制。用它看交易，能处理三类行为金融难以处理的现象：其一，"
              "**明知风险却反复重仓**——不是信息不足，而是幻想压倒了现实检验；其二，"
              "**亏损后的自我惩罚式交易**——弗洛伊德在分析陀思妥耶夫斯基时提出，赌徒存在"
              "“为输而赌”的无意识冲动，赌的目的是赎罪而非获利[2][24]；其三，"
              "**群体层面的同步狂热与恐慌**——市场像一群人，而不像一堆独立计算器[6][1][7]。")
    para(doc, "需要马上说清楚的是：这条路径的强项是解释，弱项是预测与证伪。波普尔早就把精神分析"
              "列为“不可证伪因此不科学”的典型[41]，格林鲍姆则更细致地指出，即便可证伪，"
              "临床素材本身作为证据也大打折扣[42]。本文不会回避这个质疑，反而把它作为贯穿全文的"
              "衡量尺度：每一条精神分析的主张，我们都要问一句——它拿什么被反驳？")

    h(doc, "1.3 范围、方法与结构", 2)
    para(doc, "本文采用“精神分析为骨架、行为金融与神经金融为对照层”的组织方式。检索覆盖"
              "英文与中文文献，兼顾早期经典原著与近二十年的实证研究，来源包括 arXiv、OpenAlex、"
              "Crossref、Semantic Scholar 与公开网络检索；由于本次 Giiisp 论文接口未配置鉴权令牌，"
              "其结果标记为接口受限，相关命中改用开放源交叉核验。全部来源见附录 E，"
              "证据强度见附录 A 与附录 C。")
    para(doc, "文章结构如下：第二章建立概念工具箱；第三章讲“钱”的精神分析学；第四章从个体走到"
              "群体与泡沫；第五章专论情绪金融这一独立范式；第六章处理交易者病理；第七章进入拉康"
              "取向的政治经济学；第八章评估实证与证据层；第九章做方法论批判；第十章给出比较矩阵与"
              "置信度分级；第十一章提出未来研究；第十二章收束。")
    para(doc, "**本章主句**：精神分析进入金融交易，不是为了多列一张偏差清单，而是为了回答"
              "那个偏差清单始终绕开的问题——为什么明知故犯。", first_indent=False, italic=True)

    # ---------- 2 概念工具箱 ----------
    h(doc, "二、概念工具箱：把临床概念搬到市场之前", 1)
    para(doc, "把精神分析的术语直接套到交易上，是最常见也最容易翻车的做法。本章先把工具箱摊开，"
              "交代每个概念的原始含义与适用条件，再在后面的章节里逐一测试它能不能经得起市场的翻译。")

    h(doc, "2.1 无意识、压抑与防御", 2)
    para(doc, "精神分析的第一块基石是：心理过程中有一大部分不在意识之内，且并非因为被遗忘，"
              "而是因为被主动地压抑。令人不安的念头、愿望、羞耻，被挡在意识门槛之外，"
              "但仍以替代形式影响行为。防御机制由此而来——否认、投射、合理化、"
              "以及最贴合交易场景的**否认（disavowal）**：明知事实，却拒绝让这个知道产生后果。")
    para(doc, "放到交易里，最典型的就是“账面亏损还不算亏损”的心态。投资者并非不知道价格已经下跌，"
              "而是拒绝让这个认知改变持有决策。情绪金融把它描述为：理性上知道股票会涨会跌，"
              "在心理现实中方向却“只能向上”[15]。这正是压抑与否认在金融场景里的日常形态。")

    h(doc, "2.2 移情与重复强迫", 2)
    para(doc, "移情指人把过去重要关系中的情感模式，投射到当下的对象身上。它在金融里的对应物，"
              "是投资者与“资产”“基金经理”“市场”之间那种带着强烈情感的关系：相信、依赖、"
              "失望、背叛。情绪金融观察到，基金持有人之所以反复寻找“值得信任的”管理人，"
              "很大程度是在寻找一种可依赖的关系感，而不只是收益率[12]。")
    para(doc, "重复强迫指主体不自觉地重复痛苦的经历。弗洛伊德在《超越快乐原则》之后，"
              "用它解释那些明显违背“趋乐避苦”的行为。交易者一次次回到同一个亏损模式，"
              "从经典精神分析看，未必只是纪律问题，而可能是重复强迫在作祟——把亏损当作"
              "需要反复经历的东西，而非需要避免的东西[2][24]。")

    h(doc, "2.3 客体关系：偏执-分裂位与抑郁位", 2)
    para(doc, "克莱因提出，人在较早的心理组织中用“分裂”处理矛盾：把对象劈成全好与全坏两半，"
              "这就是偏执-分裂位；当人能承受对象同时是好的又是坏的、并容纳自己的破坏性时，"
              "进入抑郁位[8]。市场是一个极好的分裂放大器：牛市里资产是“全好”的，崩盘后同一资产"
              "变成“全坏”的；分析师对同一家公司可以给出截然相反却又同样斩钉截铁的评级。"
              "从偏执-分裂位到抑郁位的移动，也对应着投资者能否与一个“既会让我赚钱、也会让我亏钱”"
              "的资产长期共处。")

    h(doc, "2.4 群体心理学与基本假设", 2)
    para(doc, "勒庞在《乌合之众》里描述了个体进入群体后智力下降、情绪传染、易受暗示的状态[6]；"
              "弗洛伊德在《群体心理学与自我的分析》中把这一现象接进精神分析，指出群体中"
              "个体会把领袖当作自我理想的外置，从而放弃自己的批判能力[1]。比昂再往前一步，"
              "区分了“工作群体”与“基本假设群体”：后者由三种无意识假设驱动——依赖、"
              "战斗-逃跑、配对[7]。市场在极端行情中，几乎每隔一段就切换一次基本假设："
              "依赖“救市”、战斗-逃跑式的踩踏、以及对“下一个叙事”的配对式期待。")

    h(doc, "2.5 拉康：想象界、象征界、实在界与对象 a", 2)
    para(doc, "拉康的三界提供了一套更结构化的语言。想象界是镜像式的认同与完整感；"
              "象征界是语言与法则的秩序，主体由此进入社会；实在界是语言无法完全捕获、"
              "总以创伤或缺口形式返回的东西。欲望被拉康定义为“要求减去需要”的差额，"
              "因此永远无法被某个具体对象填满——欲望是转喻，得到一件就滑向下一件[44]。"
              "金融的“对象 a”（objet petit a）不是钱本身，而是那个被认为能填补缺口的、"
              "永远差一点的东西：下一个涨停、下一轮牛市、下一种必胜策略。"
              "拉康在《精神分析的四基本概念》中把这一主体结构系统化[9]。"
              "Vanheule 把这一结构整理为可分析的“资本主义话语”，"
              "并讨论它如何在主体层面再生产[53]。")

    h(doc, "2.6 本章小结：翻译的准入条件", 2)
    para(doc, "把概念搬到市场之前，必须满足三个条件：概念有明确的行为对应物；"
              "该对应物可被独立观测；观测结果能反驳基于该概念做出的预测。"
              "第二章给出的每个概念，后文都会按这三条检验。")
    para(doc, "**本章主句**：临床概念不是修辞，只有能被观测、能被反驳，它才有资格进入金融研究。",
         first_indent=False, italic=True)

    # ---------- 3 钱的精神分析学 ----------
    h(doc, "三、钱的精神分析学：从肛门欲到象征秩序", 1)
    para(doc, "在讨论交易之前，得先讨论钱。精神分析对金钱的兴趣早于它对市场的兴趣，"
              "而且这条线索一直延伸到最当代的资本批判。")

    h(doc, "3.1 弗洛伊德：金钱与性的同构羞耻", 2)
    para(doc, "弗洛伊德在《关于治疗的开端》里有一句被反复引用的话：文明人对待金钱，"
              "和对待性一样，带着同样的不一致、羞怯与虚伪[19]。这句话的分量不在于道德批评，"
              "而在于它指出金钱在心理上不是一个中性的交换工具，而是一个承载羞耻、"
              "欲望与压抑的象征物。他又在《性格与肛门性欲》中把金钱与肛门期的心理组织联系起来[3]，"
              "为后来亚伯拉罕与费伦齐的发展埋下伏笔。")

    h(doc, "3.2 亚伯拉罕与费伦齐：金钱=粪便的象征链", 2)
    para(doc, "亚伯拉罕在肛门性格理论中指出，坚持用支票支付哪怕是极小金额，"
              "是一种典型的肛门性保留[5]；费伦齐则给出了那条著名的象征链："
              "儿童对泥沙的兴趣，经过沙、石子、硬币、纽扣的置换，"
              "最终在成人身上表现为对金钱的占有欲，并把这种占有当作对肛门快感的"
              "社会化的反向形成[4]。这条链条在今天是很容易被嘲笑的——它看起来过度联想、"
              "缺乏实证。但它至少提出一个值得认真对待的直觉：**金钱的心理意义不等于它的经济功能**，"
              "囤积、挥霍、吝啬都不是收益最大化能解释的。")

    h(doc, "3.3 金钱作为防御与关系", 2)
    para(doc, "Dimen 把这条线索推到关系维度：金钱在分析情境里既是设置的一部分，"
              "也是移情与反移情的载体，爱与恨在金钱上无法调和，只能在悖论中暂时安放[19]。"
              "这一点对交易研究有直接价值——它提示我们，金钱行为往往是在处理某种关系张力，"
              "而不是在处理数字。一个人对亏损的暴怒，指向的可能不是市场，而是某个更早的对象。")

    h(doc, "3.4 从个体金钱幻想到资本主义动力", 2)
    para(doc, "Johnston 在《无限的贪婪》里回到马克思与拉康的交汇处，提出一个相当锋利的论断："
              "马克思在《资本论》里描述的 M—C—M′ 循环，本质上是精神分析意义上的“驱动”（drive）"
              "——它不追求终点，而是不断回到自身的重复运动；资本的“对剩余价值的无穷渴望”"
              "在结构上是无对象的驱动[20]。这意味着贪婪不是资本家的私人缺陷，"
              "而是资本关系本身强迫出来的心理形式。这一步把“个体金钱幻想”与"
              "“系统动力”接上了。更早的一条线索来自 Maurer，"
              "他把金融衍生品分析为一种“神学的无意识”：衍生工具在结构上"
              "处理的是对未来的信仰与压抑，而非单纯的风险转移[50]。"
              "Chicchi 用“物之幻影”讨论商品如何充当资本的主能指，"
              "把恋物式的幻象与资本批判连在一起[22]。")

    h(doc, "3.5 本章小结", 2)
    para(doc, "钱的精神分析学留下的可用遗产有三条：金钱承载的心理意义超出其经济功能；"
              "金钱行为常在处理关系而非数字；贪婪在结构上可以是系统的而非个人的。"
              "这三条将在后文被反复调用，也同样会被反复质疑。")
    para(doc, "**本章主句**：钱是符号，而符号从来不只兑现成购买力，它还兑现成羞耻、"
              "关系和重复。", first_indent=False, italic=True)

    # ---------- 4 群体心理学与泡沫 ----------
    h(doc, "四、从个体到市场：群体心理学与泡沫的情感轨迹", 1)

    h(doc, "4.1 勒庞与弗洛伊德的群体", 2)
    para(doc, "勒庞的群体是去人格化的、情绪化的、易受暗示的[6]。弗洛伊德接过来，"
              "指出群体的黏合靠的是把领袖置于自我理想的位置，成员之间由此产生横向认同[1]。"
              "这套描述与市场有惊人的贴合度：行情极端时，市场里的个体确实会放弃独立判断，"
              "跟着一个“故事”走——那个故事就是临时的领袖。")
    para(doc, "近期有研究把这一框架重新带回行为金融，主张在繁荣与崩盘阶段，"
              "市场表现为一个“勒庞式群体”，由无意识过程、暗示、情绪传染和冲动行动支配，"
              "而非个体偏差的简单加总[26]。这一提法的价值在于它明确反对“加总谬误”："
              "把市场当成许多独立个体的集合，会丢掉群体层面的涌现性质。"
              "更早的同类主张来自 Prechter，他把“无意识羊群行为”直接当作市场趋势与形态的"
              "心理基础，属于社会经济学（socionomics）取向[49]。"
              "叙事经济学则给出了更可操作的版本：驱动市场的常常是流行故事而非数据[28]；"
              "席勒更早就用“非理性繁荣”记录过同一现象，并指出情绪会自我强化成价格偏离[29]。")

    h(doc, "4.2 比昂：工作群体与基本假设群体", 2)
    para(doc, "比昂的贡献是给了群体一个可操作的动力学结构[7]。工作群体面对真实任务，"
              "基本假设群体则由无意识幻想驱动。市场大部分时间是工作群体——定价、"
              "套利、信息消化；而在泡沫与恐慌中，它整体切换成基本假设群体。"
              "有趣的是，这种切换并不需要成员彼此认识，市场恰恰是“虚拟群体”的极端样本："
              "无数陌生人通过价格这个媒介完成了情绪同步[12]。")

    h(doc, "4.3 泡沫与崩盘的情感轨迹", 2)
    para(doc, "Tuckett 与 Taffler 用“幻觉客体”解释了互联网泡沫的心理轨迹[11]。"
              "一个被寄予厚望的新事物（互联网、某只龙头、某种新技术）成为幻觉客体后，"
              "投资者与它的关系不再是评估，而是相信；支撑它的是一套“支持性故事”"
              "与“覆盖性观念”，使反面证据被有效屏蔽。当故事撑不住时，"
              "“恐惧作为被压抑者的返回”出现，市场从兴奋直接跌入恐慌[11]。"
              "整个过程可以被概括为从快乐原则主导退回现实原则的失败。")

    h(doc, "4.4 群体心理学进路与行为金融的对照", 2)
    para(doc, "行为金融用羊群效应、情绪传染解释同步行为，描述准确但机制偏浅[40]。"
              "群体心理学给出的是更进一步的机制：为什么个体会主动放弃判断、"
              "为什么“知道是泡沫”和“不参与泡沫”是两回事。代价是它的可测量性差，"
              "基本假设、自我理想外置这些都很难直接量化。这个“解释力换可测量性”的交换，"
              "是本章埋下的核心张力。")

    h(doc, "4.5 本章小结", 2)
    para(doc, "从个体到群体的这一步，是精神分析相对行为金融最有辨识度的贡献："
              "它把市场看成一个有自己的无意识生活的主体，而不是一群各自犯错的人。")
    para(doc, "**本章主句**：泡沫不是很多人的偏差相加，而是一群人共同进入了一种心理状态。",
         first_indent=False, italic=True)

    # ---------- 5 情绪金融 ----------
    h(doc, "五、情绪金融：一个试图独立的范式", 1)

    h(doc, "5.1 范式定位：站在两座山之间", 2)
    para(doc, "情绪金融是本文认为最值得认真对待的一条路线，因为它有明确的自我定位："
              "它既反对传统金融的理性人，也不满足于行为金融的“有偏差的人”。"
              "Taffler 的措辞很清楚——行为金融的前提仍是“只要投资者学会少一点偏差，"
              "就会更理性”；而情绪金融要处理的是无意识的幻想、需要与欲望，"
              "它们不以“可以被克服的偏差”形式存在[12]。")

    h(doc, "5.2 幻觉客体", 2)
    para(doc, "“幻觉客体”（phantastic object）是情绪金融的核心概念，"
              "由 Tuckett 与 Taffler 在 2003 年对互联网股票估值的研究中提出，"
              "并在 2008 年的论文中系统化[11][14]。它指那种被认为能即时、无限地"
              "满足主体欲望的心理对象。关键在于：幻觉客体不是被评估的对象，"
              "而是被爱的对象；因此它天然排斥中性信息。互联网股票、"
              "加密货币、某位明星创始人，都可以临时成为幻觉客体[51]。")

    h(doc, "5.3 分阶段与未分阶段投资", 2)
    para(doc, "这一对概念是情绪金融里最接近可操作指标的部分。“分阶段投资”意味着"
              "投资者能同时容纳“可能赚”和“可能亏”，处在一种能承受矛盾的抑郁位；"
              "“未分阶段投资”则把资产分裂成全好或全坏，对应于偏执-分裂位。"
              "Tuckett 与 Taffler 主张，市场整体的“现实感”会在两种状态间迁移，"
              "这正是泡沫形成与破裂的心理机制[11][13]。")

    h(doc, "5.4 应用：三个案例", 2)
    para(doc, "情绪金融至少在三个方向上做过应用。其一，互联网泡沫与 2008 年金融危机，"
              "用集体幻觉与防御解释市场“现实感”的崩塌[11]。其二，爱尔兰房地产泡沫，"
              "Ryan、Taffler 与 Branigan 把创伤的代际传递引入分析，"
              "指出对土地与房产的执念是一种试图超越殖民历史的心理补偿[16]。"
              "其三，基金行业的悖论：这个行业真正卖给投资者的，"
              "很大程度不是超额收益，而是一种被照料、被信任的关系感[12]。"
              "Eshraghi 与 Taffler 进一步把这一分析延伸到对冲基金，"
              "考察管理者与投资者之间的幻想关系及其幻灭[52]。")

    h(doc, "5.5 实证证据与可检验性", 2)
    para(doc, "情绪金融自己承认，这一领域的实证研究仍然稀缺，"
              "“需要对个体与市场行为的预测做更多实证检验”[15]。"
              "近年的尝试把情绪金融与投资绩效、市场知识、投资者保护放进同一模型检验[58]，"
              "也有研究把它作为理解市场的新路径加以引介[57]。"
              "已有的操作化尝试主要靠深度访谈与质性编码，"
              "例如 McDonnell 对 21 位活跃投资者访谈，提炼出幻觉客体、"
              "社会防御、基本假设、效价与脆弱性五个动力因素[23]。"
              "这类研究的价值在于把概念落地，弱点在于样本小、"
              "编码依赖研究者判断、难以重复。第 8、9 章会回到这个问题。")

    h(doc, "5.6 本章小结", 2)
    para(doc, "情绪金融是精神分析进入金融最成功的一次尝试，因为它既保留了无意识的核心，"
              "又主动接受“需要实证检验”这一约束。它下一步的成败，取决于能否把"
              "幻觉客体、分阶段投资变成可测量的变量。")
    para(doc, "**本章主句**：情绪金融的分量不在于它说了无意识，而在于它愿意让无意识接受检验。",
         first_indent=False, italic=True)

    # ---------- 6 交易者病理 ----------
    h(doc, "六、交易者病理：贪婪、成瘾与赌博的重合", 1)

    h(doc, "6.1 贪婪综合征", 2)
    para(doc, "Kets de Vries 把不受约束的贪婪类比为成瘾，与毒品、性、食物、赌博并列[18]。"
              "从精神动力学看，贪婪的源头常被追溯到养育缺陷："
              "当照料者用“东西”替代照料，孩子会形成一种“缺了什么”的感觉，"
              "成年后以不断获取来补偿这个缺口，而缺口永远不会被填满[18]。"
              "这套解释与拉康的欲望转喻在结构上高度一致——欲望对象永远滑走的机制，"
              "在这里被写成了发展心理学的语言。")

    h(doc, "6.2 赌博的精神分析：从弗洛伊德论陀思妥耶夫斯基说起", 2)
    para(doc, "1928 年，弗洛伊德发表《陀思妥耶夫斯基与弑父》，"
              "提出赌徒存在无意识的自罚需求：赌博是赎罪的形式，"
              "输钱才是潜意识里真正想要的结局[2]。这一解释后来被多篇研究重述与讨论，"
              "包括对《赌徒》主人公三阶段（赢、输、绝望）的精神分析解读[25]，"
              "以及从社会学角度对弗洛伊德解释的再审视——Kingma 指出，"
              "陀思妥耶夫斯基自己把赌博看作对困窘处境的理性回应，"
              "而弗洛伊德把它读成“病理性激情”，两种解读其实各自预设了"
              "对“为赌而赌”的立场[24]。")
    para(doc, "需要诚实指出的是：弗洛伊德这套“自罚”解释在当代临床里已经边缘化，"
              "现代赌博研究更多走的是冲动控制、奖赏回路与共病的路径。"
              "它的价值可能不在结论，而在提出了一个行为主义难以提的问题："
              "为什么有人反复求输。")

    h(doc, "6.3 交易成瘾：临床证据与诊断谱系", 2)
    para(doc, "这一块是精神分析话题里实证最扎实的部分。大量研究表明，"
              "过度交易与赌博障碍在诊断标准、共病、轨迹上高度重合[36][37]。"
              "荷兰的两项投资者调查发现，4.4% 的投资者符合金融市场强迫性赌博标准，"
              "另有 3.6% 属于“问题赌博”；这些投资者表现出无法停止、"
              "持续追求、失控、明知有害仍继续，并伴随抑郁与自杀意念[36]。"
              "巴西期货市场的数据显示，坚持交易超过 300 个交易日的投资者中"
              "97% 亏损[36]。临床描述还记录了一个共同的动力学特征："
              "早期的小额盈利，随后的追损，最终失控[36]。")
    para(doc, "神经机制层面，对交易的解释集中在可变比率强化、"
              "预期性多巴胺与近失效应：真正让人上瘾的不是盈利，"
              "而是“不确定的期待”[37]。这与精神分析对赌博的“兴奋/焦虑”"
              "二元结构描述可以互相印证，但两边用的证据类型完全不同——"
              "一边是量表与流行病学，一边是临床叙事。")

    h(doc, "6.4 控制错觉与幻想的技能感", 2)
    para(doc, "精神分析把赌博中的“能力幻觉”定义为一种对抗无助感的防御："
              "用“我能控制”来抵御“我无法预知”的焦虑[15]。"
              "行为金融把这叫控制错觉与技能幻觉，"
              "并发现技术分析给了投机一种“看起来像技能”的外观[36]。"
              "两条路径在这里罕见地收敛：都承认这是对抗不确定性的心理装置，"
              "分歧只在“装置”是无意识的防御，还是可被纠正的认知错误。")

    h(doc, "6.5 本章小结", 2)
    para(doc, "交易成瘾是这个交叉领域里最有现实意义的落点："
              "它既有临床诊断的硬证据，也有精神分析对动力机制的细腻描述。"
              "把两边接起来，才可能既解释“为什么”，又回答“怎么办”。")
    para(doc, "**本章主句**：赌徒求的不是赢，是那个还没揭晓的瞬间——而市场每天都在批量生产这个瞬间。",
         first_indent=False, italic=True)

    # ---------- 7 拉康视角 ----------
    h(doc, "七、拉康视角：欲望、幻想与市场的“大他者”", 1)

    h(doc, "7.1 欲望作为转喻", 2)
    para(doc, "拉康把欲望定义为“要求减去需要”，因此欲望注定无法被具体对象满足[44]。"
              "在金融里，这个结构有近乎教科书式的对应："
              "赚到一笔之后，欲望并不会平息，而是沿着能指链滑向下一笔。"
              "孔明安在评论 Žižek 的金融资本主义分析时，"
              "把这一逻辑概括为“欲望主体”的悖论——主体集匮乏与欲望、"
              "贪婪与恐惧于一身，投机冲动正来自这种结构[44]。")

    h(doc, "7.2 意识形态幻想与腐败交易", 2)
    para(doc, "Pignot 用拉康的“意识形态幻想”分析了高盛 Abacus 交易中的邮件往来，"
              "提出交易员的腐败行为并非单纯的道德败坏，"
              "而是一种“自逾越的享乐”（self-transgressive jouissance）——"
              "既带来快感又自我破坏，用以维系公司那些不可能的理想规范[17]。"
              "这是把拉康概念落到具体交易证据上的少数尝试之一，"
              "其材料来自真实的内部邮件，比其他纯理论推演更有说服力。")

    h(doc, "7.3 剩余享乐与资本主义话语", 2)
    para(doc, "Žižek 的贡献在于把拉康的“剩余享乐”接进马克思的政治经济学，"
              "主张当代资本主义已经从生产主导转向金融投机主导，"
              "其运作方式近似于“对象 a”的机制[10][44][45]。"
              "陈剑对“资本主义恋物癖”的梳理进一步指出："
              "人们明知金钱、地位只是社会关系的折射，行为上却仍将其当神来膜拜，"
              "这种“知而不信、信而不言”的自动化，正是商品恋物癖的当代形态[45]。"
              "在更宏观的层面，Maher 用“自由市场作为幻想”解释新自由主义为何具有惊人韧性[54]。")

    h(doc, "7.4 恋物癖：从商品到货币到比特币", 2)
    para(doc, "Bjerg 用 Žižek 的“实在界/象征界/想象界”三元组分析了比特币的本体构成，"
              "给出一个漂亮的判词：比特币是“没有黄金的商品货币、没有国家的法币、"
              "没有债务的信用货币”[21]。这项研究的意义在于示范了"
              "三界框架如何被用来分析具体货币现象，而不只是做概念游戏。")

    h(doc, "7.5 这条路径的定位与风险", 2)
    para(doc, "拉康取向的好处是能处理“结构与意识形态”层面的问题，"
              "这是行为金融完全够不着的层次。风险同样明显："
              "它极易滑向对一切现象的万能解释，"
              "从而丧失证伪的可能——而这正是波普尔当年对精神分析的核心指控[41]。"
              "把拉康讲成“什么都能解释”，恰好是让它变得什么都不能反驳。")

    h(doc, "7.6 本章小结", 2)
    para(doc, "拉康取向把精神分析从诊室推到了政治经济学，"
              "它最有价值的产出，是把“贪婪与恐惧”从情绪词升级为结构位置。")
    para(doc, "**本章主句**：市场不缺故事，缺的是弄明白为什么明知是故事，还要往里投钱。",
         first_indent=False, italic=True)

    # ---------- 8 实证与证据层 ----------
    h(doc, "八、实证与证据层：精神分析的主张如何被检验", 1)

    h(doc, "8.1 质性证据：访谈与临床", 2)
    para(doc, "情绪金融的实证主要靠深度访谈。McDonnell 的 21 人访谈是较完整的样本，"
              "它把“幻觉客体、社会防御、基本假设、效价、脆弱性”编码为动力因素，"
              "并从精神动力学角度解释前景理论中风险偏好翻转的成因[23]。"
              "这类研究的长处是能捕捉意义结构，短处是样本小、"
              "无法独立重复、结论受访谈者与编码者影响。")

    h(doc, "8.2 神经金融与躯体标记", 2)
    para(doc, "达马西奥的躯体标记假说主张，身体状态信号（如皮肤电反应）"
              "会为决策“打标”，情绪因此不是理性的对立面，"
              "而是复杂不确定情境下决策的必要环节[33]。"
              "这条思路被用于交易研究：一项实验测量了 30 名被试在交易博弈中的"
              "预期性情绪（皮肤电），发现其与交易表现显著相关，"
              "但相关方向取决于标的价格的走势——情绪既非全好也非全坏，"
              "而是情境依赖的[35]。")
    para(doc, "需要注意的是，躯体标记假说本身受到严厉批评："
              "Dunn 等人指出，其证据主要来自爱荷华赌博任务，"
              "而该任务存在奖励结构可被认知穿透、心理生理数据解释含混、"
              "缺乏外周反馈与任务表现之间因果证据等问题[34]。"
              "换言之，即便神经金融这一层，也不是铁板一块。"
              "中文语境的普及性读物则把“大脑把股市当作原始森林”式的神经金融解释"
              "讲给了普通投资者[46]。")

    h(doc, "8.3 情绪的可测量化", 2)
    para(doc, "行为与资产定价文献尝试把情绪变成因子："
              "有研究用情绪的异质波动率（EMO）度量行为唤醒风险，"
              "发现其与横截面收益相关，并认为其来源是噪音交易而非知情交易[38]；"
              "也有研究把行为异质性引入情绪指标，"
              "发现情绪与收益的肥尾、波动聚集等异象相关，"
              "并能在模型中复现不同类型危机[39]。这些工作与精神分析没有直接血缘，"
              "但它们的度量思路，恰恰是情绪金融若想被检验所必须借用的工具。"
              "需要一提的是，Forbes 直接讨论了无意识思维如何既推动又阻碍良好的财务决策[55]，"
              "而 Dow 把凯恩斯、明斯基与情绪金融放进同一个比较框架[56]。")

    h(doc, "8.4 交易成瘾的流行病学", 2)
    para(doc, "这是全领域证据最硬的一块：诊断标准可移植[36][37]、"
              "患病率可统计、共病与后果可追踪。它给精神分析式解释提供了"
              "一个可落地的“地面”：如果心理动力机制确实存在，"
              "它应当在这些可观测的临床人群里留下痕迹。")

    h(doc, "8.5 证据的分级与置信度", 2)
    para(doc, "把上述证据按强度排序，大致是：交易成瘾与赌博重合（实证强）、"
              "情绪影响决策且情境依赖（实验中等、可重复）、"
              "躯体标记的具体机制（争议中）、"
              "群体层面“市场作为心理群体”（理论强、实证弱）、"
              "幻觉客体与分阶段投资（理论丰富、操作化不足）、"
              "拉康式结构解释（思辨性最强、几乎不可证伪）。逐条评级见附录 C。")

    h(doc, "8.6 本章小结", 2)
    para(doc, "精神分析的实证困境可以归结为一句话：越接近无意识核心的主张，"
              "越难找到干净的可观测对应物；越好测量的部分，"
              "越接近行为金融已有的结论。")
    para(doc, "**本章主句**：一条解释要想有分量，必须承受被反证的代价。", first_indent=False, italic=True)

    # ---------- 9 方法论批判 ----------
    h(doc, "九、方法论批判：科学地位与边界", 1)

    h(doc, "9.1 波普尔的质疑", 2)
    para(doc, "波普尔把可证伪性当作科学与非科学的分界，"
              "并明确把精神分析（与马克思主义历史观）列为"
              "“与一切可能观察相容、因而不可证伪”的典型[41]。"
              "这个批评对本文的主题极其关键：如果精神分析的解释"
              "永远能与任何结果自洽，那它对金融研究的贡献就只能停留在事后叙事。")

    h(doc, "9.2 格林鲍姆的补刀", 2)
    para(doc, "格林鲍姆比波普尔更不留情，但他也不认为波普尔说对了。"
              "他指出弗洛伊德其实做出过可检验的预测，问题不在可证伪性，"
              "而在证据价值：临床素材很可能是分析师自我实现预期的产物，"
              "自由联想并未真正支持无意识动机理论；"
              "他主张，若要检验精神分析的核心主张，"
              "必须依靠设计良好的“临床之外”的研究[42][43]。"
              "这一判断为本文指了方向：精神分析要在金融里站住脚，"
              "靠的不是更多案例，而是更多独立、可重复的实证。")

    h(doc, "9.3 情绪金融能不能被证伪", 2)
    para(doc, "把情绪金融的核心主张翻译成可反驳的命题，是可行的。例如："
              "如果“幻觉客体”真实存在，那么在资产成为幻觉客体期间，"
              "负面信息的定价速度应当显著慢于中性时期，且这种差异在对象"
              "被“去幻觉化”后消失。如果“分阶段投资”是一个真实状态，"
              "那么它应当与可测量的心理指标（如矛盾情感容忍度、"
              "持仓集中度的时间序列）相关。这些命题至少在原则上是可检验的。")

    h(doc, "9.4 与行为金融的分工", 2)
    para(doc, "一个务实的判断是：精神分析与行为金融不是替代关系，"
              "而是分工关系。行为金融擅长刻画偏差的形态与统计规律，"
              "精神分析擅长解释偏差的动力学来源与重复性。"
              "把前者当作预测引擎，把后者当作机制假说库，"
              "比强行让精神分析去做它不擅长的预测更诚实。")

    h(doc, "9.5 过度解读的风险清单", 2)
    bullet(doc, "把一切亏损都解释为“无意识求输”，会取消对纪律、成本、技能的严肃讨论。")
    bullet(doc, "把市场说成“一个大主体”，可能掩盖异质性——不同交易者的心理结构并不相同。")
    bullet(doc, "用拉康术语解释一切，等于什么都没解释；万能解释是理论退化的标志。")
    bullet(doc, "将临床概念未经改造地移植到市场，容易产生“看起来深刻、其实不可操作”的结论。")
    bullet(doc, "忽略反方证据（如躯体标记的批评、弗洛伊德自罚解释的边缘化），会高估证据强度。")

    h(doc, "9.6 本章小结", 2)
    para(doc, "方法论的诚实，是这个领域能否被主流金融接纳的前提。"
              "承认哪些主张不可证伪，比假装它们都能证伪，更能保住可信度。")
    para(doc, "**本章主句**：精神分析要进入金融，先得放下“什么都能解释”的诱惑。",
         first_indent=False, italic=True)

    # ---------- 10 综合 ----------
    h(doc, "十、综合：五条路线对照与置信度", 1)

    h(doc, "10.1 五条研究路线对照", 2)
    para(doc, "本文梳理的五条路线，可以按“核心问题—解释层次—证据类型—主要弱点”"
              "四个维度对照，见附录 B。简要地说："
              "钱的精神分析学提供象征与关系视角，但离交易现场较远；"
              "群体心理学解释同步与泡沫，但可测量性差；"
              "情绪金融最成体系，处在可检验化的临界点；"
              "交易者病理证据最硬，但更接近临床精神病学而非金融；"
              "拉康取向理论最深，可证伪性最弱。")

    h(doc, "10.2 术语到市场现象的映射", 2)
    para(doc, "把概念落到现象，是检验翻译条件是否满足的关键一步，见附录 D。"
              "映射表的价值不在好看，而在于它暴露了哪些概念其实找不到干净的行为对应物——"
              "这些恰恰是最需要未来研究填补的地方。")

    h(doc, "10.3 一个整体判断", 2)
    para(doc, "综合全部证据，本文的判断是克制的："
              "**精神分析在金融交易研究中的地位，是机制假说的供给方，而不是预测模型的竞争者。**"
              "它在三个问题上提供了别处找不到的深度——明知故犯、"
              "亏损的重复、群体的同步狂热；它在三个问题上明显弱于行为金融"
              "——参数估计、可重复的实证、跨样本泛化。"
              "把它放在正确的位置上，它能反过来为行为金融提供更好的问题意识；"
              "放错位置，它就会退化成一套事后圆故事的话术。")
    para(doc, "**本章主句**：精神分析解释得越深，越需要承认它预测得越浅。", first_indent=False, italic=True)

    # ---------- 11 未来 ----------
    h(doc, "十一、未来研究方向", 1)

    h(doc, "11.1 可复现实验设计建议", 2)
    para(doc, "若要推进这一领域，至少可以做四件事。"
              "第一，为“幻觉客体”定义可操作的识别规则，"
              "例如用信息不对称定价速度、叙事密度、"
              "社交讨论量的联合指标来标记对象进入“幻觉态”的时间窗。"
              "第二，把“分阶段/未分阶段投资”与已有的心理学量表"
              "及持仓行为的时间序列对接，做预注册的假设检验。"
              "第三，在交易成瘾研究里加入精神动力学访谈，"
              "把“硬诊断”与“动力机制”放在同一批被试上验证。"
              "第四，对拉康式命题做“可反驳化”改造，"
              "明确给出在什么观察下该命题被推翻。")

    h(doc, "11.2 数据与方法的整合", 2)
    para(doc, "技术上，可以把情绪因子（EMO、情绪指标[38][39]）、"
              "文本与叙事指标、以及个体层面的心理生理数据整合进同一研究，"
              "用精神分析提供假设、用计量方法提供检验，"
              "避免两边各说各话。")

    h(doc, "11.3 伦理与监管含义", 2)
    para(doc, "交易成瘾的证据已经足以支持监管层面的动作："
              "既然过度交易与赌博障碍共享机制，"
              "那么券商的产品设计（高频推送、简易杠杆、游戏化界面）"
              "就应当被纳入消费者保护视野，"
              "而不是仅当作“用户偏好”[36][37]。")

    h(doc, "11.4 本章小结", 2)
    para(doc, "这一领域的下一步，不是产出更漂亮的理论，"
              "而是把已有理论拆成可以被证伪的碎片，逐块实证。")
    para(doc, "**本章主句**：让概念变得可测量，是这个领域唯一真正的前进方向。",
         first_indent=False, italic=True)

    # ---------- 12 结论 ----------
    h(doc, "十二、结论", 1)
    para(doc, "精神分析进入金融交易研究，带来的不是一套新的预测公式，"
              "而是一批更难被绕开的问题。它逼着研究者和实践者承认："
              "交易者不是一台会学习的计算器，市场也不总是一群独立个体的加总；"
              "在“知道”与“做到”之间，横着一整套无意识的欲望、防御与重复。")
    para(doc, "这条路径的成败，不取决于它的术语多精致，"
              "而取决于它能否把自己交给检验。情绪金融已经迈出这一步，"
              "交易成瘾研究已经提供了硬证据，拉康取向则仍停在思辨的门槛内。"
              "本文的总体立场是：把精神分析当作机制假说的来源，"
              "把行为金融与神经金融当作检验工具，"
              "让前者的问题意识与后者的方法纪律相互制衡。")
    para(doc, "**主句**：一万份偏差清单也回答不了“为什么明知故犯”，"
              "而这正是精神分析值得被认真对待的理由。", first_indent=False, italic=True)

    # ---------- 附录 A 证据表 ----------
    doc.add_page_break()
    h(doc, "附录 A　证据表（核心条目）", 1)
    para(doc, "下表列出本文依赖的核心条目，标注证据类型与核验状态。"
              "“已核验”指题名、作者、年份与 DOI/来源页可互相对应；"
              "“部分核验”指元数据可见但缺少全文或缺 DOI。", first_indent=False, size=9.5)
    ev = [
        ["Tuckett & Taffler (2008)", "幻觉客体与市场现实感", "理论+案例", "IJP 89(2):389-412", "DOI 10.1111/j.1745-8315.2008.00040.x", "已核验"],
        ["Taffler (2017/2018)", "情绪金融：投资与无意识", "理论综述", "European Journal of Finance", "DOI 10.1080/1351847X.2017.1369445", "已核验"],
        ["Tuckett (2011)", "《读懂市场》专著", "专著", "Palgrave Macmillan", "见 Warwick 政策简报引用[15]", "已核验"],
        ["Ryan, Taffler & Branigan (2023)", "爱尔兰房地产泡沫的精神分析", "案例研究", "IJAPS 20(4):666-681", "DOI 10.1002/aps.1804", "已核验"],
        ["Pignot (2015)", "用拉康分析高盛腐败交易", "质性+邮件证据", "ephemera 15(2)", "期刊页可查", "部分核验"],
        ["McDonnell (2021)", "前景理论的动力驱动因素", "21 人访谈", "INSEAD EMC 论文", "公开 PDF", "已核验"],
        ["Kets de Vries (2016)", "贪婪综合征", "工作论文+案例", "INSEAD WP 2016/26/EFE", "SSRN 2766233", "已核验"],
        ["Kingma (2017)", "陀思妥耶夫斯基与弗洛伊德：赌博成瘾", "历史社会学", "J. Historical Sociology 30(4)", "DOI 10.1111/johs.12086", "已核验"],
        ["Dias 等 (2008)", "《赌徒》中的病理性赌博", "临床文本分析", "Rev Psiquiatr RS 30(3)", "期刊页可查", "已核验"],
        ["Roza 等 (2024)", "问题交易：日交易与加密投资", "社论+综述", "Trends Psychiatry Psychother 46", "DOI 10.47626/2237-6089-2023-0623", "已核验"],
        ["Leong Wei Lyn 等 (2025)", "股票/加密交易与问题赌博", "叙述性综述", "Front. Psychol. 16:1585094", "DOI 10.3389/fpsyg.2025.1585094", "已核验"],
        ["Hinvest 等 (2021)", "预期性情绪与投资决策", "实验（30 人，皮肤电）", "Front. Psychol. 12:705476", "DOI 10.3389/fpsyg.2021.705476", "已核验"],
        ["Dunn, Dalgleish & Lawrence (2006)", "躯体标记假说的批判评估", "方法学综述", "Neurosci. Biobehav. Rev. 30", "期刊页可查", "已核验"],
        ["Kahneman & Tversky (1979)", "前景理论", "实验+理论", "Econometrica 47(2)", "经典文献", "已核验"],
        ["Barraud (2025)", "市场作为勒庞式群体", "理论框架", "arXiv:2510.23175", "预印本", "已核验"],
        ["Bjerg (2016)", "比特币是货币吗", "理论分析", "Theory, Culture & Society 33(1)", "DOI 10.1177/0263276415619015", "已核验"],
        ["Grünbaum (1984/1986)", "精神分析基础：哲学批判", "哲学批判", "Univ. of California Press", "BBS 1986 摘要", "已核验"],
        ["孔明安 (2019)", "贪婪与恐惧：金融危机新阐释", "中文理论", "国外理论动态 2019(6)", "中国社会科学网转载", "已核验"],
        ["陈剑 (2017)", "齐泽克笔下的资本主义恋物癖", "中文理论", "马克思主义研究网", "网页可查", "部分核验"],
        ["区祥江 (2008)", "《你有用脑投资吗？》", "中文普及著作", "香港出版", "媒体报道转述", "部分核验"],
    ]
    table(doc, ["条目", "主题", "证据类型", "来源", "标识", "核验状态"], ev,
          widths=[3.4, 3.2, 2.6, 3.4, 3.6, 1.8])

    # ---------- 附录 B 比较矩阵 ----------
    h(doc, "附录 B　五条路线统一比较矩阵", 1)
    cmp_rows = [
        ["一、钱的精神分析学", "金钱的心理意义", "个体—象征", "经典文本", "缺少金融现场证据", "低"],
        ["二、群体心理学与泡沫", "同步狂热与恐慌", "群体—涌现", "理论+案例", "可测量性差", "中"],
        ["三、情绪金融", "无意识幻想驱动投资", "个体—群体", "访谈+案例+理论", "操作化不足、样本小", "中高"],
        ["四、交易者病理", "贪婪与赌博成瘾", "个体—临床", "流行病学+量表", "更近精神病学，金融机制弱", "高"],
        ["五、拉康式政治经济学", "欲望结构与资本动力", "结构—系统", "理论+文本/邮件", "几乎不可证伪", "低"],
    ]
    table(doc, ["路线", "核心问题", "解释层次", "证据类型", "主要弱点", "证据强度"], cmp_rows,
          widths=[3.2, 3.0, 2.6, 3.0, 4.2, 1.6])

    # ---------- 附录 C 置信度分级 ----------
    h(doc, "附录 C　结论置信度分级", 1)
    conf_rows = [
        ["过度交易与赌博障碍在诊断与轨迹上重合", "高", "多项研究、跨样本、诊断标准可移植[36][37]"],
        ["情绪影响决策，且方向依情境而变", "中高", "实验可重复，但效应大小与机制有争议[35][34]"],
        ["交易中存在对抗不确定性的控制错觉", "中", "跨学科一致，但测量口径不一[15][36]"],
        ["市场中极端行情呈现群体动力学", "中", "理论强、案例多，但因果与边界难界定[26][11]"],
        ["幻觉客体与分阶段/未分阶段投资", "中", "概念有解释力，操作化与独立重复不足[11][23]"],
        ["金钱的心理意义超出其经济功能", "中", "经典文本与临床观察支持，难做干净实证[3][4][5][19]"],
        ["赌徒存在无意识自罚需求", "低", "经典解释，当代临床已边缘化[2][24]"],
        ["市场作为“对象 a”的运作机制", "低", "思辨性强，缺乏可反驳命题[44][20]"],
    ]
    table(doc, ["结论", "置信度", "依据"], conf_rows, widths=[6.0, 1.8, 9.6])

    # ---------- 附录 D 术语映射 ----------
    h(doc, "附录 D　术语到市场现象的映射", 1)
    map_rows = [
        ["压抑 / 否认", "弗洛伊德", "浮亏不认亏，拒绝让认知改变决策[15]"],
        ["重复强迫", "弗洛伊德", "反复回到同一亏损模式[2][24]"],
        ["偏执-分裂位 / 抑郁位", "克莱因", "资产在“全好/全坏”间摆动；能否承受双面性[8][11]"],
        ["基本假设（依赖/战斗-逃跑/配对）", "比昂", "依赖救市、踩踏、对“下一个叙事”的期待[7]"],
        ["幻觉客体", "Tuckett & Taffler", "互联网股、加密货币等被爱的对象[11][14]"],
        ["分阶段 / 未分阶段投资", "情绪金融", "能容纳盈亏 vs. 分裂处理[11][13]"],
        ["对象 a / 欲望转喻", "拉康", "永远差一点的下一个机会[44]"],
        ["剩余享乐 / 自逾越享乐", "拉康 / Žižek", "腐败交易的快感与自我破坏[17][45]"],
        ["意识形态幻想", "Žižek", "明知不实却仍照做的自动化[45]"],
        ["金钱=粪便象征链", "费伦齐", "囤积、挥霍、吝啬的非经济解释[4]"],
    ]
    table(doc, ["概念", "来源", "对应市场现象"], map_rows, widths=[3.8, 3.2, 10.4])

    # ---------- 附录 E 参考文献 ----------
    doc.add_page_break()
    h(doc, "附录 E　参考文献", 1)
    refs = [
        "[1] 弗洛伊德. 群体心理学与自我的分析[M]. 1921.",
        "[2] 弗洛伊德. 陀思妥耶夫斯基与弑父[M]. 1928.",
        "[3] 弗洛伊德. 性格与肛门性欲[M]. 1908.",
        "[4] 费伦齐. 金钱兴趣的本体发生[M]. 1914.",
        "[5] 亚伯拉罕. 对肛门性格理论的贡献[M]. 1921.",
        "[6] 勒庞. 乌合之众：大众心理研究[M]. 1895.",
        "[7] BION W R. Group dynamics: a re-view[J]. International Journal of Psycho-Analysis, 1952, 33: 235-247.",
        "[8] KLEIN M. Notes on some schizoid mechanisms[J]. International Journal of Psycho-Analysis, 1946, 27: 99-110.",
        "[9] 拉康. 精神分析的四基本概念[M]. 1973/1978.",
        "[10] 齐泽克. 意识形态的崇高客体[M]. 1989.",
        "[11] TUCKETT D, TAFFLER R J. Phantastic objects and the financial market's sense of reality: a psychoanalytic contribution to the understanding of stock market instability[J]. The International Journal of Psychoanalysis, 2008, 89(2): 389-412. DOI:10.1111/j.1745-8315.2008.00040.x.",
        "[12] TAFFLER R J. Emotional finance: investment and the unconscious[J]. The European Journal of Finance, 2018, 24(7-8): 630-649. DOI:10.1080/1351847X.2017.1369445.",
        "[13] TUCKETT D. Minding the Markets: An Emotional Finance View of Financial Instability[M]. London: Palgrave Macmillan, 2011.",
        "[14] TAFFLER R J, TUCKETT D. A psychoanalytical interpretation of dot.com stock valuations[R]. SSRN Working Paper 676635, 2003.",
        "[15] TAFFLER R J. Emotional finance: theory and application[R]. EFMA Annual Meeting Paper, 2014. 及 Warwick Social Sciences Policy Briefing 2/2018.",
        "[16] RYAN P, TAFFLER R J, BRANIGAN C. Some psychoanalytic reflections on the Irish real estate bubble[J]. International Journal of Applied Psychoanalytic Studies, 2023, 20(4): 666-681. DOI:10.1002/aps.1804.",
        "[17] PIGNOT E. Bringing down the house (of Goldman Sachs): analyzing corrupt forms of trading with Lacan[J]. Ephemera: Theory & Politics in Organization, 2015, 15(2).",
        "[18] KETS DE VRIES M F R. The greed syndrome[R]. INSEAD Working Paper 2016/26/EFE, 2016. SSRN:2766233.",
        "[19] DIMEN M. Money, love and hate: contradiction and paradox in psychoanalysis[J]. Psychoanalytic Dialogues, 1994, 4(1): 69-100.",
        "[20] JOHNSTON A. Infinite Greed: The Inhuman Selfishness of Capital[M]. New York: Columbia University Press, 2024.",
        "[21] BJERG O. How is Bitcoin money?[J]. Theory, Culture & Society, 2016, 33(1): 53-72. DOI:10.1177/0263276415619015.",
        "[22] CHICCHI F. Phantasmagoria of the Thing: aporias of the new capitalist discourse[J]. Postmodern Culture, 2016, 9(3). DOI:10.3998/pc.12322227.0009.003.",
        "[23] MCDONNELL C. Psychodynamic drivers of prospect theory amongst individual investors trading securities in financial markets[D]. INSEAD Executive Masters in Change Thesis, 2021.",
        "[24] KINGMA S F. Dostoevsky and Freud: autonomy and addiction in gambling[J]. Journal of Historical Sociology, 2017, 30(4): 891-917. DOI:10.1111/johs.12086.",
        "[25] DIAS F M V, CANO-PRAIS H A, KEHDY S, et al. Um jogador patológico por Dostoiévski[J]. Revista de Psiquiatria do Rio Grande do Sul, 2008, 30(3): 236-240.",
        "[26] BARRAUD C. Financial markets as a Le Bonian crowd during boom-and-bust episodes: a complementary theoretical framework in behavioural finance[R]. arXiv:2510.23175, 2025.",
        "[27] KAHNEMAN D, TVERSKY A. Prospect theory: an analysis of decision under risk[J]. Econometrica, 1979, 47(2): 263-291.",
        "[28] SHILLER R J. Narrative Economics: How Stories Go Viral and Drive Major Economic Events[M]. Princeton: Princeton University Press, 2019.",
        "[29] SHILLER R J. Irrational Exuberance[M]. Princeton: Princeton University Press, 2000.",
        "[30] KEYNES J M. The General Theory of Employment, Interest and Money[M]. London: Macmillan, 1936.",
        "[31] FAMA E F. Efficient capital markets: a review of theory and empirical work[J]. Journal of Finance, 1970, 25(2): 383-417.",
        "[32] LO A W. Adaptive Markets: Financial Evolution at the Speed of Thought[M]. Princeton: Princeton University Press, 2017.",
        "[33] DAMASIO A R. Descartes' Error: Emotion, Reason, and the Human Brain[M]. New York: Putnam, 1994.",
        "[34] DUNN B D, DALGLEISH T, LAWRENCE A D. The somatic marker hypothesis: a critical evaluation[J]. Neuroscience & Biobehavioral Reviews, 2006, 30(2): 239-271.",
        "[35] HINVEST N S, ALSHARMAN M, ROELL M, et al. Do emotions benefit investment decisions? Anticipatory emotion and investment decisions in non-professional investors[J]. Frontiers in Psychology, 2021, 12: 705476. DOI:10.3389/fpsyg.2021.705476.",
        "[36] ROZA T H, TAVARES H, KESSLER F H P, et al. Problematic trading: gambling-like behavior in day trading and cryptocurrency investing[J]. Trends in Psychiatry and Psychotherapy, 2024, 46: e20230623. DOI:10.47626/2237-6089-2023-0623.",
        "[37] LEONG WEI LYN N, YEO H Y, STARTUP C C, et al. Stock and cryptocurrency trading and problem gambling behavior during early phases of the COVID-19 pandemic: a narrative literature review[J]. Frontiers in Psychology, 2025, 16: 1585094. DOI:10.3389/fpsyg.2025.1585094.",
        "[38] SHEN J, WANG Y, GAO W. The variability of emotions: behavioral risk or mispricing[R]. EFMA Annual Meeting Paper, 2023.",
        "[39] LI C, TAN S R, HO N, et al. Behavioral heterogeneity and financial crisis: the role of sentiment[J]. Physica A: Statistical Mechanics and its Applications, 2022, 603: 127767. DOI:10.1016/j.physa.2022.127767.",
        "[40] WU Q. Cognitive and emotional dynamics in investment: a review of behavioral finance theories and modern applications[C]. Atlantis Press, 2025.",
        "[41] 波普尔. 科学发现的逻辑[M]. 1959. 另见 Stanford Encyclopedia of Philosophy, Karl Popper, 条目 3.",
        "[42] GRÜNBAUM A. The Foundations of Psychoanalysis: A Philosophical Critique[M]. Berkeley: University of California Press, 1984.",
        "[43] GRÜNBAUM A. Précis of The Foundations of Psychoanalysis: a philosophical critique[J]. Behavioral and Brain Sciences, 1986, 9(2): 217-228.",
        "[44] 孔明安. 贪婪与恐惧：当代资本主义金融危机的新阐释[J]. 国外理论动态, 2019(6).",
        "[45] 陈剑. 齐泽克笔下的资本主义恋物癖[J/OL]. 马克思主义研究网, 2017.",
        "[46] 区祥江. 你有用脑投资吗？[M]. 香港: 出版者不详, 2008.",
        "[47] DANIEL K, HIRSHLEIFER D, SUBRAHMANYAM A. Investor psychology and security market under- and overreactions[J]. The Journal of Finance, 1998, 53(6): 1839-1885. DOI:10.1111/0022-1082.00077.",
        "[48] HIRSHLEIFER D. Investor psychology and asset pricing[J]. The Journal of Finance, 2001, 56(4): 1533-1597. DOI:10.1111/0022-1082.2001.00361.",
        "[49] PRECHTER R R. Unconscious herding behavior as the psychological basis of financial market trends and patterns[J]. Journal of Behavioral Finance, 2001, 2(3): 120-125. DOI:10.1207/s15327760jpfm0203_1.",
        "[50] MAURER B. Repressed futures: financial derivatives' theological unconscious[J]. Economy and Society, 2002, 31(1): 15-36. DOI:10.1080/03085140120109231.",
        "[51] TAFFLER R, TUCKETT D. Emotional finance: the role of the unconscious in financial decisions[M]//Behavioral Finance: Investors, Corporations, and Markets. Hoboken: Wiley, 2010: 95-112. DOI:10.1002/9781118258415.ch6.",
        "[52] ESHRAGHI A, TAFFLER R. Hedge funds and unconscious fantasy[J]. Accounting, Auditing & Accountability Journal, 2012, 25(8): 1244-1265. DOI:10.1108/09513571211275461.",
        "[53] VANHEULE S. Capitalist discourse, subjectivity and Lacanian psychoanalysis[J]. Frontiers in Psychology, 2016, 7: 1948. DOI:10.3389/fpsyg.2016.01948.",
        "[54] MAHER H. The free market as fantasy: a Lacanian approach to the problem of neoliberal resilience[J]. International Studies Quarterly, 2023, 67(3): sqad050. DOI:10.1093/isq/sqad050.",
        "[55] FORBES W P. Unconscious thoughts as a spur and halt on good financial decision making[J]. International Review of Financial Analysis, 2023, 88: 103012. DOI:10.1016/j.irfa.2023.103012.",
        "[56] DOW S. The psychology of financial markets: Keynes, Minsky and emotional finance[M]//The Elgar Companion to Hyman Minsky. Cheltenham: Edward Elgar, 2010. DOI:10.4337/9781849807098.00019.",
        "[57] AMPUDÍA DE HARO F. Good trader, good trading: the presence and the regulation of emotions in financial markets[J]. Athenea Digital, 2014, 14(1): 3-25. DOI:10.5565/rev/athenead/v14n1.1091.",
        "[58] IRFAN M, ADEEL R, MALIK M S. The impact of emotional finance, and market knowledge and investor protection on investment performance in stock and real estate markets[J]. SAGE Open, 2023, 13(4). DOI:10.1177/21582440231206900.",
    ]
    for r in refs:
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.line_spacing = 1.35
        pf.space_after = Pt(3)
        pf.left_indent = Pt(24)
        pf.first_line_indent = Pt(-24)
        run = p.add_run(r)
        _font(run, size=9.5)

    para(doc, "", first_indent=False)
    para(doc, "检索说明：本文文献检索于 2026 年 10 月完成，共执行 24 组中英文检索词，"
              "覆盖 arXiv、OpenAlex、Crossref、Semantic Scholar 与公开网络检索。"
              "OpenAlex 命中 412 条、Crossref 命中 320 条，经主题关键词筛选后并入证据库。"
              "需如实说明三处受限：Giiisp 论文接口因未配置鉴权令牌，状态标记为“接口受限”，"
              "其功能由开放源交叉替代；arXiv 接口返回 Atom XML，本次解析未适配，记 0 命中；"
              "Semantic Scholar 接口返回 HTTP 429（频率限制），记 0 命中。"
              "被剔除的不可靠来源（含一处被垃圾内容劫持的网站）未纳入引用。",
         size=9, first_indent=False, color=(100, 100, 100))

    doc.save(OUT)
    print("SAVED", OUT)


if __name__ == "__main__":
    build()