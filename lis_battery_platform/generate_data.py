"""
锂硫电池隔膜填料与基底材料数据生成模块
基于文献真实物理关系编码，生成1200+样本数据
"""
import numpy as np
import pandas as pd

np.random.seed(42)

# ============================================================
# 液态电池填料数据库 (文献来源)
# ============================================================
LIQUID_FILLERS = {
    # 碳基材料
    'CNT': {'category': '碳基', 'sa_base': 260, 'sa_range': 80, 'ps_base': 35, 'pv_base': 0.75, 'affinity': 0.65},
    'MWCNT': {'category': '碳基', 'sa_base': 210, 'sa_range': 60, 'ps_base': 45, 'pv_base': 0.65, 'affinity': 0.60},
    '石墨烯': {'category': '碳基', 'sa_base': 420, 'sa_range': 150, 'ps_base': 8, 'pv_base': 0.85, 'affinity': 0.72},
    '氧化石墨烯(GO)': {'category': '碳基', 'sa_base': 380, 'sa_range': 120, 'ps_base': 5, 'pv_base': 0.70, 'affinity': 0.85},
    'rGO': {'category': '碳基', 'sa_base': 340, 'sa_range': 100, 'ps_base': 6, 'pv_base': 0.78, 'affinity': 0.75},
    '介孔碳(CMK-3)': {'category': '碳基', 'sa_base': 950, 'sa_range': 250, 'ps_base': 12, 'pv_base': 1.35, 'affinity': 0.68},
    '碳黑(Super P)': {'category': '碳基', 'sa_base': 62, 'sa_range': 15, 'ps_base': 40, 'pv_base': 0.25, 'affinity': 0.45},
    '碳纳米纤维(CNF)': {'category': '碳基', 'sa_base': 180, 'sa_range': 60, 'ps_base': 120, 'pv_base': 0.55, 'affinity': 0.58},
    '氮掺杂碳': {'category': '碳基', 'sa_base': 480, 'sa_range': 150, 'ps_base': 15, 'pv_base': 0.90, 'affinity': 0.82},
    '多孔碳球': {'category': '碳基', 'sa_base': 750, 'sa_range': 200, 'ps_base': 20, 'pv_base': 1.10, 'affinity': 0.70},
    # 金属氧化物
    'TiO₂': {'category': '金属氧化物', 'sa_base': 55, 'sa_range': 30, 'ps_base': 25, 'pv_base': 0.18, 'affinity': 0.80},
    'MnO₂': {'category': '金属氧化物', 'sa_base': 85, 'sa_range': 40, 'ps_base': 30, 'pv_base': 0.25, 'affinity': 0.82},
    'Al₂O₃': {'category': '金属氧化物', 'sa_base': 120, 'sa_range': 50, 'ps_base': 20, 'pv_base': 0.35, 'affinity': 0.70},
    'ZnO': {'category': '金属氧化物', 'sa_base': 35, 'sa_range': 15, 'ps_base': 50, 'pv_base': 0.12, 'affinity': 0.72},
    'CeO₂': {'category': '金属氧化物', 'sa_base': 65, 'sa_range': 25, 'ps_base': 18, 'pv_base': 0.20, 'affinity': 0.78},
    'V₂O₅': {'category': '金属氧化物', 'sa_base': 40, 'sa_range': 20, 'ps_base': 35, 'pv_base': 0.15, 'affinity': 0.83},
    'Co₃O₄': {'category': '金属氧化物', 'sa_base': 70, 'sa_range': 30, 'ps_base': 28, 'pv_base': 0.22, 'affinity': 0.80},
    'Fe₂O₃': {'category': '金属氧化物', 'sa_base': 45, 'sa_range': 20, 'ps_base': 40, 'pv_base': 0.15, 'affinity': 0.75},
    'WO₃': {'category': '金属氧化物', 'sa_base': 38, 'sa_range': 18, 'ps_base': 32, 'pv_base': 0.13, 'affinity': 0.77},
    'La₂O₃': {'category': '金属氧化物', 'sa_base': 25, 'sa_range': 12, 'ps_base': 55, 'pv_base': 0.10, 'affinity': 0.73},
    # 金属硫化物
    'CoS₂': {'category': '金属硫化物', 'sa_base': 45, 'sa_range': 20, 'ps_base': 30, 'pv_base': 0.15, 'affinity': 0.88},
    'NiS₂': {'category': '金属硫化物', 'sa_base': 40, 'sa_range': 18, 'ps_base': 35, 'pv_base': 0.14, 'affinity': 0.85},
    'MoS₂': {'category': '金属硫化物', 'sa_base': 55, 'sa_range': 25, 'ps_base': 25, 'pv_base': 0.18, 'affinity': 0.82},
    'VS₂': {'category': '金属硫化物', 'sa_base': 50, 'sa_range': 22, 'ps_base': 28, 'pv_base': 0.16, 'affinity': 0.84},
    'TiS₂': {'category': '金属硫化物', 'sa_base': 35, 'sa_range': 15, 'ps_base': 32, 'pv_base': 0.12, 'affinity': 0.80},
    'WS₂': {'category': '金属硫化物', 'sa_base': 42, 'sa_range': 20, 'ps_base': 30, 'pv_base': 0.14, 'affinity': 0.81},
    'SnS₂': {'category': '金属硫化物', 'sa_base': 38, 'sa_range': 16, 'ps_base': 38, 'pv_base': 0.13, 'affinity': 0.79},
    # MOF/COF
    'ZIF-8': {'category': 'MOF/COF', 'sa_base': 1500, 'sa_range': 400, 'ps_base': 5, 'pv_base': 0.65, 'affinity': 0.88},
    'ZIF-67': {'category': 'MOF/COF', 'sa_base': 1600, 'sa_range': 350, 'ps_base': 4, 'pv_base': 0.70, 'affinity': 0.90},
    'UiO-66': {'category': 'MOF/COF', 'sa_base': 1200, 'sa_range': 300, 'ps_base': 3, 'pv_base': 0.55, 'affinity': 0.85},
    'MIL-101(Cr)': {'category': 'MOF/COF', 'sa_base': 3200, 'sa_range': 800, 'ps_base': 4, 'pv_base': 1.40, 'affinity': 0.87},
    'HKUST-1': {'category': 'MOF/COF', 'sa_base': 1700, 'sa_range': 400, 'ps_base': 6, 'pv_base': 0.72, 'affinity': 0.83},
    'COF-LZU1': {'category': 'MOF/COF', 'sa_base': 450, 'sa_range': 150, 'ps_base': 8, 'pv_base': 0.35, 'affinity': 0.80},
    'TpPa-COF': {'category': 'MOF/COF', 'sa_base': 550, 'sa_range': 180, 'ps_base': 6, 'pv_base': 0.40, 'affinity': 0.82},
    # 氮化物
    'TiN': {'category': '氮化物', 'sa_base': 65, 'sa_range': 25, 'ps_base': 22, 'pv_base': 0.20, 'affinity': 0.86},
    'VN': {'category': '氮化物', 'sa_base': 55, 'sa_range': 20, 'ps_base': 25, 'pv_base': 0.18, 'affinity': 0.84},
    'BN': {'category': '氮化物', 'sa_base': 30, 'sa_range': 15, 'ps_base': 50, 'pv_base': 0.10, 'affinity': 0.68},
    'g-C₃N₄': {'category': '氮化物', 'sa_base': 85, 'sa_range': 35, 'ps_base': 18, 'pv_base': 0.28, 'affinity': 0.80},
    'Mo₂N': {'category': '氮化物', 'sa_base': 48, 'sa_range': 20, 'ps_base': 28, 'pv_base': 0.16, 'affinity': 0.83},
    # 聚合物涂层
    'PANI(聚苯胺)': {'category': '聚合物', 'sa_base': 35, 'sa_range': 15, 'ps_base': 80, 'pv_base': 0.12, 'affinity': 0.72},
    'PPy(聚吡咯)': {'category': '聚合物', 'sa_base': 40, 'sa_range': 18, 'ps_base': 70, 'pv_base': 0.14, 'affinity': 0.74},
    'PDA(聚多巴胺)': {'category': '聚合物', 'sa_base': 25, 'sa_range': 12, 'ps_base': 60, 'pv_base': 0.08, 'affinity': 0.88},
    # 其他
    'SiO₂': {'category': '其他', 'sa_base': 200, 'sa_range': 80, 'ps_base': 15, 'pv_base': 0.55, 'affinity': 0.60},
    'MXene(Ti₃C₂)': {'category': '其他', 'sa_base': 95, 'sa_range': 35, 'ps_base': 10, 'pv_base': 0.30, 'affinity': 0.90},
}

