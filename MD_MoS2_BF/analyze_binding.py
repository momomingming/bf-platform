#!/usr/bin/env python3
"""
Analyze MoS2-BF binding energy from LAMMPS log files.

Reads log files from three simulations:
  - system 0: MoS2 + BF combined
  - system 1: BF only
  - system 2: MoS2 only

Computes: E_bind = E(MoS2+BF) - E(MoS2) - E(BF)
Generates: energy vs. time plots and binding energy summary.

Usage:
  python3 analyze_binding.py [log_dir]

Default log_dir is the current directory.
"""

import os
import sys
import re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

# ============================================================
# Configuration
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = sys.argv[1] if len(sys.argv) > 1 else SCRIPT_DIR

# Log file names for the three systems
LOG_FILES = {
    0: os.path.join(LOG_DIR, 'log.lammps'),        # combined (default name)
    1: os.path.join(LOG_DIR, 'log_bf.lammps'),      # BF only
    2: os.path.join(LOG_DIR, 'log_mos2.lammps'),     # MoS2 only
}

# Alternative naming: log_system0.lammps, etc.
ALT_LOG_FILES = {
    0: os.path.join(LOG_DIR, 'log_system0.lammps'),
    1: os.path.join(LOG_DIR, 'log_system1.lammps'),
    2: os.path.join(LOG_DIR, 'log_system2.lammps'),
}

# Also check for single log with all runs
SINGLE_LOG = os.path.join(LOG_DIR, 'log.lammps')

# ============================================================
# LAMMPS log parser
# ============================================================
def parse_lammps_log(filepath):
    """Parse a LAMMPS log file and extract thermo data.

    Returns dict with keys: 'step', 'temp', 'pe', 'ke', 'etotal',
    'press', 'vol', 'density', plus 'sections' (list of dicts per run).
    """
    if not os.path.exists(filepath):
        return None

    with open(filepath, 'r') as f:
        lines = f.readlines()

    sections = []
    current_header = None
    current_data = []

    for line in lines:
        stripped = line.strip()

        # Detect thermo header line
        if stripped.startswith('Step') and 'Temp' in stripped:
            if current_header and current_data:
                sections.append({
                    'header': current_header,
                    'data': np.array(current_data)
                })
            current_header = stripped.split()
            current_data = []
            continue

        # Detect end of thermo block
        if stripped.startswith('Loop time') or stripped.startswith('WARNING'):
            if current_header and current_data:
                sections.append({
                    'header': current_header,
                    'data': np.array(current_data)
                })
                current_header = None
                current_data = []
            continue

        # Parse data lines
        if current_header is not None:
            parts = stripped.split()
            if len(parts) == len(current_header):
                try:
                    row = [float(x) for x in parts]
                    current_data.append(row)
                except ValueError:
                    pass

    # Capture last section
    if current_header and current_data:
        sections.append({
            'header': current_header,
            'data': np.array(current_data)
        })

    return sections


def extract_energies(sections):
    """Extract step and PE from the last (production) section."""
    if not sections:
        return None, None, None

    # Use the last section (production run)
    last = sections[-1]
    header = last['header']
    data = last['data']

    step_idx = header.index('Step')
    pe_idx = header.index('PotEng')
    temp_idx = header.index('Temp') if 'Temp' in header else None

    steps = data[:, step_idx]
    pe = data[:, pe_idx]
    temp = data[:, temp_idx] if temp_idx is not None else None

    return steps, pe, temp


def get_final_energy(sections):
    """Get the average PE from the last 20% of the production run."""
    if not sections:
        return np.nan

    last = sections[-1]
    header = last['header']
    data = last['data']

    pe_idx = header.index('PotEng')
    pe = data[:, pe_idx]

    # Average over last 20% of production
    n = len(pe)
    start = int(0.8 * n)
    return np.mean(pe[start:])


