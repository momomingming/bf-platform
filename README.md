# Basalt Fiber / Li-S Battery Interface Study

**玄武岩纤维隔膜填料对锂硫电池多硫化物锚定与Li⁺传输的多尺度计算研究**

Multi-scale computational study of basalt fiber materials as polysulfide anchoring layers and Li⁺ transport media in lithium-sulfur batteries.

---

## 📋 Project Overview

| Category | Method | Software | Systems |
|----------|--------|----------|---------|
| Bulk crystals | DFT (PBE+D3) | CP2K | 3 (Al₂O₃, Fe₂O₃, SiO₂) |
| Surface slabs | DFT (PBE+D3) | CP2K | 4 (001/101 facets) |
| Polysulfide molecules | DFT (PBE) | CP2K | 3 (Li₂S, Li₂S₄, Li₂S₆) |
| Adsorption complexes | DFT (PBE+D3) | CP2K | 9 (3 surfaces × 3 molecules) |
| Amorphous basalt fiber | MD (Buckingham+Coulomb) | LAMMPS | 1 (200 atoms) |
| Li⁺ diffusion | MD (Buckingham+Coulomb) | LAMMPS | 1 (220 atoms, 20 Li⁺) |

**Total: 21 computational systems, 10 elements (Si, Al, Fe, Ca, Mg, Na, Ti, O, Li, S)**

---

## 📁 Directory Structure

```
├── README.md
├── LICENSE
├── .gitignore
│
├── DFT_bulk/                    # Bulk crystal DFT optimization
│   ├── Al2O3/
│   │   ├── POSCAR               # Initial structure (VASP format)
│   │   └── input.inp            # CP2K input file
│   ├── Fe2O3/
│   └── SiO2/
│
├── DFT_surfaces/                # Surface slab DFT models
│   ├── Al2O3_001/
│   ├── Fe2O3_001/
│   ├── SiO2_001/
│   └── SiO2_101/
│
├── DFT_molecules/               # Isolated polysulfide molecules
│   ├── Li2S/
│   ├── Li2S4/
│   └── Li2S6/
│
├── DFT_adsorption/              # Surface-adsorbate complexes (3×3 matrix)
│   ├── Al2O3_Li2S/
│   ├── Al2O3_Li2S4/
│   ├── Al2O3_Li2S6/
│   ├── Fe2O3_Li2S/
│   ├── Fe2O3_Li2S4/
│   ├── Fe2O3_Li2S6/
│   ├── SiO2_Li2S/
│   ├── SiO2_Li2S4/
│   └── SiO2_Li2S6/
│
├── MD_amorphous/                # Melt-quench amorphous basalt fiber
│   ├── melt_quench.in           # LAMMPS input script
│   ├── basalt_fiber.data        # Initial structure (LAMMPS data)
│   ├── basalt_fiber_initial.cif # Initial structure (CIF)
│   └── basalt_fiber_initial.xyz # Initial structure (XYZ)
│
├── MD_Li_diffusion/             # Li⁺ diffusion in basalt fiber matrix
│   ├── li_diffusion.in          # LAMMPS input script
│   └── basalt_Li.data           # Initial structure (220 atoms incl. 20 Li⁺)
│
├── figures/                     # Visualization outputs (15 figures)
│   ├── fig1_bulk_structures.png
│   ├── fig2_surface_structures.png
│   ├── ...
│   └── fig15_bulk_vs_surface.png
│
└── lis_battery_platform/        # Streamlit ML prediction platform
    ├── app.py                   # Main Streamlit application
    ├── generate_data.py         # Data generation module
    ├── modeling.py              # ML modeling (XGBoost, sklearn)
    ├── requirements.txt         # Python dependencies
    ├── liquid_data.csv          # Liquid electrolyte dataset
    └── solid_data.csv           # Solid-state dataset
```

---

## 🔬 Computational Details

### DFT Calculations (CP2K)

- **Functional:** PBE + D3(BJ) dispersion correction
- **Basis set:** DZVP-MOLOPT-SR-GTH
- **Method:** GPW (Gaussian and Plane Waves), cutoff 400–450 Ry
- **Pseudopotentials:** GTH
- **k-points:** Γ-centered 3×3×1 (surfaces), 2×2×1 (adsorption)
- **Geometry optimization:** BFGS algorithm
- **Molecules:** Non-periodic (Poisson solver: WAVELET), OT minimizer

### MD Simulations (LAMMPS)

- **Potential:** Buckingham + Coulomb (PPPM for long-range)
- **Melt-quench protocol:** 300K → 3000K (20 ps) → 300K (50 ps quench) → NPT relaxation (10 ps)
- **Li⁺ diffusion:** NVT 300K, 10 ps equilibration + 50 ps production
- **Basalt fiber composition:** Si₃₆Al₁₂Fe₈Ca₈Mg₆Na₄Ti₂O₁₂₄ (200 atoms)

---

## 📊 Visualization Gallery

| Figure | Description |
|--------|-------------|
| fig1 | Bulk crystal structures (Al₂O₃, Fe₂O₃, SiO₂) |
| fig2 | Surface slab models with vacuum layers |
| fig3 | Polysulfide molecules (Li₂S, Li₂S₄, Li₂S₆) |
| fig4 | Adsorption configuration matrix (3×3) |
| fig5 | MD initial structures (amorphous + Li diffusion) |
| fig6 | System statistics overview (6-panel) |
| fig7 | Research workflow diagram |
| fig8 | Composition pie charts (6 categories) |
| fig9 | Cell parameter & adsorption size heatmaps |
| fig10 | MD system composition analysis |
| fig11 | Adsorption interaction analysis |
| fig12 | MD simulation protocol timelines |
| fig13 | Surface properties & cost estimation |
| fig14 | Structural analysis (RDF, coordination) |
| fig15 | Bulk → surface slab comparison |

---

## 🖥️ Web Platform (Streamlit)

The `lis_battery_platform/` directory contains an interactive ML-based prediction platform for Li-S battery separator material design.

### Quick Start

```bash
cd lis_battery_platform
pip install -r requirements.txt
streamlit run app.py
```

### Features
- Separate models for liquid and solid-state electrolyte systems
- XGBoost + scikit-learn ensemble predictions
- Feature importance analysis
- Interactive Plotly visualizations

---

## 🚀 How to Use

### Running DFT Calculations (CP2K)

```bash
cd DFT_bulk/Al2O3
cp2k.popt input.inp > Al2O3.out 2>&1
```

### Running MD Simulations (LAMMPS)

```bash
cd MD_amorphous
lmp < melt_quench.in > melt_quench.log 2>&1
```

---

## 📄 License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

---

## 📝 Citation

If you use this work, please cite:

```
Basalt Fiber / Li-S Battery Interface Multi-Scale Study, 2026.
Computational investigation of basalt fiber as polysulfide anchoring
material for lithium-sulfur battery separators.
```
