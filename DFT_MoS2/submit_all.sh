#!/bin/bash
# =============================================================
# Batch submission script for MoS2 DFT calculations
# Lithium-Sulfur Battery Basalt Fiber (BF) Separator Project
# =============================================================
# Usage: bash submit_all.sh [image] [machine]
# Default image: registry.dp.tech/dptech/cp2k:2024.1
# Default machine: c32_m128_cpu
# =============================================================

set -e

IMAGE="${1:-registry.dp.tech/dptech/cp2k:2024.1}"
MACHINE="${2:-c32_m128_cpu}"
DISK=50

BASEDIR="$(cd "$(dirname "$0")" && pwd)"

# Define all calculation directories
CALC_DIRS=(
    "MoS2_bulk"
    "MoS2_001"
    "MoS2_100"
    "adsorption/MoS2_001_Li2S"
    "adsorption/MoS2_001_Li2S4"
    "adsorption/MoS2_001_Li2S6"
    "adsorption/MoS2_100_Li2S"
    "adsorption/MoS2_100_Li2S4"
    "adsorption/MoS2_100_Li2S6"
    "MoS2_SiO2_interface"
)

echo "============================================================="
echo "MoS2 DFT Calculations - Batch Submission"
echo "============================================================="
echo "Image:   ${IMAGE}"
echo "Machine: ${MACHINE}"
echo "Disk:    ${DISK} GB"
echo "============================================================="
echo ""

JOB_IDS=()

for dir in "${CALC_DIRS[@]}"; do
    full_path="${BASEDIR}/${dir}"
    job_name="MoS2_$(basename ${dir})"

    if [ ! -f "${full_path}/input.inp" ]; then
        echo "[SKIP] ${dir}: input.inp not found"
        continue
    fi

    if [ ! -f "${full_path}/POSCAR" ]; then
        echo "[SKIP] ${dir}: POSCAR not found"
        continue
    fi

    echo "[SUBMIT] ${job_name} (${dir})"

    # Submit via bohr CLI
    JOB_ID=$(bohr job submit \
        --image "${IMAGE}" \
        --machine "${MACHINE}" \
        --disk "${DISK}" \
        --name "${job_name}" \
        --input "${full_path}" \
        --cmd "cp2k.popt -i input.inp -o output.log" \
        2>&1 | grep -oP 'job_id["\s:]+\K\d+' || echo "FAILED")

    if [ "${JOB_ID}" = "FAILED" ]; then
        echo "  [ERROR] Submission failed for ${job_name}"
    else
        echo "  [OK] Job ID: ${JOB_ID}"
        JOB_IDS+=("${JOB_ID}")
    fi
    echo ""
done

echo "============================================================="
echo "Submission Summary"
echo "============================================================="
echo "Total submitted: ${#JOB_IDS[@]} / ${#CALC_DIRS[@]}"
echo "Job IDs: ${JOB_IDS[*]}"
echo ""
echo "Monitor with: bohr job status <job_id>"
echo "============================================================="