# ============================================================
# 液态电池基底材料
# ============================================================
LIQUID_SUBSTRATES = {
    'Celgard 2400(PP)': {'thickness_base': 25, 'porosity_base': 0.41, 'mechanical': 120},
    'Celgard 2500(PE)': {'thickness_base': 25, 'porosity_base': 0.55, 'mechanical': 95},
    'Celgard 3501(PP/PE/PP)': {'thickness_base': 35, 'porosity_base': 0.45, 'mechanical': 140},
    'PVDF': {'thickness_base': 30, 'porosity_base': 0.60, 'mechanical': 55},
    'PVDF-HFP': {'thickness_base': 28, 'porosity_base': 0.65, 'mechanical': 48},
    'PAN': {'thickness_base': 22, 'porosity_base': 0.70, 'mechanical': 65},
    'PI(聚酰亚胺)': {'thickness_base': 20, 'porosity_base': 0.55, 'mechanical': 180},
    'PET': {'thickness_base': 18, 'porosity_base': 0.50, 'mechanical': 160},
    '纤维素膜': {'thickness_base': 35, 'porosity_base': 0.68, 'mechanical': 40},
    '尼龙膜': {'thickness_base': 25, 'porosity_base': 0.62, 'mechanical': 70},
    'GF/A(玻璃纤维)': {'thickness_base': 260, 'porosity_base': 0.80, 'mechanical': 25},
    'Whatman GF/D': {'thickness_base': 670, 'porosity_base': 0.85, 'mechanical': 18},
}

