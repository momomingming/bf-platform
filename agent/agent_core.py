"""
硫芯LitAgent：锂硫电池科研智能体（核心编排逻辑，无 Streamlit 依赖）
========================================================================
复用父目录 lis_battery_platform 的 ML 预测引擎与材料知识库：
  - modeling.train_models / predict_single  （性能预测）
  - material_kb.search_material / get_recommended_config （文献机理 + 实验方案）
  - generate_data （数据生成）

设计原则：
  - 离线可运行：无 LLM 密钥时用「规则解析 + 模板生成」也能给出完整结果；
  - 在线增强：配置 LLM 后用大模型做自然语言理解与文案润色（可选，非必需）。
"""

import os
import re
import sys
import json
from typing import Optional

# ---- 把父目录的 lis_battery_platform 加入路径，复用真实引擎 ----
_HERE = os.path.dirname(os.path.abspath(__file__))
_PLATFORM = os.path.abspath(os.path.join(_HERE, "..", "lis_battery_platform"))
if _PLATFORM not in sys.path:
    sys.path.insert(0, _PLATFORM)

from generate_data import (  # noqa: E402
    generate_all_data,
    SOLID_FILLERS, SOLID_SUBSTRATES,
    LIQUID_FILLERS, LIQUID_SUBSTRATES,
    LIQUID_ELECTROLYTES,
)
from modeling import (  # noqa: E402
    train_models, predict_single,
    SOLID_FEATURES, SOLID_TARGETS,
    LIQUID_FEATURES, LIQUID_TARGETS,
)
from material_kb import (  # noqa: E402
    EXTENDED_SOLID_KB, EXTENDED_LIQUID_KB,
    search_material, get_recommended_config,
)

# 玄武岩纤维(BF) 在现有 SOLID_FILLERS 中没有独立实体键，使用代理材料编码，
# 物理属性取自玄武岩纤维真实区间；预测值标注为「估算」。
BF_PROFILE = {
    "display": "玄武岩纤维(BF)",
    "category": "氧化物/硅酸盐",
    "proxy": "LLZO@GO复合",        # 用作模型编码的代理材料
    "sa_base": 200.0,              # 玄武岩纤维比表面积典型区间 100–400
    "ps_base": 12.0,               # 纳米级纤维直径对应粒径
    "stability": 0.90,
    "description": "玄武岩纤维(BF)是天然硅酸盐矿物纤维，主成分为 SiO₂/Al₂O₃/Fe₂O₃/CaO，"
                   "成本低、热稳定性好、机械强度高；表面丰富的 Si–O/Fe–O 极性位点可物理锚定"
                   "多硫化物，是极具潜力的锂硫电池低成本隔膜/电解质增强相。",
    "advantages": [
        "原料丰富、成本远低于碳纳米管/石墨烯等增强相",
        "热稳定性与机械强度优异，利于电池安全",
        "表面极性位点可吸附多硫化物、抑制穿梭效应",
    ],
    "disadvantages": [
        "本体绝缘，需与离子导体复合以提升离子电导率",
        "与聚合物基体的界面相容性需优化",
    ],
    "literature_ref": "参照玄武岩纤维/硅酸盐材料在锂硫电池隔膜改性中的公开研究；"
                     "因数据集中无独立 BF 实体，建模时以 LLZO@GO 复合作为代理编码（结果标注为估算）。",
}

# 别名 → 材料键（固态优先）
_SOLID_ALIAS = {
    "玄武岩": "BF", "玄武岩纤维": "BF", "bf": "BF", "basalt": "BF", "bf纤维": "BF",
    "ldh": "LDH", "层状双氢氧化物": "LDH", "水滑石": "LDH",
    "mxene": "MXene", "黑磷": "BP", "bp": "BP",
    "llzo": "LLZO(Li₇La₃Zr₂O₁₂)", "lgps": "Li₁₀GeP₂S₁₂(LGPS)",
    "peo": "PEO/LiTFSI", "span": "PEO/LiTFSI",
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s.lower())


def get_engine():
    """加载并缓存：数据 + 双体系模型 + 编码器 + 缩放器。"""
    if getattr(get_engine, "_cache", None) is not None:
        return get_engine._cache

    liquid_df, solid_df = generate_all_data()
    liquid_res, liquid_enc, liquid_scaler = train_models(
        liquid_df, LIQUID_FEATURES, LIQUID_TARGETS)
    solid_res, solid_enc, solid_scaler = train_models(
        solid_df, SOLID_FEATURES, SOLID_TARGETS)

    eng = {
        "liquid": (liquid_res, liquid_enc, liquid_scaler, liquid_df),
        "solid": (solid_res, solid_enc, solid_scaler, solid_df),
    }
    get_engine._cache = eng
    return eng


