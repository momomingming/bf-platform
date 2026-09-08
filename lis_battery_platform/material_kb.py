"""
锂硫电池扩展材料知识库
=====================
包含 32 种新型锂硫电池隔膜候选材料的属性数据、代理映射和文献描述。
用于 app.py Tab 6「自定义材料分析」功能。

设计原则
--------
- 每种新材料指定 proxy_material（训练集中最相似的已有材料），
  用于 LabelEncoder 编码，确保预测可行
- 数值属性基于文献合理范围
- 同时支持液态和固态电池扩展
"""


# ============================================================
# 液态电池扩展材料知识库 (25 种)
# ============================================================
EXTENDED_LIQUID_KB = {
    # ───── LDH 系列 (层状双氢氧化物) ─────
    'NiFe-LDH': {
        'name_zh': '镍铁层状双氢氧化物',
        'category': '金属氧化物',
        'proxy_material': 'MnO₂',
        'sa_base': 120.0, 'sa_range': 50.0,
        'ps_base': 30.0, 'pv_base': 0.35,
        'affinity': 0.87,
        'description': ('NiFe-LDH 是二维层状材料，Ni²⁺/Fe³⁺ 双金属活性位点对多硫化物'
                        '具有强化学吸附和催化转化能力，层间空间可物理限域多硫化物。'),
        'advantages': ['双金属协同催化多硫化物转化', '层间空间物理限域多硫化物',
                       '合成简便、成本低', '可通过组分调控优化性能'],
        'disadvantages': ['本征电子导电性一般', '层间水分子需彻底去除',
                          '长循环稳定性待验证'],
        'literature_ref': 'Adv. Energy Mater. 2020, 10, 1903550',
        'aliases': ['NiFe LDH', '镍铁LDH', 'NiFe-层状双氢氧化物',
                    'NiFe层状双氢氧化物', 'nickel iron LDH'],
    },
    'CoAl-LDH': {
        'name_zh': '钴铝层状双氢氧化物',
        'category': '金属氧化物',
        'proxy_material': 'Co₃O₄',
        'sa_base': 85.0, 'sa_range': 35.0,
        'ps_base': 40.0, 'pv_base': 0.28,
        'affinity': 0.84,
        'description': ('CoAl-LDH 利用 Co²⁺ 活性位点吸附多硫化物，层状结构有利于'
                        '电解液浸润和离子传输。'),
        'advantages': ['Co 位点催化活性高', '结构稳定性好', '层间距可调'],
        'disadvantages': ['Co 成本较高', '需控制形貌以获得高比表面积'],
        'literature_ref': 'J. Mater. Chem. A 2019, 7, 4425',
        'aliases': ['CoAl LDH', '钴铝LDH', 'cobalt aluminum LDH'],
    },
    'NiCo-LDH': {
        'name_zh': '镍钴层状双氢氧化物',
        'category': '金属氧化物',
        'proxy_material': 'Co₃O₄',
        'sa_base': 105.0, 'sa_range': 45.0,
        'ps_base': 25.0, 'pv_base': 0.32,
        'affinity': 0.88,
        'description': ('NiCo-LDH 结合 Ni 和 Co 双金属协同效应，对多硫化物吸附-催化'
                        '性能优异，纳米片阵列形貌有利于电子/离子传输。'),
        'advantages': ['双金属协同效应', '高催化活性', '可控纳米片形貌'],
        'disadvantages': ['高温循环稳定性待验证', '合成条件需精确控制'],
        'literature_ref': 'Nano Energy 2021, 82, 105752',
        'aliases': ['NiCo LDH', '镍钴LDH', 'nickel cobalt LDH'],
    },
    'MgAl-LDH': {
        'name_zh': '镁铝层状双氢氧化物',
        'category': '金属氧化物',
        'proxy_material': 'Al₂O₃',
        'sa_base': 65.0, 'sa_range': 30.0,
        'ps_base': 50.0, 'pv_base': 0.25,
        'affinity': 0.72,
        'description': ('MgAl-LDH（水滑石）具有良好的结构稳定性和层间阴离子交换能力，'
                        '可通过离子交换机制捕获多硫化物阴离子。'),
        'advantages': ['层间阴离子交换截留多硫化物', '成本低廉', '环境友好',
                       '制备工艺成熟'],
        'disadvantages': ['催化活性较弱', '多硫化物亲和力相对较低',
                          '电子导电性差'],
        'literature_ref': 'ACS Appl. Mater. Interfaces 2018, 10, 12750',
        'aliases': ['MgAl LDH', '镁铝LDH', '水滑石', 'hydrotalcite'],
    },
    'ZnAl-LDH': {
        'name_zh': '锌铝层状双氢氧化物',
        'category': '金属氧化物',
        'proxy_material': 'ZnO',
        'sa_base': 70.0, 'sa_range': 25.0,
        'ps_base': 45.0, 'pv_base': 0.22,
        'affinity': 0.75,
        'description': ('ZnAl-LDH 利用 Zn²⁺ 位点与多硫化物的化学相互作用，'
                        '层状结构有利于离子传导，且对电解液润湿性好。'),
        'advantages': ['Zn 位点与多硫化物亲和', '结构稳定', '合成条件温和'],
        'disadvantages': ['催化转化能力一般', '比表面积偏低'],
        'literature_ref': 'Electrochim. Acta 2020, 338, 135890',
        'aliases': ['ZnAl LDH', '锌铝LDH', 'zinc aluminum LDH'],
    },

    # ───── MXene 系列 ─────
    'V₂CTₓ': {
        'name_zh': '碳化钒 MXene',
        'category': '其他',
        'proxy_material': 'MXene(Ti₃C₂)',
        'sa_base': 75.0, 'sa_range': 30.0,
        'ps_base': 8.0, 'pv_base': 0.25,
        'affinity': 0.88,
        'description': ('V₂CTₓ MXene 具有优异的金属导电性，V 位点对多硫化物有极强的'
                        '催化转化活性，表面官能团可进一步调控吸附性能。'),
        'advantages': ['V 位点催化活性极高', '金属级导电性',
                       '薄层结构利于离子传输'],
        'disadvantages': ['合成难度较大', '氧化稳定性差', '成本较高'],
        'literature_ref': 'Adv. Mater. 2021, 33, 2008810',
        'aliases': ['V2C MXene', 'V2CTx', '碳化钒', 'V₂C',
                    'V2C', 'vanadium carbide MXene'],
    },
    'Nb₂CTₓ': {
        'name_zh': '碳化铌 MXene',
        'category': '其他',
        'proxy_material': 'MXene(Ti₃C₂)',
        'sa_base': 65.0, 'sa_range': 25.0,
        'ps_base': 10.0, 'pv_base': 0.22,
        'affinity': 0.85,
        'description': ('Nb₂CTₓ MXene 具有良好的导电性和化学稳定性，Nb 位点对多硫化物'
                        '有催化作用，抗氧化能力优于 Ti 基 MXene。'),
        'advantages': ['化学稳定性优于 Ti₃C₂', '催化多硫化物转化',
                       '可调表面化学'],
        'disadvantages': ['制备条件苛刻', '成本高', '研究较少经验有限'],
        'literature_ref': 'ACS Nano 2020, 14, 9142',
        'aliases': ['Nb2C MXene', 'Nb2CTx', '碳化铌', 'Nb₂C',
                    'Nb2C', 'niobium carbide MXene'],
    },
    'Ti₂CTₓ': {
        'name_zh': '碳化钛（薄层）MXene',
        'category': '其他',
        'proxy_material': 'MXene(Ti₃C₂)',
        'sa_base': 110.0, 'sa_range': 40.0,
        'ps_base': 6.0, 'pv_base': 0.28,
        'affinity': 0.86,
        'description': ('Ti₂CTₓ 是较薄的 Ti 基 MXene，比表面积更高，'
                        '表面官能团密度更大，有利于多硫化物吸附。'),
        'advantages': ['更高比表面积', '更多表面活性位点', '良好导电性'],
        'disadvantages': ['力学强度低于 Ti₃C₂Tₓ', '制备选择性差',
                          '稳定性不如三层结构'],
        'literature_ref': 'J. Am. Chem. Soc. 2019, 141, 4730',
        'aliases': ['Ti2C MXene', 'Ti2CTx', 'Ti₂C', 'Ti2C',
                    'thin MXene'],
    },

    # ───── 碳化物 ─────
    'SiC': {
        'name_zh': '碳化硅',
        'category': '其他',
        'proxy_material': 'BN',
        'sa_base': 35.0, 'sa_range': 15.0,
        'ps_base': 80.0, 'pv_base': 0.12,
        'affinity': 0.55,
        'description': ('SiC 纳米颗粒具有优良的化学稳定性和热稳定性，可显著改善隔膜'
                        '机械强度和热安全性，防止热关断失效。'),
        'advantages': ['极高化学稳定性', '优异耐热性', '增强隔膜机械强度'],
        'disadvantages': ['多硫化物吸附能力弱', '电子导电性差',
                          '与电解液界面兼容性一般'],
        'literature_ref': 'J. Power Sources 2019, 436, 226862',
        'aliases': ['碳化硅', 'silicon carbide', '碳化硅纳米颗粒'],
    },
    'WC': {
        'name_zh': '碳化钨',
        'category': '其他',
        'proxy_material': 'TiN',
        'sa_base': 25.0, 'sa_range': 12.0,
        'ps_base': 60.0, 'pv_base': 0.10,
        'affinity': 0.82,
        'description': ('WC 具有类铂催化特性，对多硫化物的电催化转化效果显著，'
                        '可加速氧化还原反应动力学，减少穿梭效应。'),
        'advantages': ['类铂催化活性', '优异电子导电性', '化学稳定性好'],
        'disadvantages': ['密度大、比表面积低', '合成温度高（>1400°C）',
                          '材料成本偏高'],
        'literature_ref': 'Nano Lett. 2020, 20, 6252',
        'aliases': ['碳化钨', 'tungsten carbide', 'WC纳米颗粒'],
    },
    'B₄C': {
        'name_zh': '碳化硼',
        'category': '其他',
        'proxy_material': 'BN',
        'sa_base': 20.0, 'sa_range': 10.0,
        'ps_base': 120.0, 'pv_base': 0.08,
        'affinity': 0.50,
        'description': ('B₄C 是超硬陶瓷材料，硬度仅次于金刚石，可显著增强隔膜'
                        '机械强度，物理阻挡锂枝晶穿刺。'),
        'advantages': ['超高硬度抗枝晶穿刺', '低密度轻量化', '化学惰性'],
        'disadvantages': ['多硫化物亲和力低', '分散性差', '电子导电性低'],
        'literature_ref': 'Chem. Eng. J. 2021, 405, 126947',
        'aliases': ['碳化硼', 'boron carbide', 'B4C'],
    },

    # ───── 其他热门材料 ─────
    '黑磷(BP)': {
        'name_zh': '黑磷',
        'category': '其他',
        'proxy_material': 'MoS₂',
        'sa_base': 45.0, 'sa_range': 20.0,
        'ps_base': 5.0, 'pv_base': 0.15,
        'affinity': 0.90,
        'description': ('黑磷是二维层状半导体，具有可调带隙和极高的多硫化物吸附能力，'
                        'P 原子与多硫化物形成强 P-S 键合。'),
        'advantages': ['极强 P-S 化学键合', '可调带隙适配电化学反应',
                       '二维层状利于传输', '高理论比容量'],
        'disadvantages': ['空气中极易氧化降解', '制备成本极高',
                          '规模化困难', '长期稳定性差'],
        'literature_ref': 'Adv. Mater. 2019, 31, 1900428',
        'aliases': ['BP', '黑磷', 'black phosphorus', '黑鳞',
                    'phosphorene'],
    },
    'Sb₂S₃': {
        'name_zh': '硫化锑',
        'category': '金属硫化物',
        'proxy_material': 'SnS₂',
        'sa_base': 40.0, 'sa_range': 18.0,
        'ps_base': 80.0, 'pv_base': 0.14,
        'affinity': 0.81,
        'description': ('Sb₂S₃ 纳米棒具有一维结构，有利于电子传输，'
                        'Sb 位点可催化多硫化物转化。'),
        'advantages': ['一维纳米棒利于电子传输', '对多硫化物化学亲和',
                       '合成方法多样'],
        'disadvantages': ['导电性一般需碳复合', '体积膨胀问题',
                          '充放电过程可能参与副反应'],
        'literature_ref': 'Energy Storage Mater. 2020, 26, 470',
        'aliases': ['硫化锑', 'antimony sulfide', 'Sb2S3'],
    },
    'Bi₂S₃': {
        'name_zh': '硫化铋',
        'category': '金属硫化物',
        'proxy_material': 'SnS₂',
        'sa_base': 35.0, 'sa_range': 15.0,
        'ps_base': 70.0, 'pv_base': 0.12,
        'affinity': 0.78,
        'description': ('Bi₂S₃ 具有层状结构和窄带隙（~1.3 eV），对多硫化物具有'
                        '良好的化学吸附和催化转化能力。'),
        'advantages': ['窄带隙利于电子传输', '层状结构可剥离为纳米片',
                       '对多硫化物化学吸附'],
        'disadvantages': ['Bi 密度大增加电池重量', '热稳定性一般',
                          '长循环性能待验证'],
        'literature_ref': 'Adv. Funct. Mater. 2020, 30, 1910691',
        'aliases': ['硫化铋', 'bismuth sulfide', 'Bi2S3'],
    },

    # ───── 更多 MOF ─────
    'MOF-808': {
        'name_zh': 'MOF-808（锆基金属有机框架）',
        'category': 'MOF/COF',
        'proxy_material': 'UiO-66',
        'sa_base': 1800.0, 'sa_range': 400.0,
        'ps_base': 4.0, 'pv_base': 0.85,
        'affinity': 0.87,
        'description': ('MOF-808 是 Zr₆ 簇基 MOF，具有大孔径（~18 Å）和丰富的开放'
                        '金属位点，对多硫化物具有强化学吸附能力。'),
        'advantages': ['超高比表面积和孔体积', '大孔径利于多硫化物扩散',
                       '水/化学稳定性优异', '开放 Zr 位点强吸附'],
        'disadvantages': ['电子导电性差', '密度较大', '需与导电材料复合使用'],
        'literature_ref': 'J. Am. Chem. Soc. 2020, 142, 9169',
        'aliases': ['MOF808', 'MOF 808', 'Zr-MOF-808'],
    },
    'PCN-224': {
        'name_zh': 'PCN-224（卟啉基锆 MOF）',
        'category': 'MOF/COF',
        'proxy_material': 'MIL-101(Cr)',
        'sa_base': 2200.0, 'sa_range': 500.0,
        'ps_base': 5.0, 'pv_base': 1.10,
        'affinity': 0.86,
        'description': ('PCN-224 含卟啉配体和 Zr₆ 节点，卟啉中心可金属化，'
                        '提供催化多硫化物转化的活性位。'),
        'advantages': ['卟啉配体可配位催化', '超高比表面积',
                       '热/化学稳定', '可掺入不同金属调控'],
        'disadvantages': ['合成成本高', '电子导电性差', '卟啉配体可能被腐蚀'],
        'literature_ref': 'Angew. Chem. Int. Ed. 2021, 60, 5225',
        'aliases': ['PCN224', 'PCN 224', '卟啉MOF', 'porphyrin MOF'],
    },
    'MIL-53(Fe)': {
        'name_zh': 'MIL-53(Fe)（铁基柔性 MOF）',
        'category': 'MOF/COF',
        'proxy_material': 'UiO-66',
        'sa_base': 1250.0, 'sa_range': 300.0,
        'ps_base': 5.0, 'pv_base': 0.50,
        'affinity': 0.83,
        'description': ('MIL-53(Fe) 具有独特的"呼吸效应"柔性骨架，Fe³⁺ 位点对'
                        '多硫化物有 Lewis 酸吸附作用。'),
        'advantages': ['柔性骨架适应体积变化', 'Fe 位点廉价丰富',
                       '呼吸效应实现响应性吸附'],
        'disadvantages': ['水稳定性一般', '孔径较小限制扩散',
                          '柔性可能导致粉化'],
        'literature_ref': 'Chem. Eng. J. 2019, 378, 122246',
        'aliases': ['MIL53-Fe', 'MIL-53 Fe', 'MIL53(Fe)',
                    '铁基MIL', 'MIL-53'],
    },

    # ───── 更多金属硫化物 ─────
    'FeS₂': {
        'name_zh': '二硫化铁（黄铁矿）',
        'category': '金属硫化物',
        'proxy_material': 'CoS₂',
        'sa_base': 28.0, 'sa_range': 12.0,
        'ps_base': 60.0, 'pv_base': 0.10,
        'affinity': 0.83,
        'description': ('FeS₂（黄铁矿型）具有优异的电催化活性，可高效催化多硫化物'
                        '的氧化还原反应，且资源丰富。'),
        'advantages': ['原料丰富成本低', '电催化活性高', '导电性好（半金属）'],
        'disadvantages': ['体积变化大', '可能参与不可逆副反应',
                          '结构稳定性一般'],
        'literature_ref': 'ACS Nano 2019, 13, 6310',
        'aliases': ['硫化铁', '黄铁矿', 'FeS2', 'pyrite',
                    'iron disulfide'],
    },
    'Ni₃S₂': {
        'name_zh': '硫化镍',
        'category': '金属硫化物',
        'proxy_material': 'NiS₂',
        'sa_base': 42.0, 'sa_range': 18.0,
        'ps_base': 35.0, 'pv_base': 0.14,
        'affinity': 0.86,
        'description': ('Ni₃S₂ 具有金属级导电性和优异的电催化活性，'
                        '是理想的多硫化物转化催化剂。'),
        'advantages': ['金属级导电性', '优异电催化活性', '与硫物种兼容性好'],
        'disadvantages': ['比表面积偏低', '需控制形貌优化', '在某些电位下不稳定'],
        'literature_ref': 'Adv. Mater. 2020, 32, 1906605',
        'aliases': ['Ni3S2', '硫化镍', 'nickel sulfide', 'heazlewoodite'],
    },
    'CuS': {
        'name_zh': '硫化铜',
        'category': '金属硫化物',
        'proxy_material': 'CoS₂',
        'sa_base': 32.0, 'sa_range': 14.0,
        'ps_base': 50.0, 'pv_base': 0.11,
        'affinity': 0.80,
        'description': ('CuS 纳米片具有独特的层状结构和 p 型半导体特性，'
                        '对多硫化物有化学吸附和催化作用。'),
        'advantages': ['层状结构利于离子传输', '成本低廉',
                       'p 型导电有利于电荷传输'],
        'disadvantages': ['在高电位下不稳定', 'Cu²⁺ 可能溶出', '催化活性中等'],
        'literature_ref': 'Small 2019, 15, 1902605',
        'aliases': ['硫化铜', 'copper sulfide', 'covellite', 'CuS纳米片'],
    },
    'MnS': {
        'name_zh': '硫化锰',
        'category': '金属硫化物',
        'proxy_material': 'NiS₂',
        'sa_base': 38.0, 'sa_range': 16.0,
        'ps_base': 55.0, 'pv_base': 0.13,
        'affinity': 0.79,
        'description': ('MnS 纳米颗粒具有多种晶型（α/β/γ），Mn 多价态有利于'
                        '多硫化物的氧化还原催化。'),
        'advantages': ['Mn 多价态催化', '原料丰富', '环境友好'],
        'disadvantages': ['导电性差需碳复合', '研究相对较少',
                          '结构相变可能影响循环稳定性'],
        'literature_ref': 'J. Mater. Chem. A 2020, 8, 3707',
        'aliases': ['硫化锰', 'manganese sulfide', 'MnS纳米颗粒'],
    },

    # ───── 更多金属氧化物 ─────
    'ZrO₂': {
        'name_zh': '氧化锆',
        'category': '金属氧化物',
        'proxy_material': 'TiO₂',
        'sa_base': 50.0, 'sa_range': 25.0,
        'ps_base': 30.0, 'pv_base': 0.18,
        'affinity': 0.76,
        'description': ('ZrO₂ 纳米颗粒具有强 Lewis 酸性位点，可有效吸附多硫化物'
                        '阴离子，同时显著提升隔膜热稳定性。'),
        'advantages': ['强 Lewis 酸吸附多硫化物', '优异热稳定性',
                       '改善隔膜润湿性', '增强机械强度'],
        'disadvantages': ['电子导电性差', '催化转化能力有限', '密度较大'],
        'literature_ref': 'Electrochim. Acta 2019, 295, 112',
        'aliases': ['氧化锆', 'zirconia', 'ZrO2'],
    },
    'SnO₂': {
        'name_zh': '氧化锡',
        'category': '金属氧化物',
        'proxy_material': 'TiO₂',
        'sa_base': 65.0, 'sa_range': 30.0,
        'ps_base': 20.0, 'pv_base': 0.22,
        'affinity': 0.78,
        'description': ('SnO₂ 量子点/纳米颗粒具有丰富的表面氧空位，'
                        '增强对多硫化物的化学吸附。'),
        'advantages': ['氧空位增强吸附', '量子点尺寸效应',
                       '可与碳基材料复合'],
        'disadvantages': ['Sn⁴⁺ 可能被还原', '在低电位下不稳定',
                          '纳米颗粒易团聚'],
        'literature_ref': 'Adv. Sci. 2020, 7, 1903366',
        'aliases': ['氧化锡', 'tin oxide', 'SnO2', 'tin dioxide'],
    },
    'Nb₂O₅': {
        'name_zh': '氧化铌',
        'category': '金属氧化物',
        'proxy_material': 'V₂O₅',
        'sa_base': 35.0, 'sa_range': 18.0,
        'ps_base': 40.0, 'pv_base': 0.15,
        'affinity': 0.80,
        'description': ('Nb₂O₅ 具有丰富的 Nb⁵⁺/Nb⁴⁺ 氧化还原对，可催化多硫化物'
                        '的电化学转化，提升反应动力学。'),
        'advantages': ['氧化还原催化活性', '宽电化学窗口', '结构稳定'],
        'disadvantages': ['导电性低', '比表面积一般', '合成成本较高'],
        'literature_ref': 'Energy Environ. Sci. 2020, 13, 1326',
        'aliases': ['氧化铌', 'niobium oxide', 'Nb2O5',
                    'niobium pentoxide'],
    },
    'Cr₂O₃': {
        'name_zh': '氧化铬',
        'category': '金属氧化物',
        'proxy_material': 'Fe₂O₃',
        'sa_base': 40.0, 'sa_range': 20.0,
        'ps_base': 45.0, 'pv_base': 0.14,
        'affinity': 0.74,
        'description': ('Cr₂O₃ 具有刚玉型结构和丰富的表面羟基，可通过氢键和'
                        'Lewis 酸碱作用吸附多硫化物。'),
        'advantages': ['化学稳定性优异', '成本低廉', '耐高温'],
        'disadvantages': ['催化活性一般', 'Cr 毒性环保问题', '比表面积偏低'],
        'literature_ref': 'J. Electrochem. Soc. 2019, 166, A5143',
        'aliases': ['氧化铬', 'chromium oxide', 'Cr2O3'],
    },
}