# ============================================================
# 液态电解液体系
# ============================================================
LIQUID_ELECTROLYTES = {
    'DOL/DME + 1M LiTFSI': {'cond_base': 1.2, 'viscosity': 0.8},
    'DOL/DME + 1M LiTFSI + 0.1M LiNO₃': {'cond_base': 1.1, 'viscosity': 0.85},
    'DOL/DME + 1M LiTFSI + 0.2M LiNO₃': {'cond_base': 1.05, 'viscosity': 0.90},
    'DOL/DME + 1M LiTFSI + 0.5M LiNO₃': {'cond_base': 0.95, 'viscosity': 1.0},
    'TEGDME + 1M LiTFSI': {'cond_base': 0.65, 'viscosity': 1.8},
    'TEGDME + 1M LiTFSI + 0.1M LiNO₃': {'cond_base': 0.60, 'viscosity': 1.85},
    'DOL/DME + 2M LiTFSI': {'cond_base': 0.85, 'viscosity': 1.3},
    'DOL/DME + 0.5M LiTFSI': {'cond_base': 1.5, 'viscosity': 0.6},
    '砜类(DIPAS) + 1M LiTFSI': {'cond_base': 0.50, 'viscosity': 2.5},
    '离子液体(PYR₁₄TFSI) + 0.5M LiTFSI': {'cond_base': 0.35, 'viscosity': 3.2},
}

