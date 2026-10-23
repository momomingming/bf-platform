# -*- coding: utf-8 -*-
"""
数据字段模型（单一事实来源）
============================
import / 计算 / 存储 三个环节共用同一份字段定义，避免"导入认一套列名、
计算认另一套、数据库再认第三套"导致的数据不一致。

设计要点
--------
1. 中文字段名（业务/Excel 表头）→ 英文 snake_case 列名（SQLite 列）唯一映射。
2. 每个字段声明：类型、单位、量纲范围、是否必填、枚举白名单、所属电池体系。
3. 别名表 ALIASES 吸收常见表头写法差异（全半角、空格、单位括号、英译）。
4. 校验分两级：ERROR（拒收整行）/ WARN（入库但记录，供人工复核）。
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

LIQUID = "liquid"
SOLID = "solid"
BATTERY_TYPES = (LIQUID, SOLID)

BATTERY_TYPE_CN = {LIQUID: "液态锂硫电池", SOLID: "固态锂硫电池"}

# 体系判定关键字：导入未知来源文件时用于自动判别电池体系
LIQUID_HINTS = ("隔膜厚度", "孔隙率", "电解液体系", "穿梭因子", "填料负载量")
SOLID_HINTS = ("膜厚度", "压力(MPa)", "电化学窗口", "界面阻抗", "填料含量")


@dataclass(frozen=True)
class FieldSpec:
    """单个字段的规格定义。"""
    column: str                       # 数据库英文列名
    name_cn: str                      # 标准中文表头（平台内部与建模模块共用）
    kind: str                         # text | float | int
    unit: str = ""
    required: bool = False
    applies_to: Tuple[str, ...] = (LIQUID, SOLID)
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    enum: Tuple[str, ...] = ()
    precision: int = 4                # 入库保留小数位
    description: str = ""

    def for_battery(self, battery_type: str) -> bool:
        return battery_type in self.applies_to


def _f(column, name_cn, unit="", **kw) -> FieldSpec:
    return FieldSpec(column=column, name_cn=name_cn, kind="float", unit=unit, **kw)


def _t(column, name_cn, **kw) -> FieldSpec:
    return FieldSpec(column=column, name_cn=name_cn, kind="text", **kw)


def _i(column, name_cn, unit="", **kw) -> FieldSpec:
    return FieldSpec(column=column, name_cn=name_cn, kind="int", unit=unit, **kw)


# ============================================================
# 字段总表（顺序即导入模板列顺序）
# ============================================================
FIELD_SPECS: List[FieldSpec] = [
    # ---- 结构/材料描述 ----
    _t("filler_type", "填料类型", required=True,
       description="隔膜/电解质填料主成分，如 MnO2 / rGO / Li7P3S11"),
    # 枚举取值取自平台历史数据集（liquid/solid_data.csv）的实际分布，
    # 不在表内时只告警不拒收（WARN），避免新增材料类别卡住导入。
    _t("filler_category", "填料类别",
       enum=("金属氧化物", "氧化物", "碳基", "硫化物", "金属硫化物", "卤化物",
             "磷酸盐", "硼氢化物", "聚合物", "MOF/COF", "氮化物", "复合", "其他"),
       description="填料所属大类，用于分组统计与类别编码"),
    # 液态：负载量 mg/cm²；固态：含量 wt%
    _f("filler_loading_mg_cm2", "填料负载量(mg/cm²)", "mg/cm²",
       applies_to=(LIQUID,), minimum=0, maximum=50,
       description="单位面积活性物质/填料涂覆量"),
    _f("filler_content_wt", "填料含量(wt%)", "wt%",
       applies_to=(SOLID,), minimum=0, maximum=100,
       description="填料在复合电解质中的质量分数"),
    _f("specific_surface_area_m2_g", "比表面积(m²/g)", "m²/g",
       minimum=0, maximum=5000,
       description="BET 比表面积，影响多硫化物吸附位点密度"),
    _f("particle_size_nm", "粒径(nm)", "nm",
       minimum=0.1, maximum=200000,
       description="填料一次粒子粒径"),
    _f("pore_volume_cm3_g", "孔体积(cm³/g)", "cm³/g",
       applies_to=(LIQUID,), minimum=0, maximum=10,
       description="孔容，影响电解液浸润与多硫化物限域"),
    _t("substrate", "基底材料", applies_to=(LIQUID,),
       description="液态体系隔膜基底，如 GF/A、Celgard、Whatman GF/D"),
    _t("polymer", "基底/聚合物", applies_to=(SOLID,),
       description="固态体系聚合物基体，如 PEO、PVDF-HFP、PAN"),
    _f("membrane_thickness_um", "膜厚度(μm)", "μm",
       minimum=1, maximum=3000,
       description="隔膜 / 电解质膜厚度（液态表头常写作『隔膜厚度(μm)』）"),
    _f("porosity", "孔隙率", "-",
       applies_to=(LIQUID,), minimum=0, maximum=1,
       description="隔膜孔隙率（0~1 小数）"),
    _t("electrolyte", "电解液体系", applies_to=(LIQUID,),
       description="如 DOL/DME + 1M LiTFSI + 0.2M LiNO3"),

    # ---- 测试工况 ----
    _f("temperature_c", "温度(°C)", "°C", minimum=-60, maximum=200),
    _f("pressure_mpa", "压力(MPa)", "MPa",
       applies_to=(SOLID,), minimum=0, maximum=1000),
    _f("c_rate", "倍率(C)", "C", minimum=0.01, maximum=20),
    _i("cycle_count", "循环次数", "次", minimum=0, maximum=200000),

    # ---- 性能目标 ----
    _f("ionic_conductivity_ms_cm", "离子电导率(mS/cm)", "mS/cm",
       minimum=1e-6, maximum=1000),
    _f("interfacial_resistance_ohm_cm2", "界面阻抗(Ω·cm²)", "Ω·cm²",
       applies_to=(SOLID,), minimum=0, maximum=100000),
    _f("initial_capacity_mah_g", "初始比容量(mAh/g)", "mAh/g",
       minimum=0, maximum=2500),
    _f("capacity_retention_pct", "容量保持率(%)", "%", minimum=0, maximum=100),
    _f("coulombic_efficiency_pct", "库伦效率(%)", "%", minimum=0, maximum=100),
    _f("shuttle_factor", "穿梭因子", "-",
       applies_to=(LIQUID,), minimum=0, maximum=1),
    _f("electrochemical_window_v", "电化学窗口(V)", "V",
       applies_to=(SOLID,), minimum=0, maximum=8),
]

FIELD_BY_COLUMN: Dict[str, FieldSpec] = {s.column: s for s in FIELD_SPECS}
FIELD_BY_CN: Dict[str, FieldSpec] = {s.name_cn: s for s in FIELD_SPECS}

# 参与内容哈希（去重）的字段：材料 + 结构 + 工况 + 全部性能目标
HASH_COLUMNS: Tuple[str, ...] = tuple(s.column for s in FIELD_SPECS)

# 数值字段（计算与统计用）
NUMERIC_COLUMNS: Tuple[str, ...] = tuple(
    s.column for s in FIELD_SPECS if s.kind in ("float", "int")
)
TEXT_COLUMNS: Tuple[str, ...] = tuple(s.column for s in FIELD_SPECS if s.kind == "text")

# 建模模块（modeling.py）使用的中文特征/目标列，用于导入数据与模型对齐
LIQUID_MODEL_FEATURES = [
    "填料类型", "填料类别", "填料负载量(mg/cm²)", "比表面积(m²/g)", "粒径(nm)",
    "孔体积(cm³/g)", "基底材料", "隔膜厚度(μm)", "孔隙率", "电解液体系",
    "温度(°C)", "倍率(C)", "循环次数",
]
LIQUID_MODEL_TARGETS = [
    "离子电导率(mS/cm)", "初始比容量(mAh/g)", "容量保持率(%)", "库伦效率(%)", "穿梭因子",
]
SOLID_MODEL_FEATURES = [
    "填料类型", "填料类别", "填料含量(wt%)", "比表面积(m²/g)", "粒径(nm)",
    "基底/聚合物", "膜厚度(μm)", "温度(°C)", "压力(MPa)", "倍率(C)", "循环次数",
]
SOLID_MODEL_TARGETS = [
    "离子电导率(mS/cm)", "界面阻抗(Ω·cm²)", "初始比容量(mAh/g)",
    "容量保持率(%)", "库伦效率(%)", "电化学窗口(V)",
]


# ============================================================
# 表头归一化与别名
# ============================================================
ALIASES: Dict[str, str] = {
    # 填料
    "filler": "filler_type", "filler type": "filler_type", "填料": "filler_type",
    "填料名称": "filler_type", "材料": "filler_type", "材料名称": "filler_type",
    "filler category": "filler_category", "类别": "filler_category",
    "填料分类": "filler_category", "材料类别": "filler_category",
    # 负载 / 含量
    "填料负载量": "filler_loading_mg_cm2", "负载量": "filler_loading_mg_cm2",
    "areal loading": "filler_loading_mg_cm2", "loading": "filler_loading_mg_cm2",
    "填料含量": "filler_content_wt", "含量": "filler_content_wt",
    "filler content": "filler_content_wt",
    # 结构
    "比表面积": "specific_surface_area_m2_g", "bet": "specific_surface_area_m2_g",
    "surface area": "specific_surface_area_m2_g", "ssa": "specific_surface_area_m2_g",
    "粒径": "particle_size_nm", "particle size": "particle_size_nm",
    "孔体积": "pore_volume_cm3_g", "孔容": "pore_volume_cm3_g",
    "pore volume": "pore_volume_cm3_g",
    "基底材料": "substrate", "隔膜基底": "substrate", "substrate": "substrate",
    "基底/聚合物": "polymer", "聚合物": "polymer", "polymer": "polymer",
    "基体": "polymer",
    "膜厚度": "membrane_thickness_um", "隔膜厚度": "membrane_thickness_um",
    "厚度": "membrane_thickness_um", "thickness": "membrane_thickness_um",
    "孔隙率": "porosity", "porosity": "porosity",
    "电解液体系": "electrolyte", "电解液": "electrolyte", "electrolyte": "electrolyte",
    # 工况
    "温度": "temperature_c", "temperature": "temperature_c", "temp": "temperature_c",
    "压力": "pressure_mpa", "pressure": "pressure_mpa", "stack pressure": "pressure_mpa",
    "倍率": "c_rate", "c rate": "c_rate", "current rate": "c_rate",
    "循环次数": "cycle_count", "cycles": "cycle_count", "循环": "cycle_count",
    # 性能
    "离子电导率": "ionic_conductivity_ms_cm", "电导率": "ionic_conductivity_ms_cm",
    "conductivity": "ionic_conductivity_ms_cm",
    "界面阻抗": "interfacial_resistance_ohm_cm2", "阻抗": "interfacial_resistance_ohm_cm2",
    "resistance": "interfacial_resistance_ohm_cm2",
    "初始比容量": "initial_capacity_mah_g", "比容量": "initial_capacity_mah_g",
    "capacity": "initial_capacity_mah_g",
    "容量保持率": "capacity_retention_pct", "retention": "capacity_retention_pct",
    "库伦效率": "coulombic_efficiency_pct", "库仑效率": "coulombic_efficiency_pct",
    "ce": "coulombic_efficiency_pct",
    "穿梭因子": "shuttle_factor", "shuttle": "shuttle_factor",
    "电化学窗口": "electrochemical_window_v", "窗口": "electrochemical_window_v",
    "window": "electrochemical_window_v",
}


def normalize_header(name: str) -> str:
    """表头归一化：全角转半角 → 去空白/下划线 → 去单位括号 → 小写。"""
    if name is None:
        return ""
    s = unicodedata.normalize("NFKC", str(name)).strip()
    s = re.sub(r"[\s_]+", "", s)
    s = re.sub(r"[（(\[【].*?[)）\]】]", "", s)   # 去掉 (m²/g) 之类的单位
    s = s.replace("·", "").replace("°", "").replace("％", "%")
    return s.lower()


def map_columns(headers: Sequence[str]) -> Tuple[Dict[str, str], List[str]]:
    """把原始表头映射到标准英文列名。

    返回 (映射 orig_header -> column, 未识别表头列表)
    """
    mapping: Dict[str, str] = {}
    unknown: List[str] = []
    for h in headers:
        key = normalize_header(h)
        col = None
        if key in ALIASES:
            col = ALIASES[key]
        else:
            # 直接用标准中文名归一化后比对
            for spec in FIELD_SPECS:
                if key == normalize_header(spec.name_cn):
                    col = spec.column
                    break
        if col:
            mapping[h] = col
        else:
            unknown.append(h)
    return mapping, unknown


# ============================================================
# 取值校验
# ============================================================
@dataclass
class ValidationIssue:
    row_no: int                       # 1-based 数据行号（不含表头）
    column: str                       # 标准英文列名，整行级错误记为 "*"
    code: str                         # 机器可读错误码
    message: str                      # 面向用户的中文提示
    value: object = None
    severity: str = "ERROR"           # ERROR | WARN

    def as_dict(self) -> dict:
        return {
            "row_no": self.row_no,
            "column": self.column,
            "code": self.code,
            "message": self.message,
            "value": ("" if self.value is None else str(self.value)),
            "severity": self.severity,
        }


def coerce_value(spec: FieldSpec, raw, row_no: int) -> Tuple[object, List[ValidationIssue]]:
    """把原始值转换成标准类型，返回 (值, 问题列表)。"""
    issues: List[ValidationIssue] = []
    col = spec.column

    if raw is None or (isinstance(raw, float) and np_is_nan(raw)) or (
        isinstance(raw, str) and raw.strip() in ("", "-", "—", "NA", "N/A", "nan", "None")
    ):
        if spec.required:
            issues.append(ValidationIssue(
                row_no, col, "MISSING_REQUIRED",
                f"必填字段「{spec.name_cn}」为空", None, "ERROR"))
            return None, issues
        return None, issues

    if spec.kind == "text":
        val = str(raw).strip()
        if spec.enum and val not in spec.enum:
            issues.append(ValidationIssue(
                row_no, col, "ENUM_OUT_OF_RANGE",
                f"「{spec.name_cn}」取值「{val}」不在标准枚举 {list(spec.enum)} 内",
                val, "WARN"))
        return val, issues

    # 数值型
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        num = float(raw)
    else:
        text = str(raw).strip().replace(",", "")
        try:
            num = float(text)
        except ValueError:
            issues.append(ValidationIssue(
                row_no, col, "TYPE_NOT_NUMERIC",
                f"「{spec.name_cn}」应为数值，实际为「{raw}」", raw, "ERROR"))
            return None, issues

    if spec.kind == "int":
        if abs(num - round(num)) > 1e-9:
            issues.append(ValidationIssue(
                row_no, col, "TYPE_NOT_INT",
                f"「{spec.name_cn}」应为整数，实际为「{raw}」", raw, "ERROR"))
            return None, issues
        num = int(round(num))

    if spec.minimum is not None and num < spec.minimum:
        issues.append(ValidationIssue(
            row_no, col, "BELOW_MIN",
            f"「{spec.name_cn}」= {num}{spec.unit} 低于下限 {spec.minimum}{spec.unit}",
            raw, "ERROR"))
        return None, issues
    if spec.maximum is not None and num > spec.maximum:
        issues.append(ValidationIssue(
            row_no, col, "ABOVE_MAX",
            f"「{spec.name_cn}」= {num}{spec.unit} 超出上限 {spec.maximum}{spec.unit}",
            raw, "ERROR"))
        return None, issues

    return (num if spec.kind == "float" else int(num)), issues


def np_is_nan(x) -> bool:
    try:
        return x != x          # NaN 唯一不等于自身的性质，避免强依赖 numpy
    except Exception:
        return False


def cross_field_checks(record: dict, battery_type: str, row_no: int) -> List[ValidationIssue]:
    """跨字段物理一致性校验（WARN 级，不阻断入库）。"""
    issues: List[ValidationIssue] = []

    if battery_type == LIQUID:
        loading = record.get("filler_loading_mg_cm2")
        cap = record.get("initial_capacity_mah_g")
        if loading and cap:
            # 面容量合理区间 0.05 ~ 20 mAh/cm²
            areal = loading * cap / 1000.0
            if areal > 20:
                issues.append(ValidationIssue(
                    row_no, "filler_loading_mg_cm2", "CROSS_AREAL_CAPACITY_HIGH",
                    f"推算面容量 {areal:.2f} mAh/cm² 偏高，请核对负载量与比容量",
                    areal, "WARN"))
    ce = record.get("coulombic_efficiency_pct")
    ret = record.get("capacity_retention_pct")
    if ce is not None and ret is not None and ce > 100 and ret > 100:
        issues.append(ValidationIssue(
            row_no, "capacity_retention_pct", "CROSS_RETENTION_CE",
            "容量保持率与库伦效率同时 >100%，数据可疑", ret, "WARN"))
    cond = record.get("ionic_conductivity_ms_cm")
    thick = record.get("membrane_thickness_um")
    if cond and thick:
        asr = thick * 0.1 / cond       # Ω·cm²
        if asr < 0.05:
            issues.append(ValidationIssue(
                row_no, "membrane_thickness_um", "CROSS_ASR_LOW",
                f"推算面比电阻 {asr:.4f} Ω·cm² 异常偏低，请核对厚度与电导率",
                asr, "WARN"))
    return issues


def detect_battery_type(columns: Sequence[str]) -> Optional[str]:
    """根据列名关键字判定电池体系；无法判定时返回 None。"""
    norm = [normalize_header(c) for c in columns]
    joined = "".join(norm)
    liq = sum(1 for h in LIQUID_HINTS if normalize_header(h) in joined)
    sol = sum(1 for h in SOLID_HINTS if normalize_header(h) in joined)
    if liq > sol:
        return LIQUID
    if sol > liq:
        return SOLID
    return None


def to_model_frame(df, battery_type: str):
    """把数据库英文列 DataFrame 还原成建模模块（modeling.py）需要的中文列。

    对中文列名做别名容错：先按标准中文名查找，找不到再按归一化别名
    （如「隔膜厚度(μm)」→「膜厚度(μm)」）回退，避免字段表与建模特征表
    写法不一致导致 KeyError（决策②丙：真实样本≥30 切换后必触发）。
    """
    import pandas as pd
    feats = LIQUID_MODEL_FEATURES if battery_type == LIQUID else SOLID_MODEL_FEATURES
    tgts = LIQUID_MODEL_TARGETS if battery_type == LIQUID else SOLID_MODEL_TARGETS
    out = pd.DataFrame(index=df.index)
    for cn_list in (feats, tgts):
        for cn in cn_list:
            spec = FIELD_BY_CN.get(cn)
            if spec is None:
                col = ALIASES.get(normalize_header(cn))
                spec = FIELD_BY_COLUMN.get(col) if col else None
            if spec is None:
                out[cn] = np_nan()
                continue
            out[cn] = df[spec.column] if spec.column in df.columns else np_nan()
    return out, feats, tgts


def np_nan():
    import math
    return math.nan
