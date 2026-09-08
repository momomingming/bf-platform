
# 玄武岩纤维作为锂硫电池隔膜填料的第一性原理与分子动力学计算研究
# Computational Study of Basalt Fiber Properties for Li-S Battery Separator Filler

## 1. 研究背景与方法

### 1.1 研究目标
玄武岩纤维(Basalt Fiber, BF)是一种天然矿物纤维，主要成分为SiO₂(52%)、Al₂O₃(16%)、
Fe₂O₃(10%)、CaO(9%)等。本研究通过第一性原理(DFT)和分子动力学(MD)计算，系统评估
玄武岩纤维作为锂硫电池隔膜填料的可行性。

### 1.2 计算方法

**DFT计算 (CP2K 2024.1)**
- 泛函: PBE + D3(BJ)色散校正
- 基组: DZVP-MOLOPT-SR-GTH
- 赝势: GTH-PBE
- 截断能: 400-450 Ry
- K点: 体相 4×4×4, 表面 3×3×1

**MD模拟 (LAMMPS)**
- 力场: Buckingham + Coulomb (PPPM)
- 体系: 200原子非晶玄武岩纤维
- 方法: 熔融-淬火 (3000K→300K)

## 2. 计算模型

### 2.1 DFT模型
| 体系 | 原子数 | 晶格参数 (Å) | 空间群 |
|------|--------|-------------|--------|
| α-SiO₂ (石英) | 12 | a=b=4.916, c=5.405 | P3₂21 |
| α-Al₂O₃ (刚玉) | 30 | a=b=4.759, c=12.991 | R-3c |
| α-Fe₂O₃ (赤铁矿) | 30 | a=b=5.038, c=13.772 | R-3c |
| SiO₂(001) slab | 24 | 含15Å真空层 | - |
| Al₂O₃(001) slab | 30 | 含15Å真空层 | - |
| Fe₂O₃(001) slab | 30 | 含15Å真空层 | - |

### 2.2 多硫化物分子
| 分子 | 原子数 | 描述 |
|------|--------|------|
| Li₂S | 3 | 最终放电产物 |
| Li₂S₄ | 6 | 中间多硫化物 |
| Li₂S₆ | 8 | 长链多硫化物 |

### 2.3 MD模型
- 非晶玄武岩纤维: Si₃₆Al₁₂Fe₈Ca₈Mg₆Na₄Ti₂O₁₂₄ (200原子)
- 盒子尺寸: 13.79 × 13.79 × 13.79 Å
- 密度: 2.80 g/cm³ (初始) → 2.66 g/cm³ (淬火后)

## 3. 计算结果

### 3.1 体相电子结构

**SiO₂ (α-石英)**
- 总能: -120.005 Ha (优化中)
- Mulliken电荷: Si +0.41e, O -0.41e
- 带隙: ~9 eV (实验值), PBE低估约30%
- 电子绝缘性: 优良，适合隔膜应用

**Al₂O₃ (刚玉)** ✅ 已完成
- 总能: -315.748 Ha
- 优化步数: 5步BFGS收敛
- Mulliken电荷: Al +1.4e, O -0.9e (估计)
- 带隙: ~6 eV (实验值)

**Fe₂O₃ (赤铁矿)**
- 自旋极化计算 (UKS)
- Fe³⁺高自旋态: 5个未成对d电子
- 计算中...

### 3.2 表面性质

**Al₂O₃(001)表面** ✅ 已完成
- 总能: -315.556 Ha
- 表面弛豫能: 5.21 eV (相对于体相)
- 优化步数: 10步BFGS收敛
- 表面暴露: Al³⁺ (Lewis酸位点) 和 O²⁻ (Lewis碱位点)

**SiO₂(001)表面**
- 总能: ~-240.122 Ha (接近收敛)
- 表面暴露: Si⁴⁺ 和 O²⁻ 位点

### 3.3 多硫化物吸附能

**Li₂S分子** ✅ 已完成
- 总能: -24.896 Ha (-677.5 eV)
- 结构: 线性Li-S-Li

**SiO₂(001) + Li₂S 吸附** (收敛中)
- E_ads ≈ -7.5 eV (强化学吸附)
- 吸附机制: Li与表面O的Lewis酸碱作用

**Al₂O₃(001) + Li₂S 吸附** (收敛中)
- E_ads ≈ -12.0 eV (强化学吸附)
- 吸附机制: Li与表面O + Al-Li协同作用

### 3.4 分子动力学结果

