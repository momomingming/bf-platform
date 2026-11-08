"""
可选 LLM 增强层（OpenAI 兼容接口，无密钥时自动降级）
=====================================================
通过环境变量配置，不配置则完全不影响离线运行：
  LITAGENT_BASE_URL  —— 如 https://api.deepseek.com/v1 或通义/硅基流动地址
  LITAGENT_API_KEY   —— 你的密钥
  LITAGENT_MODEL     —— 模型名，如 deepseek-chat / qwen-plus
"""
import os
import json


def is_available() -> bool:
    return bool(os.environ.get("LITAGENT_API_KEY") and os.environ.get("LITAGENT_BASE_URL"))


def _client():
    from openai import OpenAI
    return OpenAI(
        api_key=os.environ["LITAGENT_API_KEY"],
        base_url=os.environ["LITAGENT_BASE_URL"],
    )


SYSTEM_PROMPT = (
    "你是锂硫电池材料研发助理。下面会给到你一次材料性能预测的"
    "结构化结果（输入参数、预测指标、知识库机理、推荐实验方案）。"
    "请用简洁、专业、口语化的中文，把这些信息组织成一段给研究生/本科生看的"
    "科研建议，重点说明：①预测了哪些性能、数量级是否合理；②材料起作用的可能机理；"
    "③下一步实验怎么做。不要编造具体数字，用『约/估算』措辞，并提醒预测基于代理模型。"
)


def refine_narrative(user_text: str, pred_out: dict, know: dict, fallback: str) -> str:
    """用 LLM 润色离线生成的文案；任何失败都返回 fallback。"""
    if not is_available():
        return fallback
    try:
        payload = {
            "用户输入": user_text,
            "编码材料": pred_out.get("encode_key"),
            "输入参数": pred_out.get("inputs"),
            "预测结果": {
                k: {"值": round(v["predicted_value"], 4),
                    "不确定度": round(v["uncertainty"], 4),
                    "R2": round(v["r2"], 3)}
                for k, v in pred_out.get("predictions", {}).items()
            },
            "知识库信息": {kk: know["kb_info"].get(kk) for kk in
                          ("description", "advantages", "disadvantages",
                           "literature_ref", "proxy_material")},
            "推荐方案": know.get("recommend"),
        }
        client = _client()
        resp = client.chat.completions.create(
            model=os.environ.get("LITAGENT_MODEL", "deepseek-chat"),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.3,
            max_tokens=900,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:  # noqa: BLE001
        return fallback + f"\n\n（LLM 润色失败，已回退离线文案：{e}）"


def parse_intent(user_text: str, candidates: list) -> dict:
    """可选：用 LLM 从自然语言抽取结构化意图（材料/参数/目标）。失败返回空。"""
    if not is_available():
        return {}
    try:
        client = _client()
        prompt = (
            "从用户句子中抽取锂硫电池材料研发意图，返回 JSON："
            '{"material": "材料名或null", "battery_type": "solid/liquid/null",'
            ' "params": {"含量wt": 数值或null, "sa": 数值或null, "ps": 数值或null,'
            ' "temp": 数值或null, "rate": 数值或null, "cycle": 数值或null}}。'
            f"可选材料列表（命中其一）：{candidates}。"
            f"用户原话：{user_text}"
        )
        resp = client.chat.completions.create(
            model=os.environ.get("LITAGENT_MODEL", "deepseek-chat"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0, max_tokens=400,
        )
        txt = resp.choices[0].message.content.strip()
        start, end = txt.find("{"), txt.rfind("}")
        if start >= 0 and end > start:
            return json.loads(txt[start:end + 1])
    except Exception:
        return {}
    return {}
