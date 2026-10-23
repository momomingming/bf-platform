# -*- coding: utf-8 -*-
"""
精细化指标计算引擎
==================
设计原则：口径显式化、参数可配置、结果可追溯。

* 口径显式化：每个指标在 METRIC_SPECS 中声明 公式文本 / 单位 / 保留位数 /
  输入字段 / 适用范围 / 版本，UI 与导出文档直接读同一份定义，避免"两套说法"。
* 参数可配置：CalcConfig 承载全部可调参数（标称电压、理论比容量、参考温度、
  活化能、评分权重、分档阈值…），参数的 JSON 快照与哈希写入 metric_runs。
* 结果可追溯：每条结果记录 run_id / params_hash / formula_version / inputs_json
  （参与本次计算的原始输入值），换参数重算会产生新的 run_id，旧结果不被覆盖。
* 精度：统一四舍五入（ROUND_HALF_UP，避开 Python 银行家舍入），
  位数由指标 spec 的 precision 决定，原始浮点不落库，保证"看到的=存下来的"。
"""
from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

import db
from schema import (FIELD_BY_COLUMN, LIQUID, SOLID)

METRIC_VERSION = "v1.0"
K_B_EV = 8.617333262e-5          # 玻尔兹曼常数 eV/K


# ============================================================
# 精度
# ============================================================
def rnd(x, n: int = 4) -> Optional[float]:
    """ROUND_HALF_UP 四舍五入到 n 位小数；NaN/None 原样返回。"""
    if x is None:
        return None
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return float(Decimal(str(float(x))).quantize(Decimal(1).scaleb(-n),
                                                 rounding=ROUND_HALF_UP))


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


# ============================================================
# 可配置参数
# ============================================================
@dataclass
class CalcConfig:
    config_name: str = "默认口径"

    # —— 电化学常数 ——
    nominal_voltage_v: float = 2.1            # 锂硫放电平台标称电压
    theoretical_capacity_mah_g: float = 1675.0  # 硫理论比容量
    ref_temperature_c: float = 25.0           # 电导率归一化参考温度
    activation_energy_ev: float = 0.25        # 单点外推用表观活化能
    gas_constant: float = K_B_EV

    # —— 归一化基准 ——
    conductivity_floor_ms_cm: float = 0.01    # 电导率归一化下限
    conductivity_ceiling_ms_cm: float = 10.0  # 上限
    ce_floor_pct: float = 90.0                # 库伦效率评分下限
    shuttle_ref: float = 0.15                 # 穿梭因子参考值（对应 0 分）
    asr_floor_ohm_cm2: float = 1.0            # 面比电阻评分下限
    asr_ceiling_ohm_cm2: float = 200.0

    # —— 寿命外推 ——
    eol_retention_pct: float = 80.0           # 寿命终止判据
    max_est_cycles: int = 20000               # 外推上限（防止除零/无穷）

    # —— 综合评分权重（会自动归一化到 1）——
    weights: Dict[str, float] = field(default_factory=lambda: {
        "capacity": 0.30, "retention": 0.25, "coulombic": 0.20,
        "conductivity": 0.15, "extra": 0.10,
    })

    # —— 分档阈值（由高到低）——
    retention_grades: Dict[str, float] = field(default_factory=lambda: {
        "A": 90.0, "B": 80.0, "C": 70.0, "D": 60.0,
    })

    def normalized_weights(self) -> Dict[str, float]:
        s = sum(self.weights.values()) or 1.0
        return {k: v / s for k, v in self.weights.items()}

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_dict(cls, d: dict) -> "CalcConfig":
        base = cls()
        for k, v in (d or {}).items():
            if hasattr(base, k):
                setattr(base, k, v)
        return base


# ============================================================
# 指标口径定义
# ============================================================
@dataclass(frozen=True)
class MetricSpec:
    code: str
    name_cn: str
    unit: str
    precision: int
    formula: str
    inputs: tuple
    applies_to: tuple = (LIQUID, SOLID)
    description: str = ""

    @property
    def version(self) -> str:
        return METRIC_VERSION