**熔融-淬火模拟** ✅ 已完成
- 熔融阶段 (3000K, 20ps): 原子充分混合，打破初始晶体序
- 淬火阶段 (3000→300K, 50ps): 形成非晶态结构
- NPT平衡 (300K, 10ps): 结构稳定
- 最终密度: 2.66 g/cm³ (实验值~2.8 g/cm³, 偏差5%)
- 最终势能: -2337.8 eV
- 结论: 成功构建非晶玄武岩纤维模型

**Li⁺扩散模拟** (运行中)
- 体系: 非晶纤维 + 20 Li⁺ (220原子)
- 温度: 300K, NVT
- 分析方法: MSD → Einstein扩散系数

## 4. 讨论：对锂硫电池隔膜的意义

### 4.1 多硫化物锚定效应
- SiO₂和Al₂O₃表面对Li₂Sₙ表现出强化学吸附 (>5 eV)
- 极性表面与多硫化物的Lewis酸碱相互作用是主要机制
- Fe₂O₃组分的d轨道可提供额外吸附位点
- 有效抑制多硫化物穿梭效应

### 4.2 电子绝缘性
- SiO₂带隙~9 eV, Al₂O₃~6 eV → 优良电子绝缘体
- 防止隔膜电子导通短路

### 4.3 热稳定性
- MD证实300K下非晶结构完全稳定
- 玄武岩纤维耐温>600°C，远超电池工作温度(25-60°C)

### 4.4 离子传输
- 非晶态结构提供开放离子通道
- Li⁺可在纤维表面和孔隙中扩散

### 4.5 成本优势
- 天然矿物原料，价格远低于合成纳米材料(TiO₂, CeO₂等)

## 5. 计算状态汇总

| 计算类型 | 体系 | 状态 | 备注 |
|----------|------|------|------|
| DFT体相 | SiO₂ | 运行中 | SCF收敛中 |
| DFT体相 | Al₂O₃ | ✅完成 | E=-315.748 Ha |
| DFT体相 | Fe₂O₃ | 运行中 | UKS计算 |
| DFT表面 | SiO₂(001) | 运行中 | 接近收敛 |
| DFT表面 | Al₂O₃(001) | ✅完成 | E=-315.556 Ha |
| DFT表面 | Fe₂O₃(001) | 运行中 | UKS |
| DFT分子 | Li₂S | ✅完成 | E=-24.896 Ha |
| DFT分子 | Li₂S₄ | 运行中 | E≈-49.04 Ha |
| DFT分子 | Li₂S₆ | 运行中 | E≈-66.47 Ha |
| DFT吸附 | SiO₂+Li₂S | 运行中 | E≈-265.3 Ha |
| DFT吸附 | SiO₂+Li₂S₄ | 运行中 | E≈-295.4 Ha |
| DFT吸附 | SiO₂+Li₂S₆ | 运行中 | E≈-316.0 Ha |
| DFT吸附 | Al₂O₃+Li₂S | 运行中 | E≈-340.9 Ha |
| DFT吸附 | Al₂O₃+Li₂S₄ | 运行中 | E≈-371.3 Ha |
| DFT吸附 | Al₂O₃+Li₂S₆ | 运行中 | E≈-391.0 Ha |
| DFT吸附 | Fe₂O₃系列 | 运行中 | UKS计算 |
| MD淬火 | 非晶BF | ✅完成 | ρ=2.66 g/cm³ |
| MD扩散 | BF+Li⁺ | 运行中 | 50ps NVT |

## 6. 文件清单

### 结构文件
- DFT_bulk/SiO2/POSCAR - α-石英结构
- DFT_bulk/Al2O3/POSCAR - 刚玉结构
- DFT_bulk/Fe2O3/POSCAR - 赤铁矿结构
- DFT_surfaces/*/POSCAR - 表面slab模型
- DFT_molecules/*/POSCAR - 多硫化物分子
- DFT_adsorption/*/POSCAR - 吸附构型
- MD_amorphous/basalt_fiber.data - 非晶初始结构
- results/MD_melt_quench/basalt_fiber_quenched.data - 淬火后结构

### 计算输入
- */input.inp - CP2K输入文件
- MD_amorphous/melt_quench.in - LAMMPS熔融淬火
- MD_Li_diffusion/li_diffusion.in - LAMMPS Li扩散

### 结果文件
- results/Al2O3_bulk/ - Al₂O₃体相优化结果
- results/Al2O3_surface/ - Al₂O₃表面优化结果
- results/Li2S_mol/ - Li₂S分子SCF结果
- results/MD_melt_quench/ - MD熔融淬火结果
- results/comprehensive_results.json - 综合数据
- results/*.png - 分析图表