# ============================================================
# 1) 自然语言解析（离线规则版）
# ============================================================
def detect_battery_type(text: str) -> str:
    t = _norm(text)
    if any(k in t for k in ["固态", "固体", "solid", "peo", "span", "硫化物", "氧化物电解质"]):
        return "solid"
    if any(k in t for k in ["液态", "液体", "liquid", "电解液", "隔膜的"]):
        return "liquid"
    return "solid"  # 默认固态（BF 重点方向）


def resolve_material(text: str, battery_type: str):
    """返回 (key_or_BF, info_dict, is_bf)。"""
    t = _norm(text)
    # 先查 BF 别名
    for alias, key in _SOLID_ALIAS.items():
        if alias in t:
            if key == "BF":
                return "BF", BF_PROFILE, True
            # 其它别名尝试在知识库/填料库命中
            kb = EXTENDED_SOLID_KB if battery_type == "solid" else EXTENDED_LIQUID_KB
            fillers = SOLID_FILLERS if battery_type == "solid" else LIQUID_FILLERS
            if key in kb:
                return key, kb[key], False
            if key in fillers:
                return key, fillers[key], False
    # 在填料库与扩展库里做子串匹配
    kb = EXTENDED_SOLID_KB if battery_type == "solid" else EXTENDED_LIQUID_KB
    fillers = SOLID_FILLERS if battery_type == "solid" else LIQUID_FILLERS
    for key in list(kb.keys()) + list(fillers.keys()):
        if _norm(key) in t:
            info = kb.get(key, fillers.get(key, {}))
            return key, info, False
    # 默认：固态用 BF，液态用第一个填料
    if battery_type == "solid":
        return "BF", BF_PROFILE, True
    first = next(iter(LIQUID_FILLERS))
    return first, LIQUID_FILLERS[first], False


def extract_params(text: str, battery_type: str, material_info) -> dict:
    """用正则从自然语言抽取数值参数，缺失则用材料默认/平台默认。"""
    t = text
    p = {}
    # 含量 wt% / 负载量
    m = re.search(r"含量[约约]?\s*(\d+(?:\.\d+)?)\s*(?:wt%|%)", t)
    if not m:
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:wt%|%)\s*(?:含量|负载)", t)
    if m:
        p["含量wt"] = float(m.group(1))
    m = re.search(r"负载[量]?\s*(?:约|为)?\s*(\d+(?:\.\d+)?)\s*(?:mg|毫克)", t)
    if m:
        p["负载mg"] = float(m.group(1))
    # 比表面积
    m = re.search(r"比表面积[约约]?\s*(\d+(?:\.\d+)?)\s*(?:m²|m2|平方)", t)
    if m:
        p["sa"] = float(m.group(1))
    # 粒径
    m = re.search(r"粒径[约约]?\s*(\d+(?:\.\d+)?)\s*(?:nm|纳米)", t)
    if m:
        p["ps"] = float(m.group(1))
    # 膜厚
    m = re.search(r"(?:膜厚|厚度)[约约]?\s*(\d+(?:\.\d+)?)\s*(?:μm|微米|um)", t)
    if m:
        p["thick"] = float(m.group(1))
    # 温度
    m = re.search(r"温度[约约]?\s*(\d+(?:\.\d+)?)\s*(?:°?c|度|摄)", t)
    if m:
        p["temp"] = float(m.group(1))
    # 压力
    m = re.search(r"压力[约约]?\s*(\d+(?:\.\d+)?)\s*(?:mpa|兆帕)", t)
    if m:
        p["press"] = float(m.group(1))
    # 倍率
    m = re.search(r"(\d+(?:\.\d+)?)\s*[cC]\s*(?:倍率|率)", t)
    if not m:
        m = re.search(r"倍率[约约]?\s*(\d+(?:\.\d+)?)\s*[cC]", t)
    if m:
        p["rate"] = float(m.group(1))
    # 循环
    m = re.search(r"循环[次数约约]?\s*(\d+)\s*(?:圈|次|周)", t)
    if m:
        p["cycle"] = int(m.group(1))
    return p