METRIC_SPECS: List[MetricSpec] = [
    MetricSpec(
        "retained_capacity", "循环后比容量", "mAh/g", 2,
        "初始比容量 × 容量保持率 / 100",
        ("initial_capacity_mah_g", "capacity_retention_pct"),
        description="循环结束时的可逆比容量"),
    MetricSpec(
        "capacity_fade_rate", "容量衰减率", "%/cycle", 4,
        "(100 − 容量保持率) / 循环次数",
        ("capacity_retention_pct", "cycle_count"),
        description="平均每圈容量损失，衡量衰减速度"),
    MetricSpec(
        "cycle_life_est", "寿命外推", "cycles", 0,
        "循环次数 × (100 − EOL保持率) / (100 − 容量保持率)，上限 max_est_cycles",
        ("capacity_retention_pct", "cycle_count"),
        description="线性外推到达 EOL（默认 80%）所需的循环数"),
    MetricSpec(
        "capacity_utilization", "硫利用率", "%", 2,
        "初始比容量 / 理论比容量(1675 mAh/g) × 100",
        ("initial_capacity_mah_g",),
        description="活性物质利用程度"),
    MetricSpec(
        "energy_density", "质量能量密度", "Wh/kg", 2,
        "循环后比容量 × 标称电压(2.1 V) / 1000",
        ("initial_capacity_mah_g", "capacity_retention_pct"),
        description="按循环后容量估算的单质能量密度"),
    MetricSpec(
        "areal_capacity", "面容量", "mAh/cm²", 4,
        "填料负载量(mg/cm²) × 初始比容量(mAh/g) / 1000",
        ("filler_loading_mg_cm2", "initial_capacity_mah_g"),
        applies_to=(LIQUID,),
        description="单位面积可释放容量，液态体系关键工程指标"),
    MetricSpec(
        "asr", "面比电阻", "Ω·cm²", 3,
        "膜厚度(μm) × 0.1 / 离子电导率(mS/cm)",
        ("membrane_thickness_um", "ionic_conductivity_ms_cm"),
        description="由厚度与电导率换算的欧姆内阻贡献"),
    MetricSpec(
        "conductivity_at_ref", "参考温度电导率", "mS/cm", 5,
        "σ × exp(−Ea/kB × (1/Tref − 1/T))，T 单位 K",
        ("ionic_conductivity_ms_cm", "temperature_c"),
        description="按 Arrhenius 关系归一化到 25 °C 的离子电导率"),
    MetricSpec(
        "shuttle_index", "穿梭抑制指数", "-", 2,
        "100 × (1 − min(穿梭因子 / 参考值, 1))，越大越好",
        ("shuttle_factor",),
        applies_to=(LIQUID,),
        description="多硫化物穿梭效应抑制程度"),
    MetricSpec(
        "composite_score", "综合评分", "-", 2,
        "Σ 权重 × 分项得分（容量/保持率/库伦效率/电导率/体系附加项），0~100",
        ("initial_capacity_mah_g", "capacity_retention_pct",
         "coulombic_efficiency_pct", "ionic_conductivity_ms_cm"),
        description="用于材料排序的综合打分"),
]

METRIC_BY_CODE: Dict[str, MetricSpec] = {m.code: m for m in METRIC_SPECS}


def specs_frame():
    rows = []
    for m in METRIC_SPECS:
        rows.append({
            "指标": m.name_cn,
            "编码": m.code,
            "单位": m.unit,
            "精度(小数位)": m.precision,
            "计算口径": m.formula,
            "输入字段": "、".join(FIELD_BY_COLUMN[c].name_cn for c in m.inputs),
            "适用体系": "/".join("液态" if t == LIQUID else "固态" for t in m.applies_to),
            "版本": m.version,
        })
    return pd.DataFrame(rows)


# ============================================================
# 单项计算
# ============================================================
def _arrhenius_to_ref(sigma_ms_cm: float, temp_c: float, cfg: CalcConfig) -> Optional[float]:
    t = temp_c + 273.15
    t_ref = cfg.ref_temperature_c + 273.15
    if t <= 0 or t_ref <= 0 or sigma_ms_cm <= 0:
        return None
    return sigma_ms_cm * math.exp(-cfg.activation_energy_ev / cfg.gas_constant
                                  * (1.0 / t_ref - 1.0 / t))


def _extra_term(row: pd.Series, battery_type: str, cfg: CalcConfig,
                asr: Optional[float]) -> Optional[float]:
    """体系附加项：液态=穿梭抑制指数，固态=面比电阻得分（越小越好）。"""
    if battery_type == LIQUID:
        sf = row.get("shuttle_factor")
        if sf is None or (isinstance(sf, float) and math.isnan(sf)):
            return None
        return 100.0 * (1.0 - _clamp(sf / cfg.shuttle_ref, 0.0, 1.0))
    if asr is None:
        return None
    span = cfg.asr_ceiling_ohm_cm2 - cfg.asr_floor_ohm_cm2
    if span <= 0:
        return None
    return 100.0 * _clamp(1.0 - (asr - cfg.asr_floor_ohm_cm2) / span, 0.0, 1.0)


