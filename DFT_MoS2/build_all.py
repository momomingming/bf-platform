#!/usr/bin/env python3
"""Build all MoS2 DFT calculation structures and CP2K input files.
Corrected version: proper layer counts, surface normals, and CP2K syntax."""
import os
import numpy as np
from ase import Atoms
from ase.io import read, write
from ase.build import surface, make_supercell

BASE = '/share/bf/DFT_MoS2'
MOL_DIR = '/share/bf/DFT_molecules'

# ======================== Utility Functions ========================

def build_mos2_bulk():
    """Build 2H-MoS2 bulk unit cell (P63/mmc)."""
    a, c = 3.16, 12.30
    cell = np.array([
        [a, 0, 0],
        [-a/2, a*np.sqrt(3)/2, 0],
        [0, 0, c]
    ])
    # Fractional positions for 2H-MoS2 (P63/mmc)
    # S atoms offset in-plane from Mo for correct trigonal prismatic coordination
    # All Mo-S distances ~2.35 A (verified)
    frac = [
        (1/3, 2/3, 0.25, 'Mo'),
        (2/3, 1/3, 0.75, 'Mo'),
        (2/3, 1/3, 0.13, 'S'),   # bottom S of trilayer 1
        (1/3, 2/3, 0.63, 'S'),   # symmetry equiv
        (2/3, 1/3, 0.37, 'S'),   # top S of trilayer 1
        (1/3, 2/3, 0.87, 'S'),   # symmetry equiv
    ]
    pos, sym = [], []
    for fx, fy, fz, s in frac:
        cart = fx*cell[0] + fy*cell[1] + fz*cell[2]
        pos.append(cart); sym.append(s)
    return Atoms(symbols=sym, positions=pos, cell=cell, pbc=True)


def atoms_to_coord_lines(atoms):
    """Convert ASE Atoms to COORD lines."""
    lines = []
    for sym, p in zip(atoms.get_chemical_symbols(), atoms.get_positions()):
        lines.append(f"{sym:4s} {p[0]:16.10f} {p[1]:16.10f} {p[2]:16.10f}")
    return lines


def get_kinds(elements):
    """Return KIND definitions for given elements."""
    kind_map = {
        'Mo': ('Mo', 'Mo', 'DZVP-MOLOPT-SR-GTH', 'GTH-PBE-q14'),
        'S':  ('S',  'S',  'DZVP-MOLOPT-SR-GTH', 'GTH-PBE-q6'),
        'Li': ('Li', 'Li', 'DZVP-MOLOPT-SR-GTH', 'GTH-PBE-q1'),
        'Si': ('Si', 'Si', 'DZVP-MOLOPT-SR-GTH', 'GTH-PBE-q4'),
        'O':  ('O',  'O',  'DZVP-MOLOPT-SR-GTH', 'GTH-PBE-q6'),
    }
    return [kind_map[el] for el in sorted(set(elements)) if el in kind_map]


def write_poscar(atoms, filepath):
    """Write POSCAR."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    write(filepath, atoms, format='vasp', direct=True, sort=True)
    print(f"  Written: {filepath}")


def write_cp2k_input(filepath, project, run_type, cell, coord_lines, kinds,
                     kpoints, periodic='XYZ', fixed_indices=None):
    """Generate CP2K input file with correct syntax."""
    a1, a2, a3 = cell[0]
    b1, b2, b3 = cell[1]
    c1, c2, c3 = cell[2]

    kind_sec = ""
    for kn, el, basis, pot in kinds:
        kind_sec += f"""    &KIND {kn}
      ELEMENT {el}
      BASIS_SET {basis}
      POTENTIAL {pot}
    &END KIND
"""
    coord_sec = "\n".join([f"      {l}" for l in coord_lines])

    # Motion section with constraint
    motion_sec = ""
    if run_type == 'GEO_OPT':
        fixed_sec = ""
        if fixed_indices and len(fixed_indices) > 0:
            idx_str = " ".join([str(i+1) for i in sorted(fixed_indices)])
            fixed_sec = f"""    &CONSTRAINT
      &FIXED_ATOMS
        LIST {idx_str}
      &END FIXED_ATOMS
    &END CONSTRAINT"""

        motion_sec = f"""
&MOTION
  &GEO_OPT
    OPTIMIZER BFGS
    MAX_ITER 300
    MAX_DR 3.0E-3
    MAX_FORCE 4.5E-4
    RMS_DR 1.5E-3
    RMS_FORCE 3.0E-4
  &END GEO_OPT
{fixed_sec}
  &PRINT
    &TRAJECTORY
      &EACH
        GEO_OPT 1
      &END EACH
    &END TRAJECTORY
  &END PRINT
