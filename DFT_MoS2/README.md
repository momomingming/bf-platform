# MoS₂ DFT 计算系统

## 项目背景

锂硫电池玄武岩纤维(BF)隔膜改性研究 — MoS₂涂层与多硫化锂(LiPS)的相互作用及BF表面(SiO₂)的结合。

## 计算系统总览

| # | 系统 | 目录 | 原子数 | K点 | 说明 |
|---|------|------|--------|-----|------|
| 1 | MoS₂ 体相 | `MoS2_bulk/` | 6 | 6×6×3 | 2H-MoS₂ 体相优化, P6₃/mmc |
| 2 | MoS₂ (001) 基面 | `MoS2_001/` | 54 | 3×3×1 | 3×3超胞, 1层S-Mo-S, 15Å真空 |
| 3 | MoS₂ (100) 边缘 | `MoS2_100/` | 48 | 2×3×1 | 2×1×1超胞, Mo边缘暴露 |
| 4 | (001)+Li₂S | `adsorption/MoS2_001_Li2S/` | 57 | 3×3×1 | Li₂S在基面吸附, h=2.5Å |
| 5 | (001)+Li₂S₄ | `adsorption/MoS2_001_Li2S4/` | 60 | 3×3×1 | Li₂S₄在基面吸附, h=2.8Å |
| 6 | (001)+Li₂S₆ | `adsorption/MoS2_001_Li2S6/` | 62 | 3×3×1 | Li₂S₆在基面吸附, h=3.0Å |
| 7 | (100)+Li₂S | `adsorption/MoS2_100_Li2S/` | 51 | 2×3×1 | Li₂S在边缘吸附, h=2.5Å |
| 8 | (100)+Li₂S₄ | `adsorption/MoS2_100_Li2S4/` | 54 | 2×3×1 | Li₂S₄在边缘吸附, h=2.8Å |
| 9 | (100)+Li₂S₆ | `adsorption/MoS2_100_Li2S6/` | 56 | 2×3×1 | Li₂S₆在边缘吸附, h=3.0Å |
| 10 | MoS₂-SiO₂ 界面 | `MoS2_SiO2_interface/` | 99 | 2×2×1 | MoS₂单层/SiO₂(001), 模拟BF表面 |

## 计算方法

- **软件**: CP2K (Quickstep, GPW)
- **泛函**: PBE + D3(BJ) 色散校正
- **基组**: DZVP-MOLOPT-SR-GTH
- **赝势**: GTH-PBE (Mo: q14, S: q6, Li: q1, Si: q4, O: q6)
- **截断能**: CUTOFF 450 Ry, REL_CUTOFF 60
- **优化**: BFGS, MAX_ITER 300
- **表面计算**: PERIODIC XY, 底部原子固定

## 结构参数

### MoS₂ 体相 (2H, P6₃/mmc)
- a = 3.16 Å, c = 12.30 Å
- Mo: (1/3, 2/3, 1/4), (2/3, 1/3, 3/4)
- S: (2/3, 1/3, 0.13), (1/3, 2/3, 0.37) + 对称等效
- Mo-S 键长: 2.35 Å (已验证)
- 层间距 (S-S vdW gap): 3.68 Å

### 表面模型
- **(001) 基面**: 1层S-Mo-S三层层, 3×3超胞, 底部S层固定
- **(100) 边缘**: 暴露Mo边缘, 2×1×1超胞, 底部原子固定

### 吸附构型
- Li₂S: Li端朝下, 距表面2.5 Å
- Li₂S₄: 链状构型, Li端靠近表面, 2.8 Å
- Li₂S₆: 链状构型, Li端靠近表面, 3.0 Å
- 分子结构来源: `/share/bf/DFT_molecules/`

### MoS₂-SiO₂ 界面
- MoS₂ 3×3 单层 + SiO₂ 2×2×2 (001) 表面
- 晶格匹配: MoS₂ 拉伸 ~3.7% 适配 SiO₂
- 界面间距: 3.0 Å, 真空层: 15 Å
- SiO₂底部固定

## 文件结构

```
DFT_MoS2/
├── README.md
├── submit_all.sh          # 批量提交脚本
├── build_all.py           # 结构构建脚本 (ASE)
├── MoS2_bulk/
│   ├── POSCAR
│   └── input.inp
├── MoS2_001/
│   ├── POSCAR
│   └── input.inp
├── MoS2_100/
│   ├── POSCAR
│   └── input.inp
├── adsorption/
│   ├── MoS2_001_Li2S/     (POSCAR + input.inp)
│   ├── MoS2_001_Li2S4/    (POSCAR + input.inp)
│   ├── MoS2_001_Li2S6/    (POSCAR + input.inp)
│   ├── MoS2_100_Li2S/     (POSCAR + input.inp)
│   ├── MoS2_100_Li2S4/    (POSCAR + input.inp)
│   └── MoS2_100_Li2S6/    (POSCAR + input.inp)
└── MoS2_SiO2_interface/
    ├── POSCAR
    └── input.inp
```

## 提交计算

```bash
# 使用默认参数提交所有计算
bash submit_all.sh

# 指定镜像和机器
bash submit_all.sh registry.dp.tech/dptech/cp2k:2024.1 c32_m128_cpu
```

## 计算流程建议

1. **先优化体相** → 验证晶格参数
2. **切面优化** → (001)和(100)表面弛豫
3. **吸附计算** → 在优化后的表面上放置分子
4. **界面计算** → MoS₂-SiO₂结合能
5. **吸附能计算**: E_ads = E_total - E_surface - E_molecule

## 注意事项

- 所有表面计算使用 PERIODIC XY (z方向非周期)
- 底部原子通过 CONSTRAINT/FIXED_ATOMS 固定
- 多硫化物分子结构来自 `/share/bf/DFT_molecules/`
- MoS₂坐标已校正: S原子在面内相对Mo有偏移, 确保正确的三棱柱配位