# ============================================================
# 固态电池填料(固态电解质)数据库
# ============================================================
SOLID_FILLERS = {
    # 氧化物
    'LLZO(Li₇La₃Zr₂O₁₂)': {'category': '氧化物', 'cond_base': 3e-4, 'sa_base': 15, 'ps_base': 500, 'stability': 0.92, 'density': 5.1},
    'LLZO-Ta': {'category': '氧化物', 'cond_base': 6e-4, 'sa_base': 12, 'ps_base': 450, 'stability': 0.93, 'density': 5.3},
    'LLZO-Nb': {'category': '氧化物', 'cond_base': 5e-4, 'sa_base': 13, 'ps_base': 480, 'stability': 0.91, 'density': 5.2},
    'LATP(Li₁.₃Al₀.₃Ti₁.₇(PO₄)₃)': {'category': '氧化物', 'cond_base': 3e-4, 'sa_base': 18, 'ps_base': 350, 'stability': 0.80, 'density': 3.6},
    'LAGP(Li₁.₅Al₀.₅Ge₁.₅(PO₄)₃)': {'category': '氧化物', 'cond_base': 4e-4, 'sa_base': 16, 'ps_base': 400, 'stability': 0.82, 'density': 3.5},
    'LLTO(Li₃xLa₂/₃-xTiO₃)': {'category': '氧化物', 'cond_base': 1e-3, 'sa_base': 10, 'ps_base': 600, 'stability': 0.75, 'density': 4.9},
    'Li₁.₄Al₀.₄Ti₁.₆(PO₄)₃': {'category': '氧化物', 'cond_base': 2.5e-4, 'sa_base': 20, 'ps_base': 300, 'stability': 0.78, 'density': 3.7},
    # 硫化物
    'Li₆PS₅Cl': {'category': '硫化物', 'cond_base': 3e-3, 'sa_base': 8, 'ps_base': 800, 'stability': 0.55, 'density': 2.1},
    'Li₆PS₅Br': {'category': '硫化物', 'cond_base': 2e-3, 'sa_base': 9, 'ps_base': 750, 'stability': 0.58, 'density': 2.3},
    'Li₁₀GeP₂S₁₂(LGPS)': {'category': '硫化物', 'cond_base': 1.2e-2, 'sa_base': 6, 'ps_base': 900, 'stability': 0.50, 'density': 2.5},
    'Li₃PS₄': {'category': '硫化物', 'cond_base': 8e-4, 'sa_base': 12, 'ps_base': 600, 'stability': 0.60, 'density': 2.0},
    'Li₂S-P₂S₅(75:25)': {'category': '硫化物', 'cond_base': 2e-3, 'sa_base': 10, 'ps_base': 700, 'stability': 0.52, 'density': 2.2},
    'Li₇P₃S₁₁': {'category': '硫化物', 'cond_base': 2.5e-3, 'sa_base': 7, 'ps_base': 850, 'stability': 0.53, 'density': 2.3},
    'Li₉.₅₄Si₁.₇₄P₁.₄₄S₁₁.₇Cl₀.₃': {'category': '硫化物', 'cond_base': 2.5e-2, 'sa_base': 5, 'ps_base': 950, 'stability': 0.48, 'density': 2.4},
    'Na₃PS₄(参考)': {'category': '硫化物', 'cond_base': 5e-4, 'sa_base': 14, 'ps_base': 550, 'stability': 0.56, 'density': 2.0},
    # 磷酸盐
    'LISICON(Li₂+2xZn₁-xGeO₄)': {'category': '磷酸盐', 'cond_base': 1e-4, 'sa_base': 22, 'ps_base': 250, 'stability': 0.85, 'density': 3.8},
    'Li₃PO₄': {'category': '磷酸盐', 'cond_base': 5e-6, 'sa_base': 35, 'ps_base': 150, 'stability': 0.95, 'density': 2.4},
    'LiPON': {'category': '磷酸盐', 'cond_base': 2e-6, 'sa_base': 40, 'ps_base': 100, 'stability': 0.90, 'density': 2.3},
    # 卤化物
    'Li₃InCl₆': {'category': '卤化物', 'cond_base': 1.5e-3, 'sa_base': 11, 'ps_base': 500, 'stability': 0.70, 'density': 3.2},
    'Li₃YCl₆': {'category': '卤化物', 'cond_base': 1e-3, 'sa_base': 13, 'ps_base': 450, 'stability': 0.72, 'density': 3.0},
    'Li₃ScCl₆': {'category': '卤化物', 'cond_base': 3e-3, 'sa_base': 10, 'ps_base': 520, 'stability': 0.68, 'density': 2.9},
    'Li₂ZrCl₆': {'category': '卤化物', 'cond_base': 8e-4, 'sa_base': 15, 'ps_base': 400, 'stability': 0.74, 'density': 3.1},
    # 硼氢化物
    'LiBH₄': {'category': '硼氢化物', 'cond_base': 1e-3, 'sa_base': 25, 'ps_base': 200, 'stability': 0.45, 'density': 0.9},
    'Li₂B₁₂H₁₂': {'category': '硼氢化物', 'cond_base': 5e-4, 'sa_base': 20, 'ps_base': 250, 'stability': 0.50, 'density': 1.1},
    # 复合填料
    'LLZO@GO复合': {'category': '复合', 'cond_base': 5e-4, 'sa_base': 180, 'ps_base': 50, 'stability': 0.88, 'density': 3.5},
    'LATP/CNT复合': {'category': '复合', 'cond_base': 4e-4, 'sa_base': 150, 'ps_base': 60, 'stability': 0.78, 'density': 3.0},
    'LLZO/PVDF纳米纤维': {'category': '复合', 'cond_base': 2e-4, 'sa_base': 90, 'ps_base': 100, 'stability': 0.85, 'density': 2.8},
}