&END MOTION"""

    content = f"""&GLOBAL
  PROJECT {project}
  RUN_TYPE {run_type}
  PRINT_LEVEL MEDIUM
&END GLOBAL

&FORCE_EVAL
  METHOD Quickstep
  &DFT
    BASIS_SET_FILE_NAME BASIS_MOLOPT
    POTENTIAL_FILE_NAME GTH_POTENTIALS

    &MGRID
      CUTOFF 450
      REL_CUTOFF 60
    &END MGRID
    &QS
      METHOD GPW
      EPS_DEFAULT 1.0E-12
    &END QS
    &SCF
      SCF_GUESS ATOMIC
      EPS_SCF 1.0E-6
      MAX_SCF 100
      MAX_DIIS 7
      &DIAGONALIZATION
        ALGORITHM STANDARD
      &END DIAGONALIZATION
      &MIXING
        METHOD BROYDEN_MIXING
        ALPHA 0.4
        NBROYDEN 8
      &END MIXING
    &END SCF
    &XC
      &XC_FUNCTIONAL PBE
      &END XC_FUNCTIONAL
      &VDW_POTENTIAL
        POTENTIAL_TYPE PAIR_POTENTIAL
        &PAIR_POTENTIAL
          PARAMETER_FILE_NAME dftd3.dat
          TYPE DFTD3(BJ)
          REFERENCE_FUNCTIONAL PBE
        &END PAIR_POTENTIAL
      &END VDW_POTENTIAL
    &END XC
    &KPOINTS
      SCHEME MONKHORST-PACK {kpoints[0]} {kpoints[1]} {kpoints[2]}
    &END KPOINTS
  &END DFT
  &SUBSYS
    &CELL
      A  {a1:16.10f} {a2:16.10f} {a3:16.10f}
      B  {b1:16.10f} {b2:16.10f} {b3:16.10f}
      C  {c1:16.10f} {c2:16.10f} {c3:16.10f}
      PERIODIC {periodic}
    &END CELL
    &COORD
{coord_sec}
    &END COORD
{kind_sec}  &END SUBSYS
&END FORCE_EVAL
{motion_sec}
"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        f.write(content)
    print(f"  Written: {filepath}")


# ======================== 1. MoS2 Bulk ========================
def build_bulk():
    print("\n=== 1. MoS2 Bulk ===")
    d = f'{BASE}/MoS2_bulk'
    os.makedirs(d, exist_ok=True)

    bulk = build_mos2_bulk()
    write_poscar(bulk, f'{d}/POSCAR')
    write_cp2k_input(f'{d}/input.inp', 'MoS2_bulk_opt', 'GEO_OPT',
                     bulk.cell[:], atoms_to_coord_lines(bulk),
                     get_kinds(['Mo', 'S']), [6, 6, 3], 'XYZ')
    print(f"  {len(bulk)} atoms, a=3.16, c=12.30")
    return bulk


# ======================== 2. MoS2 (001) Surface ========================
def build_001(bulk_atoms):
    print("\n=== 2. MoS2 (001) Basal Surface ===")
    d = f'{BASE}/MoS2_001'
    os.makedirs(d, exist_ok=True)

    # 1 S-Mo-S trilayer, surface normal along z
    slab = surface(bulk_atoms, (0, 0, 1), layers=1, vacuum=7.5)
    slab_sc = make_supercell(slab, [[3, 0, 0], [0, 3, 0], [0, 0, 1]])

    # Ensure exactly 15 Å vacuum
    pos = slab_sc.get_positions().copy()
    z_min, z_max = pos[:, 2].min(), pos[:, 2].max()
    slab_thick = z_max - z_min
    new_c = slab_thick + 15.0

    # Center slab in cell
    cell = slab_sc.cell[:].copy()
    cell[2] = [0, 0, new_c]
    shift = new_c / 2 - (z_max + z_min) / 2
    pos[:, 2] += shift
    slab_sc.set_positions(pos)
    slab_sc.set_cell(cell, scale_atoms=False)

    # Fix bottom 1/3 of atoms (bottom S layer of the trilayer)
    pos = slab_sc.get_positions()
    z_sorted = np.sort(pos[:, 2])
    z_threshold = z_sorted[0] + slab_thick * 0.33 + 0.3
    fixed = [i for i, z in enumerate(pos[:, 2]) if z < z_threshold]

    print(f"  {len(slab_sc)} atoms, {len(fixed)} fixed")
    print(f"  Cell: {cell[0][0]:.2f} x {cell[1][1]:.2f} x {cell[2][2]:.2f} Å")
    print(f"  Slab: {slab_thick:.2f} Å, Vacuum: {new_c - slab_thick:.2f} Å")

    write_poscar(slab_sc, f'{d}/POSCAR')
    write_cp2k_input(f'{d}/input.inp', 'MoS2_001_surf', 'GEO_OPT',
                     cell, atoms_to_coord_lines(slab_sc),
                     get_kinds(['Mo', 'S']), [3, 3, 1], 'XY', fixed)
    return slab_sc, fixed