def compute_row_metrics(row: pd.Series, battery_type: str, cfg: CalcConfig) -> Dict[str, dict]:
    """计算单条样品的全部指标。

    返回 {metric_code: {'value', 'unit', 'precision', 'inputs'}}
    """
    out: Dict[str, dict] = {}
    g = lambda c: row.get(c)          # noqa: E731

    cap0 = g("initial_capacity_mah_g")
    ret = g("capacity_retention_pct")
    ce = g("coulombic_efficiency_pct")
    cond = g("ionic_conductivity_ms_cm")
    thick = g("membrane_thickness_um")
    cycles = g("cycle_count")
    temp = g("temperature_c")

    def put(code, value, inputs):
        spec = METRIC_BY_CODE[code]
        out[code] = {
            "value": rnd(value, spec.precision),
            "unit": spec.unit,
            "precision": spec.precision,
            # 使用本次调用实际传入的 inputs（含体系附加项来源），保证可追溯
            "inputs": {k: (None if _isna(g(k)) else rnd(g(k), 6)) for k in inputs},
        }

    def _isna(x):
        return x is None or (isinstance(x, float) and math.isnan(x))

    # 1. 循环后比容量
    if not _isna(cap0) and not _isna(ret):
        put("retained_capacity", cap0 * ret / 100.0,
            ("initial_capacity_mah_g", "capacity_retention_pct"))

    # 2. 衰减率
    if not _isna(ret) and not _isna(cycles) and cycles and cycles > 0:
        put("capacity_fade_rate", (100.0 - ret) / float(cycles),
            ("capacity_retention_pct", "cycle_count"))

    # 3. 寿命外推
    if not _isna(ret) and not _isna(cycles) and cycles and cycles > 0 and ret < 100:
        est = float(cycles) * (100.0 - cfg.eol_retention_pct) / (100.0 - ret)
        put("cycle_life_est", _clamp(est, 0, cfg.max_est_cycles),
            ("capacity_retention_pct", "cycle_count"))
    elif not _isna(ret) and ret >= 100:
        put("cycle_life_est", float(cfg.max_est_cycles),
            ("capacity_retention_pct", "cycle_count"))

    # 4. 硫利用率
    if not _isna(cap0) and cfg.theoretical_capacity_mah_g > 0:
        put("capacity_utilization", cap0 / cfg.theoretical_capacity_mah_g * 100.0,
            ("initial_capacity_mah_g",))

    # 5. 能量密度（按循环后容量）
    if not _isna(cap0) and not _isna(ret):
        put("energy_density", cap0 * ret / 100.0 * cfg.nominal_voltage_v / 1000.0,
            ("initial_capacity_mah_g", "capacity_retention_pct"))

    # 6. 面容量（液态）
    if battery_type == LIQUID:
        load = g("filler_loading_mg_cm2")
        if not _isna(load) and not _isna(cap0):
            put("areal_capacity", load * cap0 / 1000.0,
                ("filler_loading_mg_cm2", "initial_capacity_mah_g"))

    # 7. 面比电阻
    asr = None
    if not _isna(cond) and not _isna(thick) and cond and cond > 0:
        asr = float(thick) * 0.1 / float(cond)
        put("asr", asr, ("membrane_thickness_um", "ionic_conductivity_ms_cm"))

    # 8. 参考温度电导率
    if not _isna(cond) and not _isna(temp):
        put("conductivity_at_ref", _arrhenius_to_ref(float(cond), float(temp), cfg),
            ("ionic_conductivity_ms_cm", "temperature_c"))

    # 9. 穿梭抑制指数（液态）
    if battery_type == LIQUID and not _isna(g("shuttle_factor")):
        put("shuttle_index", _extra_term(row, LIQUID, cfg, asr), ("shuttle_factor",))

    # 10. 综合评分
    w = cfg.normalized_weights()
    terms: Dict[str, Optional[float]] = {}
    if not _isna(cap0):
        terms["capacity"] = _clamp(cap0 / cfg.theoretical_capacity_mah_g, 0, 1) * 100
    if not _isna(ret):
        terms["retention"] = _clamp(ret, 0, 100)
    if not _isna(ce):
        span = 100.0 - cfg.ce_floor_pct
        terms["coulombic"] = (_clamp((ce - cfg.ce_floor_pct) / span, 0, 1) * 100
                              if span > 0 else None)
    if not _isna(cond) and cond and cond > 0:
        lo, hi = cfg.conductivity_floor_ms_cm, cfg.conductivity_ceiling_ms_cm
        if hi > lo > 0:
            ratio = (math.log10(cond / lo) / math.log10(hi / lo))
            terms["conductivity"] = _clamp(ratio, 0, 1) * 100
    terms["extra"] = _extra_term(row, battery_type, cfg, asr)

    score, weight_sum = 0.0, 0.0
    for k, v in terms.items():
        if v is None:
            continue
        score += v * w.get(k, 0.0)
        weight_sum += w.get(k, 0.0)
    if weight_sum > 0:
        # 综合评分的「体系附加项(extra)」来源也要记录，保证结果完全可追溯：
        # 液态=穿梭因子，固态=面比电阻(由膜厚度与离子电导率推算)。
        extra_inputs = (("shuttle_factor",) if battery_type == LIQUID
                        else ("membrane_thickness_um", "ionic_conductivity_ms_cm"))
        put("composite_score", score / weight_sum,
            ("initial_capacity_mah_g", "capacity_retention_pct",
             "coulombic_efficiency_pct", "ionic_conductivity_ms_cm") + extra_inputs)

    return out


