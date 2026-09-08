#!/usr/bin/env python3
"""
Generate MoS2 nanoflake and combined MoS2+BF LAMMPS data files.

MoS2: 3x3 supercell of single-layer 2H-MoS2 (54 atoms)
BF:   Read from existing basalt_fiber.data (201 atoms)
Combined: MoS2 placed 3.0 A above BF surface
"""

import numpy as np
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BF_DATA_FILE = os.path.join(os.path.dirname(SCRIPT_DIR), 'MD_amorphous', 'basalt_fiber.data')

# ============================================================
# Read basalt fiber data file
# ============================================================
bf_atoms = []
bf_box = {}

with open(BF_DATA_FILE, 'r') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    parts = line.split()
    if len(parts) >= 2:
        if parts[1] == 'atoms':
            bf_natoms = int(parts[0])
        elif parts[1] == 'types':
            bf_ntypes = int(parts[0])
        elif len(parts) >= 4 and parts[2] == 'xlo' and parts[3] == 'xhi':
            bf_box['xlo'], bf_box['xhi'] = float(parts[0]), float(parts[1])
        elif len(parts) >= 4 and parts[2] == 'ylo' and parts[3] == 'yhi':
            bf_box['ylo'], bf_box['yhi'] = float(parts[0]), float(parts[1])
        elif len(parts) >= 4 and parts[2] == 'zlo' and parts[3] == 'zhi':
            bf_box['zlo'], bf_box['zhi'] = float(parts[0]), float(parts[1])

in_atoms = False
for line in lines:
    stripped = line.strip()
    if stripped.startswith('Atoms'):
        in_atoms = True
        continue
    if in_atoms and stripped == '':
        continue
    if in_atoms:
        parts = stripped.split()
        if len(parts) >= 4:
            try:
                aid = int(parts[0])
                atype = int(parts[1])
                x, y, z = float(parts[2]), float(parts[3]), float(parts[4])
                bf_atoms.append((aid, atype, x, y, z))
            except (ValueError, IndexError):
                in_atoms = False

n_bf = len(bf_atoms)
print(f"Read {n_bf} BF atoms from {BF_DATA_FILE}")
print(f"BF box: x=[{bf_box['xlo']:.4f}, {bf_box['xhi']:.4f}], "
      f"y=[{bf_box['ylo']:.4f}, {bf_box['yhi']:.4f}], "
      f"z=[{bf_box['zlo']:.4f}, {bf_box['zhi']:.4f}]")

# BF atom type mapping (by count analysis):
# Type 1: Si (36), Type 2: Al (12), Type 3: Fe (8), Type 4: Ca (8),
# Type 5: Mg (6), Type 6: Na (4), Type 7: O (126+1outlier), Type 9: Ti (1)

# ============================================================
# Build 2H-MoS2 3x3 supercell (single layer)
# ============================================================
a_mos2 = 3.16   # lattice constant (Angstrom)
dz_MS = 1.58    # Mo-S layer half-spacing

# Hexagonal lattice vectors
a1 = np.array([a_mos2, 0.0])
a2 = np.array([a_mos2 * 0.5, a_mos2 * np.sqrt(3) / 2])

nx, ny = 3, 3
mos2_atoms = []

for ix in range(nx):
    for iy in range(ny):
        R = ix * a1 + iy * a2
        # 2H-MoS2 single-layer basis (6 atoms per hexagonal unit cell):
        # Mo1 at (0, 0, 0)
        mos2_atoms.append(('Mo', R[0], R[1], 0.0))
        # Mo2 at (1/3, 2/3, 0)
        p = R + (1.0/3)*a1 + (2.0/3)*a2
        mos2_atoms.append(('Mo', p[0], p[1], 0.0))
        # S1 at (1/3, 2/3, +dz)  — above Mo1
        p = R + (1.0/3)*a1 + (2.0/3)*a2
        mos2_atoms.append(('S', p[0], p[1], dz_MS))
        # S2 at (2/3, 1/3, -dz)  — below Mo1
        p = R + (2.0/3)*a1 + (1.0/3)*a2
        mos2_atoms.append(('S', p[0], p[1], -dz_MS))
        # S3 at (0, 0, +dz)  — above Mo2 (in-plane at Mo1 site)
        mos2_atoms.append(('S', R[0], R[1], dz_MS))
        # S4 at (0, 0, -dz)  — below Mo2 (in-plane at Mo1 site)
        mos2_atoms.append(('S', R[0], R[1], -dz_MS))

n_mos2 = len(mos2_atoms)
n_mo = sum(1 for a in mos2_atoms if a[0] == 'Mo')
n_s = sum(1 for a in mos2_atoms if a[0] == 'S')
print(f"\nMoS2 nanoflake: {n_mos2} atoms ({n_mo} Mo + {n_s} S)")

# MoS2 bounding box
mos2_x = [a[1] for a in mos2_atoms]
mos2_y = [a[2] for a in mos2_atoms]
mos2_size_x = max(mos2_x) - min(mos2_x)
mos2_size_y = max(mos2_y) - min(mos2_y)
print(f"MoS2 size: {mos2_size_x:.2f} x {mos2_size_y:.2f} Angstrom")

# ============================================================
# Position MoS2 above BF surface
# ============================================================
bf_xlo, bf_xhi = bf_box['xlo'], bf_box['xhi']
bf_ylo, bf_yhi = bf_box['ylo'], bf_box['yhi']
bf_zhi = bf_box['zhi']

bf_cx = (bf_xlo + bf_xhi) / 2
bf_cy = (bf_ylo + bf_yhi) / 2