# ======================== 3. MoS2 (100) Edge Surface ========================
def build_100(bulk_atoms):
    print("\n=== 3. MoS2 (100) Edge Surface ===")
    d = f'{BASE}/MoS2_100'
    os.makedirs(d, exist_ok=True)

    # ASE (100) surface: x along a, y along c, z = surface normal
    slab = surface(bulk_atoms, (1, 0, 0), layers=4, vacuum=7.5)

    # Supercell: 2x1x1 → 48 atoms (in range 40-60)
    slab_sc = make_supercell(slab, [[2, 0, 0], [0, 1, 0], [0, 0, 1]])

    # Ensure 15 Å vacuum in z (surface normal direction)
    pos = slab_sc.get_positions().copy()
    z_min, z_max = pos[:, 2].min(), pos[:, 2].max()
    slab_thick_z = z_max - z_min
    new_c = slab_thick_z + 15.0

    cell = slab_sc.cell[:].copy()
    cell[2] = [0, 0, new_c]
    shift = new_c / 2 - (z_max + z_min) / 2
    pos[:, 2] += shift
    slab_sc.set_positions(pos)
    slab_sc.set_cell(cell, scale_atoms=False)

    # Fix bottom layer (lowest z atoms)
    pos = slab_sc.get_positions()
    z_sorted = np.sort(pos[:, 2])
    z_threshold = z_sorted[0] + slab_thick_z * 0.25 + 0.3
    fixed = [i for i, z in enumerate(pos[:, 2]) if z < z_threshold]

    print(f"  {len(slab_sc)} atoms, {len(fixed)} fixed")
    print(f"  Cell: {cell[0][0]:.2f} x {cell[1][1]:.2f} x {cell[2][2]:.2f} Å")
    print(f"  Slab(z): {slab_thick_z:.2f} Å, Vacuum: {new_c - slab_thick_z:.2f} Å")

    write_poscar(slab_sc, f'{d}/POSCAR')
    write_cp2k_input(f'{d}/input.inp', 'MoS2_100_edge', 'GEO_OPT',
                     cell, atoms_to_coord_lines(slab_sc),
                     get_kinds(['Mo', 'S']), [2, 3, 1], 'XY', fixed)
    return slab_sc, fixed


# ======================== 4. Adsorption Systems ========================
def load_molecule(name):
    """Load molecule POSCAR and center at origin."""
    mol = read(f'{MOL_DIR}/{name}/POSCAR', format='vasp')
    mol.positions -= mol.get_center_of_mass()
    return mol