# ============================================================
# 2) 调用真实模型做预测
# ============================================================
def run_prediction(material_key, material_info, is_bf, battery_type, params: dict) -> dict:
    eng = get_engine()
    res, enc, scaler, df = eng[battery_type]

    if battery_type == "solid":
        fillers = SOLID_FILLERS
        subs = SOLID_SUBSTRATES
        feats = SOLID_FEATURES
        tgts = SOLID_TARGETS
    else:
        fillers = LIQUID_FILLERS
        subs = LIQUID_SUBSTRATES
        feats = LIQUID_FEATURES
        tgts = LIQUID_TARGETS

    # 编码用的材料键：BF 用代理材料
    encode_key = material_info.get("proxy", material_key) if is_bf else material_key
    base = fillers.get(encode_key, {})
    if not base:  # 兜底：取第一个填料
        encode_key = next(iter(fillers))
        base = fillers[encode_key]

    category = material_info.get("category") or base.get("category", "其它")

    if battery_type == "solid":
        first_sub = next(iter(subs))
        sub_thick = 50.0
        if isinstance(subs[first_sub], dict):
            sub_thick = float(subs[first_sub].get("thickness_base", 50.0))
        inp = {
            "填料类型": encode_key,
            "填料类别": category,
            "填料含量(wt%)": params.get("含量wt", 40.0),
            "比表面积(m²/g)": params.get("sa", float(base.get("sa_base", 100))),
            "粒径(nm)": params.get("ps", float(base.get("ps_base", 30))),
            "基底/聚合物": params.get("sub", first_sub),
            "膜厚度(μm)": params.get("thick", sub_thick),
            "温度(°C)": params.get("temp", 25.0),
            "压力(MPa)": params.get("press", 200.0),
            "倍率(C)": params.get("rate", 0.2),
            "循环次数": params.get("cycle", 200),
        }
    else:
        inp = {
            "填料类型": encode_key,
            "填料类别": category,
            "填料负载量(mg/cm²)": params.get("负载mg", 1.0),
            "比表面积(m²/g)": params.get("sa", float(base.get("sa_base", 100))),
            "粒径(nm)": params.get("ps", float(base.get("ps_base", 30))),
            "孔体积(cm³/g)": float(base.get("pv_base", 0.2)),
            "基底材料": params.get("sub", next(iter(subs))),
            "隔膜厚度(μm)": params.get("thick", 25.0),
            "孔隙率": 0.5,
            "电解液体系": params.get("elec", next(iter(LIQUID_ELECTROLYTES))),
            "温度(°C)": params.get("temp", 25.0),
            "倍率(C)": params.get("rate", 0.5),
            "循环次数": params.get("cycle", 200),
        }

    preds = predict_single(res, enc, scaler, feats, tgts, inp, battery_type)
    return {
        "inputs": inp,
        "encode_key": encode_key,
        "is_bf": is_bf,
        "predictions": preds,
        "targets": tgts,
    }


# ============================================================
# 3) 文献机理 + 实验方案
# ============================================================
def gather_knowledge(material_key, material_info, is_bf, battery_type) -> dict:
    kb = EXTENDED_SOLID_KB if battery_type == "solid" else EXTENDED_LIQUID_KB
    # 优先用扩展库命中
    hits = search_material(material_key, battery_type)
    info = material_info
    if not is_bf and hits:
        info = hits[0][1]
    elif is_bf:
        info = BF_PROFILE
    rec = {}
    try:
        rec = get_recommended_config(info, battery_type)
    except Exception:
        rec = {}
    return {
        "kb_info": info,
        "search_hits": [k for k, _ in hits][:5],
        "recommend": rec,
    }


# ============================================================
# 4) 自然语言生成（离线模板版，保证无密钥也能出完整结果）
# ============================================================
def _fmt_target(target, val, unc):
    if "电导率" in target:
        return f"{val:.4f} ± {unc:.4f}"
    if "容量" in target or "阻抗" in target:
        return f"{val:.1f} ± {unc:.1f}"
    if "效率" in target or "保持率" in target or "窗口" in target:
        return f"{val:.2f} ± {unc:.2f}"
    return f"{val:.4f} ± {unc:.4f}"