# Center MoS2 in BF box (xy)
mos2_cx = (max(mos2_x) + min(mos2_x)) / 2
mos2_cy = (max(mos2_y) + min(mos2_y)) / 2
offset_x = bf_cx - mos2_cx
offset_y = bf_cy - mos2_cy

# MoS2 above BF: gap = 3.0 A from BF box top
gap = 3.0
z_mos2_base = bf_zhi + gap + dz_MS  # Mo layer z-position

print(f"\nPositioning MoS2: offset=({offset_x:.2f}, {offset_y:.2f}), z_Mo={z_mos2_base:.2f} A")

# Build positioned MoS2 atoms (element, x, y, z)
mos2_positioned = []
for elem, mx, my, mz in mos2_atoms:
    x = mx + offset_x
    y = my + offset_y
    z = mz + z_mos2_base
    mos2_positioned.append((elem, x, y, z))

# ============================================================
# Compute combined box dimensions
# ============================================================
all_x = [a[2] for a in bf_atoms] + [a[1] for a in mos2_positioned]
all_y = [a[3] for a in bf_atoms] + [a[2] for a in mos2_positioned]
all_z = [a[4] for a in bf_atoms] + [a[3] for a in mos2_positioned]

vacuum = 10.0
xlo, xhi = bf_xlo, bf_xhi
ylo, yhi = bf_ylo, bf_yhi
zlo = min(min(all_z), 0.0) - 2.0
zhi = max(all_z) + vacuum

print(f"\nCombined box: x=[{xlo:.4f}, {xhi:.4f}]")
print(f"              y=[{ylo:.4f}, {yhi:.4f}]")
print(f"              z=[{zlo:.4f}, {zhi:.4f}]")

# ============================================================
# Atom type mapping for combined system
# ============================================================
# BF types (from data file): 1=Si, 2=Al, 3=Fe, 4=Ca, 5=Mg, 6=Na, 7=O, 9=Ti
# New types: 10=Mo, 11=S
TOTAL_TYPES = 11

# Masses (amu)
masses = {
    1: 28.085,   # Si
    2: 26.982,   # Al
    3: 55.845,   # Fe
    4: 40.078,   # Ca
    5: 24.305,   # Mg
    6: 22.990,   # Na
    7: 15.999,   # O
    8: 15.999,   # (unused placeholder)
    9: 47.867,   # Ti
    10: 95.950,  # Mo
    11: 32.065,  # S
}

elem_to_type = {'Mo': 10, 'S': 11}

# ============================================================
# Write MoS2-only data file
# ============================================================
mos2_file = os.path.join(SCRIPT_DIR, 'MoS2_nanoflake.data')
with open(mos2_file, 'w') as f:
    f.write("MoS2 nanoflake - 3x3 supercell single-layer 2H-MoS2\n\n")
    f.write(f"{n_mos2} atoms\n")
    f.write(f"{TOTAL_TYPES} atom types\n\n")
    f.write(f"0.0  {bf_xhi - bf_xlo:.10f}  xlo xhi\n")
    f.write(f"0.0  {bf_yhi - bf_ylo:.10f}  ylo yhi\n")
    f.write(f"-5.0  10.0  zlo zhi\n\n")
    f.write("Masses\n\n")
    for t in range(1, TOTAL_TYPES + 1):
        f.write(f"  {t}  {masses[t]:.3f}\n")
    f.write("\nAtoms # charge\n\n")
    for i, (elem, mx, my, mz) in enumerate(mos2_atoms):
        atype = elem_to_type[elem]
        # Center MoS2 in its own box
        cx = mx - mos2_cx + (bf_xhi - bf_xlo) / 2
        cy = my - mos2_cy + (bf_yhi - bf_ylo) / 2
        cz = mz
        f.write(f"  {i+1}  {atype}  {cx:.10f}  {cy:.10f}  {cz:.10f}\n")

print(f"\nWrote MoS2 nanoflake: {mos2_file}")

# ============================================================
# Write combined MoS2+BF data file
# ============================================================
combined_file = os.path.join(SCRIPT_DIR, 'MoS2_BF_combined.data')
total_atoms = n_bf + n_mos2

with open(combined_file, 'w') as f:
    f.write("MoS2 + Basalt Fiber combined system\n")
    f.write("MoS2 nanoflake on BF surface, 3.0 A initial gap\n\n")
    f.write(f"{total_atoms} atoms\n")
    f.write(f"{TOTAL_TYPES} atom types\n\n")
    f.write(f"{xlo:.10f}  {xhi:.10f}  xlo xhi\n")
    f.write(f"{ylo:.10f}  {yhi:.10f}  ylo yhi\n")
    f.write(f"{zlo:.10f}  {zhi:.10f}  zlo zhi\n\n")
    f.write("Masses\n\n")
    for t in range(1, TOTAL_TYPES + 1):
        f.write(f"  {t}  {masses[t]:.3f}\n")
    f.write("\nAtoms # charge\n\n")

    # BF atoms first (preserve original IDs and types)
    for aid, atype, x, y, z in bf_atoms:
        f.write(f"  {aid}  {atype}  {x:.10f}  {y:.10f}  {z:.10f}\n")

    # MoS2 atoms (IDs continue from n_bf+1)
    for i, (elem, x, y, z) in enumerate(mos2_positioned):
        new_id = n_bf + i + 1
        atype = elem_to_type[elem]
        f.write(f"  {new_id}  {atype}  {x:.10f}  {y:.10f}  {z:.10f}\n")

print(f"Wrote combined system: {combined_file}")
print(f"  Total: {total_atoms} atoms ({n_bf} BF + {n_mos2} MoS2)")
print(f"  BF atoms: IDs 1-{n_bf}")
print(f"  MoS2 atoms: IDs {n_bf+1}-{total_atoms}")
print("\nDone!")