# ============================================================
# Main analysis
# ============================================================
def main():
    print("=" * 60)
    print("  MoS2-BF Binding Energy Analysis")
    print("=" * 60)

    # Find log files
    logs = {}
    for sys_id in [0, 1, 2]:
        path = LOG_FILES[sys_id]
        if os.path.exists(path):
            logs[sys_id] = path
        elif os.path.exists(ALT_LOG_FILES[sys_id]):
            logs[sys_id] = ALT_LOG_FILES[sys_id]

    # If individual logs not found, try parsing single log
    if len(logs) < 3 and os.path.exists(SINGLE_LOG):
        print(f"\nNote: Found single log file: {SINGLE_LOG}")
        print("Expecting 3 separate log files for systems 0, 1, 2.")
        print("If you ran all 3 cases in sequence, the log may contain all runs.")

    if len(logs) < 3:
        print(f"\nWarning: Found {len(logs)}/3 log files.")
        print("Expected files:")
        for sys_id, name in LOG_FILES.items():
            status = "FOUND" if sys_id in logs else "MISSING"
            print(f"  [{status}] {name}")
        print(f"\nAlternative naming:")
        for sys_id, name in ALT_LOG_FILES.items():
            status = "FOUND" if os.path.exists(name) else "MISSING"
            print(f"  [{status}] {name}")

        if len(logs) == 0:
            print("\nNo log files found. Run the simulations first.")
            sys.exit(1)

    # Parse each log
    results = {}
    labels = {0: 'MoS2+BF (combined)', 1: 'BF only', 2: 'MoS2 only'}

    for sys_id, path in sorted(logs.items()):
        print(f"\nParsing: {path}")
        sections = parse_lammps_log(path)
        if sections:
            steps, pe, temp = extract_energies(sections)
            e_avg = get_final_energy(sections)
            results[sys_id] = {
                'steps': steps,
                'pe': pe,
                'temp': temp,
                'e_avg': e_avg,
                'e_final': pe[-1] if pe is not None else np.nan,
                'n_sections': len(sections),
            }
            print(f"  Sections: {len(sections)}")
            print(f"  Production steps: {len(pe) if pe is not None else 0}")
            print(f"  Final PE: {e_avg:.2f} kcal/mol (avg last 20%)")
        else:
            print(f"  ERROR: Could not parse {path}")

    # ============================================================
    # Calculate binding energy
    # ============================================================
    print("\n" + "=" * 60)
    print("  Binding Energy Results")
    print("=" * 60)

    if all(i in results for i in [0, 1, 2]):
        E_combined = results[0]['e_avg']
        E_bf = results[1]['e_avg']
        E_mos2 = results[2]['e_avg']
        E_bind = E_combined - E_bf - E_mos2

        print(f"\n  E(MoS2+BF) = {E_combined:>14.2f} kcal/mol")
        print(f"  E(BF)      = {E_bf:>14.2f} kcal/mol")
        print(f"  E(MoS2)    = {E_mos2:>14.2f} kcal/mol")
        print(f"  ─────────────────────────────────────")
        print(f"  E_bind     = {E_bind:>14.2f} kcal/mol")
        print(f"             = {E_bind / 23.0605:>14.4f} eV")

        # Per-atom binding energy
        n_mos2_atoms = 54
        e_bind_per_atom = E_bind / n_mos2_atoms
        print(f"  E_bind/atom = {e_bind_per_atom:>13.4f} kcal/mol  (per MoS2 atom)")

        # Convert to common units
        print(f"\n  Unit conversions:")
        print(f"    {E_bind:.2f} kcal/mol = {E_bind * 4.184:.2f} kJ/mol")
        print(f"    {E_bind:.2f} kcal/mol = {E_bind / 23.0605:.4f} eV")
        print(f"    {E_bind:.2f} kcal/mol = {E_bind * 6.9477e-21:.4e} J")

        # Save results to file
        results_file = os.path.join(SCRIPT_DIR, 'binding_energy_results.txt')
        with open(results_file, 'w') as f:
            f.write("# MoS2-BF Binding Energy Results\n")
            f.write(f"# Generated from LAMMPS log files in {LOG_DIR}\n\n")
            f.write(f"E_combined  = {E_combined:.6f}  # kcal/mol\n")
            f.write(f"E_BF        = {E_bf:.6f}  # kcal/mol\n")
            f.write(f"E_MoS2      = {E_mos2:.6f}  # kcal/mol\n")
            f.write(f"E_bind      = {E_bind:.6f}  # kcal/mol\n")
            f.write(f"E_bind_eV   = {E_bind / 23.0605:.6f}  # eV\n")
            f.write(f"E_bind_kJ   = {E_bind * 4.184:.6f}  # kJ/mol\n")
        print(f"\n  Results saved to: {results_file}")

    else:
        print("\n  Cannot compute binding energy: missing simulation data.")
        print("  Run all 3 systems first:")
        print("    lmp -v system 0 -in MoS2_BF_binding.in")
        print("    lmp -v system 1 -in MoS2_BF_binding.in")
        print("    lmp -v system 2 -in MoS2_BF_binding.in")

    # ============================================================
    # Plot energy vs. time
    # ============================================================
    fig, axes = plt.subplots(2, 1, figsize=(10, 8), gridspec_kw={'height_ratios': [2, 1]})

    colors = {0: '#2196F3', 1: '#FF9800', 2: '#4CAF50'}
    labels_short = {0: 'MoS₂+BF', 1: 'BF only', 2: 'MoS₂ only'}

    # --- Panel 1: PE vs time ---
    ax1 = axes[0]
    for sys_id in sorted(results.keys()):
        r = results[sys_id]
        if r['steps'] is not None and r['pe'] is not None:
            # Convert steps to time (ps): metal units, dt=0.001 ps
            time_ps = r['steps'] * 0.001
            ax1.plot(time_ps, r['pe'], color=colors[sys_id],
                     label=labels_short[sys_id], linewidth=0.8, alpha=0.9)

    ax1.set_xlabel('Time (ps)', fontsize=12)
    ax1.set_ylabel('Potential Energy (kcal/mol)', fontsize=12)
    ax1.set_title('MoS₂-BF Binding Energy: Potential Energy vs. Time', fontsize=13)
    ax1.legend(fontsize=11, loc='best')
    ax1.grid(True, alpha=0.3)

    # Add binding energy annotation if available
    if all(i in results for i in [0, 1, 2]):
        E_bind_val = results[0]['e_avg'] - results[1]['e_avg'] - results[2]['e_avg']
        ax1.annotate(
            f'$E_{{bind}}$ = {E_bind_val:.2f} kcal/mol\n'
            f'= {E_bind_val/23.0605:.4f} eV',
            xy=(0.98, 0.95), xycoords='axes fraction',
            horizontalalignment='right', verticalalignment='top',
            fontsize=11,
            bbox=dict(boxstyle='round,pad=0.5', facecolor='lightyellow', alpha=0.8),
        )

    # --- Panel 2: Temperature vs time ---
    ax2 = axes[1]
    for sys_id in sorted(results.keys()):
        r = results[sys_id]
        if r['steps'] is not None and r['temp'] is not None:
            time_ps = r['steps'] * 0.001
            ax2.plot(time_ps, r['temp'], color=colors[sys_id],
                     label=labels_short[sys_id], linewidth=0.5, alpha=0.7)

    ax2.set_xlabel('Time (ps)', fontsize=12)
    ax2.set_ylabel('Temperature (K)', fontsize=12)
    ax2.set_title('Temperature', fontsize=12)
    ax2.axhline(y=300, color='red', linestyle='--', alpha=0.5, label='Target 300K')
    ax2.legend(fontsize=10, loc='best')
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    fig_path = os.path.join(SCRIPT_DIR, 'binding_energy_plot.png')
    plt.savefig(fig_path, dpi=150, bbox_inches='tight')
    print(f"\n  Plot saved to: {fig_path}")
    plt.close()

    # ============================================================
    # Plot binding energy convergence
    # ============================================================
    if all(i in results for i in [0, 1, 2]):
        fig2, ax3 = plt.subplots(figsize=(10, 5))

        r0, r1, r2 = results[0], results[1], results[2]
        # Use the minimum length across all three
        n_min = min(len(r0['pe']), len(r1['pe']), len(r2['pe']))
        steps = r0['steps'][:n_min]
        time_ps = steps * 0.001

        # Running binding energy
        e_bind_running = r0['pe'][:n_min] - r1['pe'][:n_min] - r2['pe'][:n_min]

        ax3.plot(time_ps, e_bind_running, 'b-', linewidth=0.8, alpha=0.6,
                 label='$E_{bind}$(t) instantaneous')

        # Running average
        window = max(1, n_min // 50)
        e_bind_avg = np.convolve(e_bind_running, np.ones(window)/window, mode='valid')
        time_avg = time_ps[window-1:]
        ax3.plot(time_avg, e_bind_avg, 'r-', linewidth=2.0,
                 label=f'$E_{{bind}}$ running avg (window={window})')

        ax3.axhline(y=E_bind, color='green', linestyle='--', linewidth=1.5,
                     label=f'Final avg: {E_bind:.2f} kcal/mol')
        ax3.set_xlabel('Time (ps)', fontsize=12)
        ax3.set_ylabel('Binding Energy (kcal/mol)', fontsize=12)
        ax3.set_title('MoS₂-BF Binding Energy Convergence', fontsize=13)
        ax3.legend(fontsize=11)
        ax3.grid(True, alpha=0.3)

        plt.tight_layout()
        conv_path = os.path.join(SCRIPT_DIR, 'binding_energy_convergence.png')
        plt.savefig(conv_path, dpi=150, bbox_inches='tight')
        print(f"  Convergence plot saved to: {conv_path}")
        plt.close()

    print("\n" + "=" * 60)
    print("  Analysis complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