# ============================================================
# 批量计算 + 落库
# ============================================================
def compute_frame(df: pd.DataFrame, battery_type: str, cfg: CalcConfig,
                  progress: Optional[Callable[[str, float, str], None]] = None
                  ) -> pd.DataFrame:
    """对样品 DataFrame 计算全部指标，返回宽表（一行一样品，一列一指标）。"""
    if df is None or df.empty:
        return pd.DataFrame()
    codes = [m.code for m in METRIC_SPECS if battery_type in m.applies_to]
    rows = []
    total = len(df)
    for i, (_, r) in enumerate(df.iterrows()):
        m = compute_row_metrics(r, battery_type, cfg)
        row = {"sample_id": r.get("id")}
        for c in codes:
            row[c] = m.get(c, {}).get("value")
        rows.append(row)
        if progress and (i + 1) % 200 == 0:
            progress("compute", 100 * (i + 1) / total, f"已计算 {i + 1}/{total}")
    return pd.DataFrame(rows)


def run_metrics(df: pd.DataFrame, battery_type: str, cfg: Optional[CalcConfig] = None,
                note: str = "", source_batch_ids: Optional[Sequence[str]] = None,
                run_id: Optional[str] = None, db_path: Optional[str] = None,
                progress: Optional[Callable[[str, float, str], None]] = None
                ) -> Dict[str, object]:
    """执行一次可追溯的指标计算：落 metric_runs + metric_results。

    返回 {'run_id', 'wide', 'params_hash', 'result_count', 'sample_count'}
    """
    cfg = cfg or CalcConfig()
    if df is None or df.empty:
        raise ValueError("没有可计算的样品数据")

    db.init_db(db_path)
    params_hash = db.compute_params_hash(cfg.to_dict())
    run_id = run_id or f"R{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    codes = [m.code for m in METRIC_SPECS if battery_type in m.applies_to]

    db.create_metric_run({
        "run_id": run_id,
        "battery_type": battery_type,
        "config_name": cfg.config_name,
        "params_json": cfg.to_json(),
        "params_hash": params_hash,
        "formula_version": METRIC_VERSION,
        "sample_count": len(df),
        "result_count": 0,
        "metric_codes": ",".join(codes),
        "source_batch_ids": ",".join(source_batch_ids or []),
        "note": note,
    }, db_path=db_path)

    wide_rows, result_rows = [], []
    total = len(df)
    for i, (_, r) in enumerate(df.iterrows()):
        metrics = compute_row_metrics(r, battery_type, cfg)
        row = {"sample_id": r.get("id")}
        for code in codes:
            item = metrics.get(code)
            row[code] = item["value"] if item else None
            if item and item["value"] is not None:
                result_rows.append({
                    "run_id": run_id,
                    "sample_id": r.get("id"),
                    "metric_code": code,
                    "value": item["value"],
                    "unit": item["unit"],
                    "precision": item["precision"],
                    "formula_version": METRIC_VERSION,
                    "params_hash": params_hash,
                    "inputs_json": json.dumps(item["inputs"], ensure_ascii=False),
                    "computed_at": datetime.now().isoformat(timespec="seconds"),
                })
        wide_rows.append(row)
        if progress and (i + 1) % 200 == 0:
            progress("compute", 10 + 80 * (i + 1) / total, f"已计算 {i + 1}/{total}")

    n = db.save_metric_results(result_rows, db_path=db_path)
    _update_run_count(run_id, len(result_rows), db_path)
    if progress:
        progress("compute", 100, f"完成，写入 {n} 条结果")

    return {
        "run_id": run_id,
        "wide": pd.DataFrame(wide_rows),
        "params_hash": params_hash,
        "result_count": n,
        "sample_count": total,
    }