def build_adsorption(slab, fixed, mol_name, mol, surf_tag, height, orient, kpoints):
    """Place molecule on surface and write files."""
    d = f'{BASE}/adsorption/MoS2_{surf_tag}_{mol_name}'
    os.makedirs(d, exist_ok=True)

    slab_pos = slab.get_positions()
    slab_cell = slab.cell[:].copy()
    z_top = slab_pos[:, 2].max()

    # Orient molecule
    mol_pos = mol.get_positions().copy()
    mol_sym = mol.get_chemical_symbols()

    if orient == 'li_down':
        # Li atoms at bottom (closest to surface)
        li_z = [mol_pos[i, 2] for i, s in enumerate(mol_sym) if s == 'Li']
        if li_z:
            mol_pos[:, 2] -= min(li_z)
    elif orient == 'chain':
        # Chain config: Li end near surface
        li_z = [mol_pos[i, 2] for i, s in enumerate(mol_sym) if s == 'Li']
        if li_z:
            mol_pos[:, 2] -= min(li_z)

    # Place above surface
    mol_pos[:, 2] += z_top + height

    # Center molecule in xy over slab center
    slab_center_x = (slab_cell[0][0] + slab_cell[1][0]) / 2
    slab_center_y = (slab_cell[0][1] + slab_cell[1][1]) / 2
    mol_cx = (mol_pos[:, 0].max() + mol_pos[:, 0].min()) / 2
    mol_cy = (mol_pos[:, 1].max() + mol_pos[:, 1].min()) / 2
    mol_pos[:, 0] += slab_center_x - mol_cx
    mol_pos[:, 1] += slab_center_y - mol_cy

    # Combine
    all_sym = list(slab.get_chemical_symbols()) + mol_sym
    all_pos = np.vstack([slab_pos, mol_pos])
    combined = Atoms(symbols=all_sym, positions=all_pos,
                     cell=slab_cell, pbc=[True, True, False])

    # Adjust cell height if molecule extends too high
    z_all_max = all_pos[:, 2].max()
    current_c = slab_cell[2][2]
    if z_all_max + 5.0 > current_c:
        new_c = z_all_max + 10.0
        slab_cell[2] = [0, 0, new_c]
        combined.set_cell(slab_cell, scale_atoms=False)

    project = f'MoS2_{surf_tag}_{mol_name}_ads'
    write_poscar(combined, f'{d}/POSCAR')
    write_cp2k_input(f'{d}/input.inp', project, 'GEO_OPT',
                     combined.cell[:], atoms_to_coord_lines(combined),
                     get_kinds(all_sym), kpoints, 'XY', fixed)
    print(f"  {project}: {len(combined)} atoms, height={height} Å")
    return combined


def build_all_adsorption(slab_001, fixed_001, slab_100, fixed_100):
    print("\n=== 4. Adsorption Systems ===")
    os.makedirs(f'{BASE}/adsorption', exist_ok=True)

    mols = {
        'Li2S':  (load_molecule('Li2S'),  'li_down', 2.5),
        'Li2S4': (load_molecule('Li2S4'), 'chain',   2.8),
        'Li2S6': (load_molecule('Li2S6'), 'chain',   3.0),
    }

    for mol_name, (mol, orient, h) in mols.items():
        build_adsorption(slab_001, fixed_001, mol_name, mol, '001', h, orient, [3, 3, 1])
        build_adsorption(slab_100, fixed_100, mol_name, mol, '100', h, orient, [2, 3, 1])


