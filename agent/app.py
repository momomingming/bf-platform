"""
硫芯LitAgent：锂硫电池科研智能体（Streamlit 交互界面）
===========================================================
运行：
    cd agent
    pip install -r requirements.txt
    streamlit run app.py
"""
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agent_core as core
from agent_core import run_agent

st.set_page_config(page_title="硫芯LitAgent：锂硫电池科研智能体", page_icon="🪨", layout="wide")

st.markdown("""
<style>
.big-title{font-size:2.0rem;font-weight:700;color:#16213e;text-align:center;
  border-bottom:3px solid #16213e;padding-bottom:.4rem;margin-bottom:.6rem;}
.agent-box{background:#f0f4ff;border:2px solid #4361ee;border-radius:10px;
  padding:1rem;margin:.5rem 0;line-height:1.7;}
.user-box{background:#f0fff4;border:2px solid #2ecc71;border-radius:10px;
  padding:.6rem 1rem;margin:.4rem 0;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="big-title">🪨 硫芯LitAgent：锂硫电池科研智能体</div>',
            unsafe_allow_html=True)

# ---------- 侧边栏 ----------
with st.sidebar:
    st.markdown("### ⚙️ 设置")
    bt = st.radio("电池体系", ["固态锂硫电池", "液态锂硫电池"], index=0,
                  help="默认固态（玄武岩纤维 BF 重点方向）")
    battery_type = "solid" if bt.startswith("固态") else "liquid"
    use_llm = st.checkbox("启用 LLM 润色（需配置密钥）", value=False,
                          help="在环境变量设置 LITAGENT_API_KEY / BASE_URL / MODEL 后生效；"
                               "未配置则自动使用离线模板生成。")
    st.markdown("---")
    st.markdown("### 💡 示例问题")
    examples = [
        "用玄武岩纤维做固态锂硫电池电解质，含量40%，比表面积200，预测性能并给实验方案",
        "LLZO 固态电解质，比表面积15，预测离子电导率和界面阻抗",
        "LDH 做液态锂硫电池隔膜填料，负载1.5 mg/cm²，给性能预测",
    ]
    for ex in examples:
        if st.button(ex, key=ex):
            st.session_state["preset"] = ex

# ---------- 引擎加载（首次约30s，缓存）----------
@st.cache_resource
def load_engine():
    return core.get_engine()

with st.spinner("正在加载预测引擎（首次约30秒，后续秒开）..."):
    load_engine()

# ---------- 对话区 ----------
if "history" not in st.session_state:
    st.session_state["history"] = []

user_q = st.text_input(
    "🔎 用自然语言描述你的材料与需求（例如：玄武岩纤维 含量40% 比表面积200，预测性能并给实验方案）",
    value=st.session_state.get("preset", ""),
    key="q")

col_run, col_clear = st.columns([1, 1])
with col_run:
    submitted = st.button("🚀 运行智能体", type="primary", use_container_width=True)
with col_clear:
    if st.button("🧹 清空对话", use_container_width=True):
        st.session_state["history"] = []
        st.session_state["preset"] = ""
        st.rerun()

if submitted and user_q.strip():
    with st.spinner("智能体思考中..."):
        out = run_agent(user_q, battery_type=battery_type, use_llm=use_llm)
    st.session_state["history"].append((user_q, out))
    st.session_state["preset"] = ""

# 渲染历史（最新在上）
for q, out in reversed(st.session_state["history"]):
    st.markdown(f'<div class="user-box">🧑‍🔬 <b>你</b>：{q}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="agent-box">{out["narrative"]}</div>', unsafe_allow_html=True)
    with st.expander("🔧 技术细节：输入参数与模型预测"):
        st.json(out["inputs"])
        pred_df = {t: {"预测值": round(p["predicted_value"], 4),
                       "不确定度": round(p["uncertainty"], 4),
                       "R²": round(p["r2"], 3),
                       "最佳模型": p["best_model"]}
                   for t, p in out["predictions"].items()}
        st.dataframe(pred_df, use_container_width=True)

if not st.session_state["history"]:
    st.info("在上方输入你的问题，或点左侧示例开始。无需联网、无需密钥即可运行（LLM 为可选增强）。")

st.markdown("---")
st.caption("硫芯LitAgent：第四届 AIGC 大赛 · 智能体创意应用 ｜ 预测基于文献物理关系编码的代理模型，用于方案比选而非绝对标定。")