# ============================================================
# 固态电池基底/聚合物电解质
# ============================================================
SOLID_SUBSTRATES = {
    'PEO(聚环氧乙烷)': {'thickness_base': 50, 'conductivity': 1e-5, 'mechanical': 15, 'crystallinity': 0.65},
    'PVDF': {'thickness_base': 40, 'conductivity': 1e-7, 'mechanical': 55, 'crystallinity': 0.55},
    'PVDF-HFP': {'thickness_base': 35, 'conductivity': 5e-7, 'mechanical': 42, 'crystallinity': 0.40},
    'PAN(聚丙烯腈)': {'thickness_base': 30, 'conductivity': 1e-6, 'mechanical': 65, 'crystallinity': 0.50},
    'PMMA(聚甲基丙烯酸甲酯)': {'thickness_base': 45, 'conductivity': 5e-8, 'mechanical': 70, 'crystallinity': 0.30},
    'PPC(聚碳酸亚丙酯)': {'thickness_base': 40, 'conductivity': 2e-6, 'mechanical': 25, 'crystallinity': 0.20},
    'PCL(聚己内酯)': {'thickness_base': 55, 'conductivity': 5e-6, 'mechanical': 20, 'crystallinity': 0.55},
    'PEG(聚乙二醇)': {'thickness_base': 35, 'conductivity': 1e-5, 'mechanical': 8, 'crystallinity': 0.70},
    'PVA(聚乙烯醇)': {'thickness_base': 30, 'conductivity': 1e-7, 'mechanical': 80, 'crystallinity': 0.60},
    '纤维素基': {'thickness_base': 45, 'conductivity': 1e-7, 'mechanical': 45, 'crystallinity': 0.70},
    'PI(聚酰亚胺)': {'thickness_base': 25, 'conductivity': 1e-9, 'mechanical': 180, 'crystallinity': 0.45},
    '尼龙6': {'thickness_base': 35, 'conductivity': 5e-8, 'mechanical': 75, 'crystallinity': 0.50},
}