# ======================== 5. MoS2-SiO2 Interface ========================
def build_interface():
    print("\n=== 5. MoS2-SiO2 Interface ===")
    d = f'{BASE}/MoS2_SiO2_interface'
    os.makedirs(d, exist_ok=True)

    # --- MoS2 monolayer (single S-Mo-S trilayer) ---
    a_mos2 = 3.16
    cell_m = np.array([[a_mos2, 0, 0],
                       [-a_mos2/2, a_mos2*np.sqrt(3)/2, 0],
                       [0, 0, 25.0]])
    frac_m = [
        (2/3, 1/3, 0.5 - 0.12, 'S'),   # bottom S (offset from Mo in-plane)
        (1/3, 2/3, 0.5, 'Mo'),
        (2/3, 1/3, 0.5 + 0.12, 'S'),   # top S (offset from Mo in-plane)
    ]
    pos_m, sym_m = [], []
    for fx, fy, fz, s in frac_m:
        pos_m.append(fx*cell_m[0] + fy*cell_m[1] + fz*cell_m[2])
        sym_m.append(s)
    monolayer = Atoms(symbols=sym_m, positions=pos_m, cell=cell_m, pbc=True)
    mono_sc = make_supercell(monolayer, [[3, 0, 0], [0, 3, 0], [0, 0, 1]])

    # --- SiO2 (001) slab (alpha-quartz, 2 trilayers) ---
    a_sio2, c_sio2 = 4.916, 5.405
    cell_s = np.array([[a_sio2, 0, 0],
                       [-a_sio2/2, a_sio2*np.sqrt(3)/2, 0],
                       [0, 0, c_sio2]])
    # Alpha-quartz fractional coords (one layer)
    si_frac = [(0.0, 0.0, 0.0), (0.5, 0.0, 0.333), (0.0, 0.5, 0.667)]
    o_frac = [(0.206, 0.0, 0.083), (0.794, 0.206, 0.083), (0.0, 0.794, 0.083),
              (0.294, 0.5, 0.417), (0.706, 0.794, 0.417), (0.5, 0.294, 0.417)]
    pos_s, sym_s = [], []
    for fx, fy, fz in si_frac:
        pos_s.append(fx*cell_s[0] + fy*cell_s[1] + fz*cell_s[2]); sym_s.append('Si')
    for fx, fy, fz in o_frac:
        pos_s.append(fx*cell_s[0] + fy*cell_s[1] + fz*cell_s[2]); sym_s.append('O')
    sio2 = Atoms(symbols=sym_s, positions=pos_s, cell=cell_s, pbc=True)
    sio2_sc = make_supercell(sio2, [[2, 0, 0], [0, 2, 0], [0, 0, 2]])

    # --- Match cells ---
    # MoS2 3x3: a_vec = [9.48, 0], b_vec = [-4.74, 8.21]
    # SiO2 2x2: a_vec = [9.832, 0], b_vec = [-4.916, 8.514]
    # Use SiO2 cell as reference (BF surface is larger/rigid)
    ref_cell = sio2_sc.cell[:].copy()

    # Scale MoS2 to match SiO2 in-plane
    mono_pos = mono_sc.get_positions().copy()
    mono_cell = mono_sc.cell[:].copy()
    scale_x = ref_cell[0][0] / mono_cell[0][0]
    scale_y = ref_cell[1][1] / mono_cell[1][1]
    mono_pos[:, 0] *= scale_x
    mono_pos[:, 1] *= scale_y

    # Compute dimensions
    sio2_pos = sio2_sc.get_positions()
    sio2_zmin, sio2_zmax = sio2_pos[:, 2].min(), sio2_pos[:, 2].max()
    sio2_thick = sio2_zmax - sio2_zmin

    mono_pos_z = mono_pos[:, 2]
    mono_zmin, mono_zmax = mono_pos_z.min(), mono_pos_z.max()
    mono_thick = mono_zmax - mono_zmin

    gap = 3.0  # interface gap
    vacuum = 15.0
    total_c = sio2_thick + gap + mono_thick + vacuum + 2.0  # extra margin

    # Build interface cell
    iface_cell = [ref_cell[0].tolist(), ref_cell[1].tolist(), [0, 0, total_c]]

    # Place SiO2 at bottom
    sio2_shifted = sio2_pos.copy()
    sio2_shifted[:, 2] -= sio2_zmin
    sio2_shifted[:, 2] += 1.0  # 1 Å from bottom

    # Place MoS2 on top
    mono_shifted = mono_pos.copy()
    mono_shifted[:, 2] -= mono_zmin
    mono_shifted[:, 2] += 1.0 + sio2_thick + gap

    # Combine
    all_sym = list(sio2_sc.get_chemical_symbols()) + list(mono_sc.get_chemical_symbols())
    all_pos = np.vstack([sio2_shifted, mono_shifted])
    iface = Atoms(symbols=all_sym, positions=all_pos, cell=iface_cell, pbc=[True, True, False])

    # Fix SiO2 bottom half
    z_all = iface.get_positions()[:, 2]
    z_mid = 1.0 + sio2_thick * 0.5
    fixed = [i for i, z in enumerate(z_all) if z < z_mid]

    print(f"  {len(iface)} atoms (SiO2: {len(sio2_sc)}, MoS2: {len(mono_sc)})")
    print(f"  Cell: {iface_cell[0][0]:.2f} x {iface_cell[1][1]:.2f} x {iface_cell[2][2]:.2f} Å")
    print(f"  Fixed (SiO2 bottom): {len(fixed)} atoms")
    print(f"  MoS2 strain: x={scale_x:.3f}, y={scale_y:.3f}")

    write_poscar(iface, f'{d}/POSCAR')
    write_cp2k_input(f'{d}/input.inp', 'MoS2_SiO2_interface', 'GEO_OPT',
                     iface_cell, atoms_to_coord_lines(iface),
                     get_kinds(['Mo', 'S', 'Si', 'O']), [2, 2, 1], 'XY', fixed)
    return iface


# ======================== Main ========================
if __name__ == '__main__':
    print("=" * 60)
    print("MoS2 DFT Calculation Systems - Corrected Build")
    print("=" * 60)

    os.makedirs(BASE, exist_ok=True)

    bulk = build_bulk()
    slab_001, fixed_001 = build_001(bulk)
    slab_100, fixed_100 = build_100(bulk)
    build_all_adsorption(slab_001, fixed_001, slab_100, fixed_100)
    build_interface()

    print("\n" + "=" * 60)
    print("All structures and input files created!")
    print("=" * 60)