def _update_run_count(run_id: str, n: int, db_path: Optional[str] = None) -> None:
    conn = db.get_connection(db_path)
    with db.transaction(db_path):
        conn.execute("UPDATE metric_runs SET result_count=? WHERE run_id=?", (n, run_id))


# ============================================================
# 批次级附加分析（不写样品级结果）
# ============================================================
def fit_activation_energy(df: pd.DataFrame, group_cols=("filler_type",)) -> pd.DataFrame:
    """按材料分组，用 ln(σ) ~ 1/T 线性拟合表观活化能 Ea (eV)。

    仅当组内温度点数 >= 3 时给出结果，否则返回 NaN（避免两点拟合的假精度）。
    """
    need = {"filler_type", "temperature_c", "ionic_conductivity_ms_cm"}
    if df is None or df.empty or not need.issubset(set(df.columns)):
        return pd.DataFrame(columns=list(group_cols) + ["n_points", "Ea_eV", "R2"])
    rows = []
    for key, grp in df.groupby(list(group_cols), dropna=False):
        g = grp.dropna(subset=["temperature_c", "ionic_conductivity_ms_cm"])
        g = g[g["ionic_conductivity_ms_cm"] > 0]
        if len(g) < 3 or g["temperature_c"].nunique() < 3:
            rows.append({**dict(zip(group_cols, key if isinstance(key, tuple) else (key,))),
                         "n_points": len(g), "Ea_eV": None, "R2": None})
            continue
        t = g["temperature_c"].astype(float).to_numpy() + 273.15
        y = np.log(g["ionic_conductivity_ms_cm"].astype(float).to_numpy())
        x = 1.0 / t
        slope, intercept = np.polyfit(x, y, 1)
        yhat = slope * x + intercept
        ss_res = float(((y - yhat) ** 2).sum())
        ss_tot = float(((y - y.mean()) ** 2).sum())
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        rows.append({**dict(zip(group_cols, key if isinstance(key, tuple) else (key,))),
                     "n_points": len(g),
                     "Ea_eV": rnd(-slope * K_B_EV, 4),
                     "R2": rnd(r2, 4)})
    return pd.DataFrame(rows)


def export_for_modeling(battery_type: str, run_id: Optional[str] = None,
                         db_path: Optional[str] = None):
    """指标回流建模闭环（决策④）。

    把「已入库样品 + 最近一次指标计算结果」合并为建模可用宽表。

    返回 (frame, feature_cols, target_cols)：
      * 基础特征/目标来自 schema 的 LIQUID/SOLID_MODEL_*（中文列）。
      * 追加派生指标（composite_score / areal_capacity / asr / shuttle_index /
        retained_capacity / energy_density / cycle_life_est）作为**额外特征**，
        并把 composite_score 追加为**额外目标**，使"精细化计算"反过来提升预测模型。
    若某体系尚未计算过指标，则退化为纯基础字段（与旧逻辑一致，不报错）。
    """
    import db
    from schema import to_model_frame

    samples = db.fetch_samples(battery_type, db_path=db_path)
    if samples is None or samples.empty:
        return samples, [], []
    frame, feats, tgts = to_model_frame(samples, battery_type)
    frame = frame.copy()
    frame.insert(0, "id", samples["id"].values)

    # 选定该体系最近一次计算 run
    if run_id is None:
        runs = db.list_metric_runs(db_path=db_path, limit=50)
        bt_runs = runs[runs["体系"] == battery_type] if not runs.empty else runs
        run_id = bt_runs.iloc[0]["run_id"] if not bt_runs.empty else None

    derived = []
    if run_id:
        pivot = db.fetch_metric_pivot(run_id, db_path=db_path)
        if not pivot.empty:
            m = pivot.set_index("sample_id")
            candidates = ["composite_score", "areal_capacity", "asr",
                          "shuttle_index", "retained_capacity",
                          "energy_density", "cycle_life_est"]
            for c in candidates:
                if c in m.columns:
                    frame[c] = [m.loc[sid, c] if sid in m.index else None
                                for sid in frame["id"]]
                    derived.append(c)

    feats_out = list(feats) + derived
    tgts_out = list(tgts) + (["composite_score"] if "composite_score" in derived else [])
    return frame, feats_out, tgts_out


def retention_grade(value: Optional[float], cfg: Optional[CalcConfig] = None) -> str:
    cfg = cfg or CalcConfig()
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "-"
    for grade, threshold in sorted(cfg.retention_grades.items(),
                                   key=lambda kv: -kv[1]):
        if value >= threshold:
            return grade
    return "E"