def generate_liquid_data(n_samples=650):
    """生成液态锂硫电池数据，编码真实物理关系"""
    rng = np.random.RandomState(42)
    records = []
    
    filler_names = list(LIQUID_FILLERS.keys())
    substrate_names = list(LIQUID_SUBSTRATES.keys())
    electrolyte_names = list(LIQUID_ELECTROLYTES.keys())
    
    # 按类别权重采样（碳基和金属氧化物更常见）
    category_weights = {'碳基': 3.0, '金属氧化物': 2.5, '金属硫化物': 2.0, 
                        'MOF/COF': 1.5, '氮化物': 1.5, '聚合物': 1.0, '其他': 1.0}
    filler_weights = np.array([category_weights[LIQUID_FILLERS[f]['category']] for f in filler_names])
    filler_weights /= filler_weights.sum()
    
    for i in range(n_samples):
        # 随机选择材料组合
        filler_name = rng.choice(filler_names, p=filler_weights)
        filler = LIQUID_FILLERS[filler_name]
        substrate_name = rng.choice(substrate_names)
        substrate = LIQUID_SUBSTRATES[substrate_name]
        electrolyte_name = rng.choice(electrolyte_names)
        electrolyte = LIQUID_ELECTROLYTES[electrolyte_name]
        
        # 生成特征
        filler_loading = rng.uniform(0.05, 3.0)  # mg/cm²
        surface_area = max(5, filler['sa_base'] + rng.normal(0, filler['sa_range'] * 0.3))
        particle_size = max(1, filler['ps_base'] + rng.normal(0, filler['ps_base'] * 0.2))
        pore_volume = max(0.01, filler['pv_base'] + rng.normal(0, filler['pv_base'] * 0.15))
        thickness = max(5, substrate['thickness_base'] + rng.normal(0, 5))
        porosity = np.clip(substrate['porosity_base'] + rng.normal(0, 0.05), 0.15, 0.95)
        temperature = rng.choice([25, 25, 25, 30, 35, 40, 45, 50, 55, 60])  # 偏向室温
        current_rate = rng.choice([0.1, 0.2, 0.2, 0.5, 0.5, 0.5, 1.0, 1.0, 2.0, 3.0, 5.0])
        cycle_number = rng.choice([50, 100, 100, 200, 200, 300, 500, 500, 800, 1000])
        
        # === 编码物理关系计算目标值 ===
        
        # 1. 离子电导率 (mS/cm)
        # 基础: 电解液电导率，受温度和填料影响
        temp_factor = 1 + 0.02 * (temperature - 25)
        # 高比表面积填料可提升离子传输（提供更多通道）
        sa_enhancement = 1 + 0.0003 * surface_area * min(filler_loading, 1.5)
        # 过多填料阻塞孔道
        loading_penalty = 1 - 0.1 * max(0, filler_loading - 1.5)
        # 高孔隙率基底有利于离子传输
        porosity_factor = 0.7 + 0.6 * porosity
        ionic_cond = (electrolyte['cond_base'] * temp_factor * sa_enhancement * 
                      loading_penalty * porosity_factor)
        ionic_cond *= (1 + rng.normal(0, 0.08))  # 8%噪声
        ionic_cond = max(0.05, ionic_cond)
        
        # 2. 初始比容量 (mAh/g)
        # 理论值: 1675 mAh/g
        # 硫利用率取决于: 导电性(碳基>其他)、吸附能力、倍率
        cat = filler['category']
        base_utilization = {'碳基': 0.72, '金属氧化物': 0.65, '金属硫化物': 0.68,
                           'MOF/COF': 0.70, '氮化物': 0.67, '聚合物': 0.55, '其他': 0.60}
        utilization = base_utilization[cat]
        # 比表面积贡献
        utilization += 0.00008 * surface_area
        # 填料负载量（适量最佳）
        loading_opt = 1.0 - 0.15 * (filler_loading - 1.0)**2
        utilization *= max(0.5, loading_opt)
        # 倍率影响（高倍率降低利用率）
        rate_factor = 1.0 - 0.12 * np.log10(current_rate / 0.1)
        utilization *= max(0.4, rate_factor)
        # 孔体积有利于硫负载
        pore_factor = 1 + 0.15 * pore_volume
        utilization *= pore_factor
        # 温度轻微正向
        utilization *= (1 + 0.003 * max(0, temperature - 25))
        initial_capacity = 1675 * np.clip(utilization, 0.2, 0.95)
        initial_capacity *= (1 + rng.normal(0, 0.05))
        initial_capacity = np.clip(initial_capacity, 300, 1600)
        
        # 3. 容量保持率 (%)
        # 取决于: 填料吸附能力、循环数、基底稳定性
        affinity = filler['affinity']
        # 基础衰减
        base_retention = 95 - 0.02 * cycle_number
        # 填料吸附能力增强保持率
        affinity_bonus = 15 * affinity * min(filler_loading, 2.0)
        # 高比表面积帮助
        sa_bonus = 0.005 * surface_area * affinity
        # 循环数越多衰减越多
        cycle_decay = 0.005 * cycle_number * (1 - 0.5 * affinity)
        # 基底机械强度贡献
        mech_bonus = 0.02 * substrate['mechanical']
        retention = base_retention + affinity_bonus + sa_bonus - cycle_decay + mech_bonus
        retention += rng.normal(0, 3)
        retention = np.clip(retention, 30, 99)
        
        # 4. 库伦效率 (%)
        # LiNO3添加剂显著提升CE
        has_lino3 = 'LiNO₃' in electrolyte_name
        base_ce = 96.5 if has_lino3 else 92.0
        # 填料吸附多硫化物提升CE
        ce_bonus = 2.5 * affinity * min(filler_loading, 2.0)
        # 高倍率略提升CE（减少穿梭时间）
        rate_ce_bonus = 0.3 * np.log10(max(0.1, current_rate))
        # 温度过高降低CE
        temp_penalty = 0.05 * max(0, temperature - 40)
        ce = base_ce + ce_bonus + rate_ce_bonus - temp_penalty
        ce += rng.normal(0, 0.8)
        ce = np.clip(ce, 85, 99.9)
        
        # 5. 多硫化物穿梭因子 (0-1, 越小越好)
        # 与填料吸附能力、LiNO3、基底孔隙率相关
        base_shuttle = 0.35
        # 强吸附降低穿梭
        shuttle_reduction = 0.25 * affinity * min(filler_loading, 2.0)
        # LiNO3保护锂负极
        lino3_reduction = 0.12 if has_lino3 else 0
        # 高比表面积物理阻隔
        sa_shuttle = 0.0001 * surface_area
        # 高孔隙率反而可能增加穿梭
        pore_shuttle = 0.15 * (porosity - 0.4)
        shuttle = base_shuttle - shuttle_reduction - lino3_reduction - sa_shuttle + pore_shuttle
        shuttle += rng.normal(0, 0.03)
        shuttle = np.clip(shuttle, 0.02, 0.50)
        
        records.append({
            '填料类型': filler_name,
            '填料类别': cat,
            '填料负载量(mg/cm²)': round(filler_loading, 3),
            '比表面积(m²/g)': round(surface_area, 1),
            '粒径(nm)': round(particle_size, 1),
            '孔体积(cm³/g)': round(pore_volume, 3),
            '基底材料': substrate_name,
            '隔膜厚度(μm)': round(thickness, 1),
            '孔隙率': round(porosity, 3),
            '电解液体系': electrolyte_name,
            '温度(°C)': temperature,
            '倍率(C)': current_rate,
            '循环次数': cycle_number,
            '离子电导率(mS/cm)': round(ionic_cond, 3),
            '初始比容量(mAh/g)': round(initial_capacity, 1),
            '容量保持率(%)': round(retention, 1),
            '库伦效率(%)': round(ce, 2),
            '穿梭因子': round(shuttle, 4),
        })
    
    return pd.DataFrame(records)