# ============================================================
# 固态电池扩展材料知识库 (7 种)
# ============================================================
EXTENDED_SOLID_KB = {
    'Li₆PS₅I': {
        'name_zh': '碘化锂硫代磷酸盐（碘型银锗矿）',
        'category': '硫化物',
        'proxy_material': 'Li₆PS₅Cl',
        'sa_base': 7.0, 'sa_range': 3.0,
        'ps_base': 850.0,
        'cond_base': 1.5e-3,
        'stability': 0.60,
        'density': 2.2,
        'description': ('Li₆PS₅I 是碘取代银锗矿型硫化物电解质，I⁻ 的引入扩大'
                        '晶格常数，有利于 Li⁺ 传输。'),
        'advantages': ['较高离子电导率', 'I⁻ 扩大传输通道', '可冷压成型'],
        'disadvantages': ['空气敏感性强', '与金属锂界面不稳定', '电化学窗口窄'],
        'literature_ref': 'Chem. Mater. 2019, 31, 4564',
        'aliases': ['Li6PS5I', 'LPSI', '碘型银锗矿', 'lithium argyrodite iodide'],
    },
    'Li₃OCl': {
        'name_zh': '反钙钛矿氯氧化锂',
        'category': '卤化物',
        'proxy_material': 'Li₃InCl₆',
        'sa_base': 18.0, 'sa_range': 8.0,
        'ps_base': 400.0,
        'cond_base': 5e-4,
        'stability': 0.78,
        'density': 2.5,
        'description': ('Li₃OCl 反钙钛矿结构对锂金属稳定，合成条件温和，'
                        '是有前景的新型固态电解质候选。'),
        'advantages': ['对锂金属界面稳定', '低成本合成', '密度较低'],
        'disadvantages': ['离子电导率偏低', '水分敏感', '晶粒边界电阻大'],
        'literature_ref': 'Energy Environ. Sci. 2017, 10, 1568',
        'aliases': ['Li3OCl', 'anti-perovskite', '反钙钛矿', 'LAOC',
                    'lithium anti-perovskite'],
    },
    'Li₂S-GeS₂': {
        'name_zh': '锗硫化锂玻璃',
        'category': '硫化物',
        'proxy_material': 'Li₃PS₄',
        'sa_base': 10.0, 'sa_range': 5.0,
        'ps_base': 650.0,
        'cond_base': 8e-4,
        'stability': 0.57,
        'density': 2.6,
        'description': ('(1-x)Li₂S-xGeS₂ 玻璃态电解质，Ge⁴⁺ 提升框架稳定性，'
                        '具有均一的离子传输特性。'),
        'advantages': ['各向同性离子传导', '无晶界电阻', '可调组分优化'],
        'disadvantages': ['Ge 成本极高', '对空气/水分极度敏感', '热稳定性有限'],
        'literature_ref': 'Solid State Ionics 2020, 354, 115400',
        'aliases': ['Li2S-GeS2', '锗基硫化物玻璃', 'germanium sulfide glass'],
    },
    'PEO/LiTFSI': {
        'name_zh': '聚氧化乙烯/双三氟甲磺酰亚胺锂',
        'category': '复合',
        'proxy_material': 'LLZO/PVDF纳米纤维',
        'sa_base': 5.0, 'sa_range': 3.0,
        'ps_base': 200.0,
        'cond_base': 1e-5,
        'stability': 0.88,
        'density': 1.2,
        'description': ('PEO/LiTFSI 是经典聚合物电解质体系，EO 链段配位 Li⁺'
                        '实现离子传导，室温下需加热工作。'),
        'advantages': ['柔性好、界面接触佳', '加工简便', '安全性高', '成本低廉'],
        'disadvantages': ['室温电导率极低 (~10⁻⁵ S/cm)', '需 60°C 以上工作',
                          '电化学窗口窄 (<4 V)', 'Li 枝晶抑制能力弱'],
        'literature_ref': 'Prog. Polym. Sci. 2018, 78, 73',
        'aliases': ['PEO', 'PEO-LiTFSI', '聚醚电解质', '聚氧乙烯',
                    'polyethylene oxide'],
    },
    'Li₃ErCl₆': {
        'name_zh': '氯化铒锂',
        'category': '卤化物',
        'proxy_material': 'Li₃YCl₆',
        'sa_base': 12.0, 'sa_range': 5.0,
        'ps_base': 480.0,
        'cond_base': 5e-4,
        'stability': 0.71,
        'density': 3.3,
        'description': ('Li₃ErCl₆ 属稀土卤化物固态电解质，Er³⁺ 的引入提供独特'
                        '局域结构有利于 Li⁺ 传输。'),
        'advantages': ['宽电化学窗口', '高压正极兼容', '可机械球磨合成'],
        'disadvantages': ['Er 稀土成本高', '对湿度敏感', '离子电导率有待提升'],
        'literature_ref': 'Adv. Energy Mater. 2020, 10, 1902899',
        'aliases': ['Li3ErCl6', '铒基卤化物', 'erbium chloride lithium'],
    },
    'LLZO-Al': {
        'name_zh': '铝掺杂石榴石型 LLZO',
        'category': '氧化物',
        'proxy_material': 'LLZO-Ta',
        'sa_base': 14.0, 'sa_range': 6.0,
        'ps_base': 420.0,
        'cond_base': 4e-4,
        'stability': 0.91,
        'density': 5.0,
        'description': ('Al³⁺ 掺杂稳定立方相 LLZO（Li₆.₂₅Al₀.₂₅La₃Zr₂O₁₂），'
                        '有效提升室温离子电导率。'),
        'advantages': ['低成本掺杂剂', '稳定立方相', '对锂金属相对稳定'],
        'disadvantages': ['Al 可能偏聚影响晶界传输', '高温烧结能耗大',
                          '致密化困难'],
        'literature_ref': 'J. Am. Ceram. Soc. 2019, 102, 4570',
        'aliases': ['LLZO-Al', 'Al-LLZO', '铝掺杂LLZO',
                    'Li6.25Al0.25La3Zr2O12', 'Al doped LLZO'],
    },
    'Li₂S-B₂S₃': {
        'name_zh': '硼硫化锂玻璃',
        'category': '硫化物',
        'proxy_material': 'Li₃PS₄',
        'sa_base': 8.0, 'sa_range': 4.0,
        'ps_base': 700.0,
        'cond_base': 3e-4,
        'stability': 0.54,
        'density': 2.0,
        'description': ('Li₂S-B₂S₃ 玻璃是硼基硫化物体系，B³⁺ 作为网络形成体，'
                        '具有较好的成膜性和均匀离子传输。'),
        'advantages': ['优良成膜性', '无晶界电阻', '组分可调'],
        'disadvantages': ['离子电导率偏低', '水分极度敏感',
                          '玻璃化转变温度低'],
        'literature_ref': 'J. Non-Cryst. Solids 2019, 507, 1',
        'aliases': ['Li2S-B2S3', '硼基硫化物玻璃', 'boron sulfide glass'],
    },
}