def nlg_offline(material_key, material_info, is_bf, battery_type, pred_out, know) -> str:
    info = know["kb_info"]
    lines = []
    title = material_info.get("display", material_key) if is_bf else material_key
    lines.append(f"## 🔋 针对「{title}」的科研建议\n")

    # 预测结果
    lines.append("### 一、性能预测（模型估算）")
    lines.append("> 说明：预测引擎在**基于文献物理关系编码的生成式数据集**上训练"
                 "（约 1250 条合成样本），输出为**相对趋势与方案比选参考**，并非实验实测值；"
                 "下方 R² 反映模型对生成数据的拟合优度，不代表对真实电池的预测精度。")
    if is_bf:
        lines.append("> 注：玄武岩纤维(BF)在当前数据集中以代理材料编码，结果为**趋势性估算**，用于方案比选而非绝对标定。")
    preds = pred_out["predictions"]
    for tgt, pi in preds.items():
        v = pi["predicted_value"]
        u = pi["uncertainty"]
        r2 = pi["r2"]
        badge = "🟢" if r2 > 0.8 else ("🟡" if r2 > 0.5 else "🔴")
        lines.append(f"- **{tgt}**：{_fmt_target(tgt, v, u)}  （{badge} 模型R²={r2:.2f}，{pi['best_model']}）")
    lines.append("")

    # 机理 / 文献依据
    lines.append("### 二、机理与文献依据")
    desc = info.get("description") or info.get("name_zh") or ""
    if desc:
        lines.append(f"- **材料特性**：{desc}")
    adv = info.get("advantages") or []
    if adv:
        lines.append("- **核心优势**：" + "；".join(adv) + "。")
    dis = info.get("disadvantages") or []
    if dis:
        lines.append("- **主要短板**：" + "；".join(dis) + "。")
    ref = info.get("literature_ref") or info.get("proxy_material")
    if ref:
        lines.append(f"- **文献/代理依据**：{ref}")
    if know["search_hits"]:
        lines.append(f"- **知识库命中（相关材料）**：{', '.join(know['search_hits'])}")
    lines.append("")

    # 实验方案
    lines.append("### 三、推荐实验方案")
    rec = know["recommend"]
    if rec:
        for k, v in rec.items():
            lines.append(f"- **{k}**：{v}")
    else:
        lines.append("- 建议组装扣式电池，按 0.05–1C 倍率梯度进行倍率测试，并在 0.2C 下进行 ≥100 圈循环评估容量保持率。")
    lines.append("")

    # 一句话结论
    lines.append("### 四、结论速览")
    cap = preds.get("初始比容量(mAh/g)")
    if cap:
        lines.append(f"在设定工况下，预期初始比容量约 {cap['predicted_value']:.0f} mAh/g"
                     f"（±{cap['uncertainty']:.0f}），建议据此设定对照组与表征计划。")
    else:
        lines.append("已给出上述预测与方案，可作为实验设计的起点。")
    return "\n".join(lines)


# ============================================================
# 5) 对外主入口
# ============================================================
def run_agent(user_text: str, battery_type: Optional[str] = None,
              use_llm: bool = False) -> dict:
    """智能体主循环：解析 → 预测 → 检索 → 生成。返回结构化结果。"""
    bt = battery_type or detect_battery_type(user_text)
    mat_key, mat_info, is_bf = resolve_material(user_text, bt)
    params = extract_params(user_text, bt, mat_info)
    pred_out = run_prediction(mat_key, mat_info, is_bf, bt, params)
    know = gather_knowledge(mat_key, mat_info, is_bf, bt)

    narrative = nlg_offline(mat_key, mat_info, is_bf, bt, pred_out, know)
    if use_llm:
        try:
            from llm_client import refine_narrative
            narrative = refine_narrative(user_text, pred_out, know, narrative)
        except Exception:
            pass  # LLM 失败则回退离线文案

    return {
        "battery_type": bt,
        "material": mat_info.get("display", mat_key) if is_bf else mat_key,
        "is_bf": is_bf,
        "inputs": pred_out["inputs"],
        "predictions": pred_out["predictions"],
        "knowledge": know,
        "narrative": narrative,
    }


if __name__ == "__main__":
    # 离线自测：不依赖任何网络/密钥
    sample = "我想用玄武岩纤维做固态锂硫电池电解质，含量40%，比表面积200 m²/g，预测性能并给实验方案"
    out = run_agent(sample)
    print("材料:", out["material"], "| 电池类型:", out["battery_type"])
    print(out["narrative"])