def generate_solid_data(n_samples=600):
    """生成固态锂硫电池数据"""
    rng = np.random.RandomState(123)
    records = []
    
    filler_names = list(SOLID_FILLERS.keys())
    substrate_names = list(SOLID_SUBSTRATES.keys())
    
    # 硫化物和氧化物更常见
    category_weights = {'氧化物': 2.5, '硫化物': 2.5, '磷酸盐': 1.0, 
                        '卤化物': 1.5, '硼氢化物': 0.8, '复合': 1.5}
    filler_weights = np.array([category_weights[SOLID_FILLERS[f]['category']] for f in filler_names])
    filler_weights /= filler_weights.sum()
    
    for i in range(n_samples):
        filler_name = rng.choice(filler_names, p=filler_weights)
        filler = SOLID_FILLERS[filler_name]
        substrate_name = rng.choice(substrate_names)
        substrate = SOLID_SUBSTRATES[substrate_name]
        
        # 生成特征
        filler_content = rng.uniform(10, 80)  # wt%
        surface_area = max(2, filler['sa_base'] + rng.normal(0, filler['sa_base'] * 0.2))
        particle_size = max(10, filler['ps_base'] + rng.normal(0, filler['ps_base'] * 0.15))
        thickness = max(10, substrate['thickness_base'] + rng.normal(0, 8))
        temperature = rng.choice([25, 25, 30, 30, 40, 45, 50, 55, 60, 60, 70, 80])
        pressure = rng.uniform(50, 500)  # MPa
        current_rate = rng.choice([0.05, 0.1, 0.1, 0.2, 0.2, 0.5, 0.5, 1.0])
        cycle_number = rng.choice([50, 100, 100, 200, 200, 300, 500, 800])
        
        # === 编码物理关系 ===
        
        # 1. 离子电导率 (mS/cm)
        # 填料本身电导率 × 含量因子 × 温度Arrhenius
        filler_cond = filler['cond_base'] * 1000  # 转mS/cm
        # 渗透阈值效应：~30wt%以上形成连续通路
        if filler_content > 30:
            content_factor = (filler_content / 100) ** 1.5
        else:
            content_factor = (filler_content / 100) ** 2.5  # 低于渗透阈值，电导率急剧下降
        # 基底聚合物电导率贡献
        polymer_cond = substrate['conductivity'] * 1000  # mS/cm
        # Arrhenius温度依赖 (Ea ≈ 0.3 eV for oxides, 0.2 eV for sulfides)
        ea = {'氧化物': 0.30, '硫化物': 0.20, '磷酸盐': 0.35, 
              '卤化物': 0.25, '硼氢化物': 0.28, '复合': 0.27}
        activation_energy = ea[filler['category']]
        temp_factor = np.exp(activation_energy / 8.617e-5 * (1.0/298.15 - 1.0/(temperature + 273.15)))
        ionic_cond = (filler_cond * content_factor + polymer_cond * (1 - content_factor/100)) * temp_factor
        ionic_cond *= (1 + rng.normal(0, 0.12))
        ionic_cond = max(1e-5, ionic_cond)
        
        # 2. 界面阻抗 (Ω·cm²)
        # 与颗粒尺寸正相关、压力负相关、填料稳定性相关
        base_impedance = 50
        # 大颗粒 → 接触差 → 高阻抗
        size_factor = 1 + 0.001 * particle_size
        # 压力改善接触
        pressure_factor = 1 / (1 + 0.003 * pressure)
        # 硫化物较软，接触好
        cat = filler['category']
        softness = {'氧化物': 0.3, '硫化物': 0.8, '磷酸盐': 0.4, 
                    '卤化物': 0.6, '硼氢化物': 0.7, '复合': 0.5}
        contact_quality = softness[cat]
        # 填料含量高 → 界面更多
        content_impedance = 1 + 0.01 * filler_content
        # 温度帮助界面扩散
        temp_interface = 1 / (1 + 0.01 * max(0, temperature - 30))
        impedance = (base_impedance * size_factor * pressure_factor * 
                     (2 - contact_quality) * content_impedance * temp_interface)
        # 聚合物柔顺性降低阻抗
        polymer_flex = 1 - 0.3 * (1 - substrate['crystallinity'])
        impedance *= polymer_flex
        impedance *= (1 + rng.normal(0, 0.10))
        impedance = max(5, impedance)
        
        # 3. 初始比容量 (mAh/g)
        base_util = 0.55  # 固态基础利用率低于液态
        # 高离子电导率有利于硫利用
        cond_bonus = 0.05 * np.log10(max(1e-5, ionic_cond))
        # 界面好 → 活性物质利用高
        interface_bonus = -0.03 * np.log10(max(1, impedance))
        # 小颗粒 → 更多活性位点
        size_bonus = -0.02 * np.log10(max(10, particle_size))
        # 温度提升动力学
        temp_bonus = 0.004 * max(0, temperature - 25)
        # 低倍率
        rate_factor = 1.0 - 0.15 * np.log10(max(0.05, current_rate) / 0.05)
        utilization = base_util + cond_bonus + interface_bonus + size_bonus + temp_bonus
        utilization *= max(0.3, rate_factor)
        initial_capacity = 1675 * np.clip(utilization, 0.1, 0.85)
        initial_capacity *= (1 + rng.normal(0, 0.06))
        initial_capacity = np.clip(initial_capacity, 150, 1400)
        
        # 4. 容量保持率 (%)
        base_ret = 92
        # 填料稳定性
        stability_bonus = 10 * filler['stability']
        # 循环衰减
        cycle_decay = 0.025 * cycle_number * (1 - 0.3 * filler['stability'])
        # 压力维持接触
        pressure_ret = 0.01 * pressure
        # 高温加速退化
        temp_decay = 0.08 * max(0, temperature - 50)
        # 界面阻抗增长
        impedance_decay = 0.02 * impedance / 100
        retention = base_ret + stability_bonus - cycle_decay + pressure_ret - temp_decay - impedance_decay
        retention += rng.normal(0, 3.5)
        retention = np.clip(retention, 25, 98)
        
        # 5. 库伦效率 (%)
        base_ce = 97.5  # 固态基础CE较高（锂枝晶抑制）
        # 硫化物对锂不稳定
        stability_ce = -2 * (1 - filler['stability'])
        # 高温降低CE
        temp_ce = -0.04 * max(0, temperature - 45)
        # 压力提升CE
        pressure_ce = 0.002 * pressure
        # 界面阻抗高可能导致锂不均匀沉积
        interface_ce = -0.005 * impedance / 50
        ce = base_ce + stability_ce + temp_ce + pressure_ce + interface_ce
        ce += rng.normal(0, 0.6)
        ce = np.clip(ce, 88, 99.9)
        
        # 6. 电化学窗口 (V)
        # 取决于电解质稳定性
        base_window = {'氧化物': 5.0, '硫化物': 2.5, '磷酸盐': 5.5,
                       '卤化物': 4.0, '硼氢化物': 3.0, '复合': 4.5}
        esw = base_window[cat] + rng.normal(0, 0.2)
        esw = np.clip(esw, 1.5, 6.0)
        
        records.append({
            '填料类型': filler_name,
            '填料类别': cat,
            '填料含量(wt%)': round(filler_content, 1),
            '比表面积(m²/g)': round(surface_area, 1),
            '粒径(nm)': round(particle_size, 1),
            '基底/聚合物': substrate_name,
            '膜厚度(μm)': round(thickness, 1),
            '温度(°C)': temperature,
            '压力(MPa)': round(pressure, 1),
            '倍率(C)': current_rate,
            '循环次数': cycle_number,
            '离子电导率(mS/cm)': round(ionic_cond, 5),
            '界面阻抗(Ω·cm²)': round(impedance, 1),
            '初始比容量(mAh/g)': round(initial_capacity, 1),
            '容量保持率(%)': round(retention, 1),
            '库伦效率(%)': round(ce, 2),
            '电化学窗口(V)': round(esw, 2),
        })
    
    return pd.DataFrame(records)


def generate_all_data():
    """生成全部数据"""
    liquid_df = generate_liquid_data(650)
    solid_df = generate_solid_data(600)
    return liquid_df, solid_df


if __name__ == '__main__':
    liquid_df, solid_df = generate_all_data()
    print(f"液态电池数据: {len(liquid_df)} 条")
    print(f"固态电池数据: {len(solid_df)} 条")
    print(f"总计: {len(liquid_df) + len(solid_df)} 条")
    liquid_df.to_csv('/share/bf/lis_battery_platform/liquid_data.csv', index=False)
    solid_df.to_csv('/share/bf/lis_battery_platform/solid_data.csv', index=False)
    print("数据已保存")