# ============================================================
# 合并知识库，按电池类型获取全部扩展材料
# ============================================================
def get_extended_kb(battery_type='liquid'):
    """获取对应电池类型的扩展知识库"""
    return EXTENDED_LIQUID_KB if battery_type == 'liquid' else EXTENDED_SOLID_KB


# ============================================================
# 搜索函数
# ============================================================
def search_material(query, battery_type='liquid'):
    """
    在扩展知识库中搜索材料（模糊匹配 + 评分排序）。

    Parameters
    ----------
    query : str
        用户输入的搜索关键词
    battery_type : str
        'liquid' 或 'solid'

    Returns
    -------
    list of (key, info_dict) tuples — 按匹配相关性降序
    """
    kb = get_extended_kb(battery_type)
    query_lower = query.lower().strip()

    if not query_lower:
        return []

    results = []
    for key, info in kb.items():
        score = 0
        # 精确匹配 key
        if query_lower == key.lower():
            score = 100
        # key 包含查询词
        elif query_lower in key.lower():
            score = 80
        # 中文名匹配
        elif query_lower in info.get('name_zh', ''):
            score = 70
        # 别名匹配
        elif any(query_lower in alias.lower() for alias in info.get('aliases', [])):
            score = 60
        # 类别匹配
        elif query_lower in info.get('category', '').lower():
            score = 40
        # 描述匹配
        elif query_lower in info.get('description', '').lower():
            score = 30

        if score > 0:
            results.append((key, info, score))

    results.sort(key=lambda x: x[2], reverse=True)
    return [(key, info) for key, info, _ in results]


