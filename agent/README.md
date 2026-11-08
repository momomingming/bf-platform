# 硫芯·LitAgent —— 锂硫电池科研智能体

> 第四届 AIGC 大赛 · 智能体创意应用赛道作品
> 面向锂硫电池研究者：输入材料配比即可预测电化学性能，并联动文献知识库给出机理解释与实验方案建议。

## 它解决谁的什么问题

做锂硫电池实验的研究生/本科生，经常面临两个痛点：
1. **配方设计靠试错**——换一种填料、调一个含量，性能会怎样，心里没底；
2. **查文献费时**——多硫化物锚定、Li⁺ 传输的机理和对应实验验证散落各处。

本智能体把已有的 **ML 性能预测引擎（XGBoost / RF / Ridge，1250+ 样本）** 与
**材料文献知识库（扩展 KB + 训练 KB）** 编排成一个可对话的科研助手：
用自然语言描述材料与目标，即得「性能预测 + 机理依据 + 可执行实验方案」。

## 核心能力

| 能力 | 实现 |
|------|------|
| 自然语言理解 | 离线规则解析 + 可选 LLM 意图抽取 |
| 性能预测 | 复用 `lis_battery_platform` 的 `predict_single`（真实训练模型） |
| 文献机理 | `material_kb.search_material` / `get_recommended_config` |
| 实验方案 | 基于材料属性自动推荐基底/电解液/负载/倍率/制备 |
| 玄武岩纤维(BF) | 设为一级材料（代理编码，趋势性估算，贴合揭榜挂帅方向） |

## 快速开始

```bash
cd agent
pip install -r requirements.txt
streamlit run app.py
```

首次加载约 30 秒（训练预测模型，之后缓存秒开）。无需联网、无需密钥即可运行；
配置 LLM 后自动启用大模型润色（见下）。

## 可选 LLM 增强（非必需）

```bash
export LITAGENT_BASE_URL="https://api.deepseek.com/v1"   # 或通义/硅基流动
export LITAGENT_API_KEY="你的密钥"
export LITAGENT_MODEL="deepseek-chat"
streamlit run app.py
```

未配置时自动降级为离线模板生成，结果同样完整、可复现。

## 示例输入

- 「用玄武岩纤维做固态锂硫电池电解质，含量40%，比表面积200，预测性能并给实验方案」
- 「LLZO 固态电解质，比表面积15，预测离子电导率和界面阻抗」
- 「LDH 做液态锂硫电池隔膜填料，负载1.5 mg/cm²，给性能预测」

## 目录结构

```
agent/
├── app.py            # Streamlit 对话界面
├── agent_core.py     # 智能体编排：解析 → 预测 → 检索 → 生成（无 Streamlit 依赖）
├── llm_client.py     # 可选 LLM 增强层（OpenAI 兼容，自动降级）
├── prompts.md        # 关键 Prompt 留档（AIGC 声明用）
└── requirements.txt
```

> 预测基于文献物理关系编码的代理模型，用于**方案比选**而非绝对标定；
> 玄武岩纤维(BF)在数据集内以代理材料编码，结果为趋势性估算，已在界面与文案中明确标注。