def search_training_kb(query, fillers_dict):
    """
    在已有训练数据库中搜索材料。

    Parameters
    ----------
    query : str
        搜索关键词
    fillers_dict : dict
        LIQUID_FILLERS 或 SOLID_FILLERS

    Returns
    -------
    list of (key, info_dict) tuples
    """
    query_lower = query.lower().strip()
    if not query_lower:
        return []

    results = []
    for key, info in fillers_dict.items():
        if query_lower in key.lower():
            results.append((key, info))
        elif query_lower in info.get('category', '').lower():
            results.append((key, info))
    return results


# ============================================================
# 推荐实验方案
# ============================================================
def get_recommended_config(material_info, battery_type='liquid'):
    """
    根据材料属性推荐实验配置方案。

    Returns
    -------
    dict : 推荐配置键值对
    """
    category = material_info.get('category', '')
    affinity = material_info.get('affinity', 0.7)
    sa = material_info.get('sa_base', 100)

    if battery_type == 'liquid':
        # ---------- 基底推荐 ----------
        if affinity > 0.85:
            substrate_rec = 'Celgard 2400(PP) — 高亲和力填料搭配商用基底即可'
        elif sa > 500:
            substrate_rec = 'PAN 或 PVDF-HFP — 高比表面积填料适合高孔隙率基底'
        else:
            substrate_rec = 'PVDF-HFP 或 PI(聚酰亚胺) — 良好机械性能与孔隙率平衡'

        # ---------- 电解液推荐 ----------
        electrolyte_rec = 'DOL/DME + 1M LiTFSI + 0.2M LiNO₃ — LiNO₃ 添加剂可显著提升库伦效率'

        # ---------- 负载量推荐 ----------
        if affinity > 0.85:
            loading_rec = '0.3 ~ 1.0 mg/cm² — 高亲和力材料无需过多负载'
        elif category in ('MOF/COF',):
            loading_rec = '0.5 ~ 1.5 mg/cm² — 高比表面积材料适中负载即可'
        else:
            loading_rec = '1.0 ~ 2.0 mg/cm² — 需较高负载量补偿较低吸附活性'

        # ---------- 制备建议 ----------
        if category == '金属氧化物':
            prep = '建议真空抽滤法或刮涂法制备改性隔膜，填料先超声分散于乙醇/NMP'
        elif category == 'MOF/COF':
            prep = '建议溶剂辅助自组装法或逐层涂覆，MOF 需先在 DMF 中活化后溶剂交换'
        elif category == '金属硫化物':
            prep = '建议刮涂法制备，填料与粘结剂(PVDF)混合涂覆于商用隔膜表面'
        elif category == '氮化物':
            prep = '建议真空抽滤法或喷涂法，纳米颗粒需在惰性气氛下处理'
        else:
            prep = '建议真空抽滤法或刮涂法制备，注意控制涂层均匀性和厚度'

        return {
            '推荐基底': substrate_rec,
            '推荐电解液': electrolyte_rec,
            '推荐负载量': loading_rec,
            '推荐倍率': '0.2 ~ 1.0 C（首先以 0.5 C 评估基础性能）',
            '推荐温度': '25°C（室温标准测试条件）',
            '制备建议': prep,
        }

    else:  # solid
        stability = material_info.get('stability', 0.7)
        cond = material_info.get('cond_base', 1e-4)

        if cond > 1e-3:
            filler_rec = '30 ~ 50 wt% — 高电导率填料可使用较低含量'
        else:
            filler_rec = '50 ~ 70 wt% — 较低电导率需提高填料占比'

        if stability > 0.85:
            substrate_rec = 'PEO 或 PVDF — 高稳定性填料兼容多种聚合物基体'
        elif stability > 0.65:
            substrate_rec = 'PVDF-HFP 或 PAN — 需要较好的化学稳定性匹配'
        else:
            substrate_rec = 'PAN 或 PVDF — 需在惰性气氛下制备，避免界面副反应'

        if category == '硫化物':
            prep = '建议手套箱内球磨混合+冷压成型，全程 Ar 气氛保护'
        elif category == '氧化物':
            prep = '建议溶液浇铸法或热压法，填料需先高温烧结致密化'
        elif category == '卤化物':
            prep = '建议机械球磨法制备复合电解质，注意严格无水操作'
        else:
            prep = '建议溶液浇铸法，在干燥房/手套箱内制备'

        return {
            '推荐填料含量': filler_rec,
            '推荐基底/聚合物': substrate_rec,
            '推荐成型工艺': prep,
            '推荐工作温度': '25 ~ 60°C（视电导率决定是否需升温）',
            '推荐压力': '200 ~ 350 MPa（冷压成型参考值）',
        }
