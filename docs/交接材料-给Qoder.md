# 交接材料 — 硫芯LitAgent 平台迁移阿里云（给接手的 AI / Qoder）

> 这份文档**自包含**。接手方只需拿到仓库 `D:\锂硫电池\bf-platform` 和这份文档，即可无缝继续，不需要翻历史对话。
> 整理时间：2026-11-21　｜　整理人：沈屹（原协作 AI）

---

## 0. 一句话交代

把 **bf-platform / 硫芯LitAgent**（锂硫电池材料性能预测平台）从已停用的腾讯云 Windows 服务器，迁到**阿里云 ECS Linux + Docker**。代码在 GitHub，数据用脚本可复现重建。用户已明确：**只迁这一个平台**，其余平台不动。

用户当前状态：**还没建 ECS**，需要按 `docs/阿里云ECS与SSH连接-新手操作手册.md` 建好机器后，把「公网 IP + 登录用户名 + `.pem` 私钥的本机路径」交给接手方，即可开工。

---

## 1. 项目身份与坐标（一字不改地交接）

| 项 | 值 |
|---|---|
| 应用名（已定，勿再改） | **硫芯LitAgent：锂硫电池科研智能体** |
| GitHub 仓库 | `https://github.com/momomingming/bf-platform`（**公开**） |
| 分支 | `main` |
| 本地工作目录 | `D:\锂硫电池\bf-platform` |
| 本地 Python | `C:/Users/HJ/.workbuddy/binaries/python/envs/default/Scripts/python.exe`（pandas 3.0.5） |
| 服务端口 | **8501**（Streamlit），健康检查 `/_stcore/health` |
| 目标形态 | 阿里云 ECS Ubuntu 22.04（2C2G）+ Docker Compose |
| 旧服务器 | 腾讯云 Lighthouse `lhins-gkzr2xzg` / `82.156.43.223` — **已停用，不再依赖** |

⚠️ **命名相关的两个已定决策，不要推翻**：
1. 应用显示名统一为「硫芯LitAgent：锂硫电池科研智能体」（app.py 三处 + agent 四处已改完）。
2. GitHub 仓库名**保持 `bf-platform` 不改**（改名会破坏报名表/README 的外链）。

---

## 2. 用户是谁、怎么沟通（重要）

- 用户：**黄晋**（昵称晋晋），大连理工大学盘锦校区大二，锂硫电池 / LDH / 玄武岩纤维方向。
- 沟通偏好：**直接、果断、务实、不废话**；简体中文。厌恶长篇铺垫和空话。
- 技术水平：**正在学习云服务器和 SSH**。涉及基础操作（建 ECS、密钥、安全组、SSH 命令）时**不要省略步骤**，要有"为什么这么做"的解释——`docs/阿里云ECS与SSH连接-新手操作手册.md` 已按这个标准写好，可直接给她。
- 协作风格：习惯用很短的指令（"继续""重试"）驱动任务；对发布/覆盖类操作（tag、release、强推）要求**先确认前提、冲突回到她这边**，不要自作主张覆盖。
- 安全红线：**永远不要在对话里让她发私钥 `.pem` 的内容**，只要本机路径即可。

---

## 3. 已完成的工作（不要重做）

| 阶段 | 内容 | 状态 |
|---|---|---|
| Phase 0–3 | 基线自测、玄武岩纤维(BF)/LDH 升为一等公民场景、模型版本化、指标回流 | ✅ 完成 |
| 顯示透明度 | 首页均值卡片显示 `(n=...)` 与 `±标准差`，低样本标"样本不足" | ✅ 完成 |
| 数据灌库 | `tools/seed_db.py`：从原始 CSV + 文献样本幂等重建 SQLite | ✅ 1254 条 / 0 错误 / 一致性 7/7 |
| 文献入库 | `lit_samples/lit_lis_hosts.csv`：4 条原创研究样本（NiFe LDH / 1T'-LixMoS2 / ZLS-0.2） | ✅ 完成 |
| 命名统一 | 应用 + agent 全部统一为硫芯LitAgent | ✅ 完成 |
| agent 合并 | 远端 agent 批次已合并入 main | ✅ 完成 |
| 旧数据排查 | GitHub vs 本地 173 文件零差异；确认无旧库独有数据（详见 §6） | ✅ 完成 |
| 交接文档 | `docs/迁移阿里云-资料清单与协作方案.md`、`docs/阿里云ECS与SSH连接-新手操作手册.md` | ✅ 已推 GitHub |

**本地自测命令**（接手方任何时候可重跑）：
```bash
VENV="C:/Users/HJ/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
cd "D:/锂硫电池/bf-platform/lis_battery_platform"
# Streamlit 无头自测（注意：HTTP GET / 恒返回 200，不能用来判断异常）
# 用 AppTest：
#   at = AppTest.from_file("app.py", default_timeout=900)
#   at.run(); len(at.exception) 应为 0
#   再切固态 radio 后 at.run()，也应为 0
```

---

## 4. 待办（接手方从这里继续）

按优先级：

1. **建 ECS**（用户操作，接手方指导）——Ubuntu 22.04 / 2C2G / 勾公网 IP / 密钥对登录 / 安全组放行 **22 和 8501**。
2. **拿到连接三件套**——公网 IP、用户名（一般 `root`）、`.pem` 本机路径（**不要内容**）。
3. **修 Dockerfile 依赖红线**（本地无风险，先做）：
   - `lis_battery_platform/requirements.txt` 里 `xgboost>=2.0.0` → **`xgboost>=3.0.0`**。
     ⚠️ 原因：xgboost 2.x 加载 3.x 训练的 UBJ 模型**不报错但预测全错**（实测 −12.5 vs 68.24）。
   - `pandas` 保持 3.x（代码已用 `is_numeric_dtype` 适配 pandas 3 的 `str` dtype，别降到 2）。
   - `docker-compose.yml` 补上 `BF_DB_PATH=/app/data/platform.db` 环境变量（当前没有，必须显式设，否则每次重建容器可能丢库）。
4. **本地 Docker 起一遍**：`docker compose up -d --build`，跑 AppTest 液态/固态两条路径。
5. **灌库**：在 ECS 上跑 `tools/seed_db.py`（设 `BF_DB_PATH=/opt/litagent/data/platform.db`），产出 1254 条干净库。
6. **上线**：`docker compose up -d --build` → 健康检查 → 外部 `http://<IP>:8501` 打开验证。
7. **写一键更新脚本**（Docker 版，替代旧的 Windows `update_bf_server.ps1`）。
8. **清理可选**：本地 2GB VASP 中间产物（`results/Al2O3_*` 等）按用户确认处置.

---

## 5. 环境与依赖（迁移必须对齐）

| 包 | 生产实测版本 | 红线 |
|---|---|---|
| Python | 3.11.9 | Docker 用 `python:3.11-slim` |
| streamlit | 1.63.0 | — |
| pandas | 3.0.5 | **保持 3.x**，别降到 2 |
| numpy | 2.4.6 | — |
| scikit-learn | 1.9.0 | — |
| xgboost | **3.2.0** | **必须 ≥3**（见 §4-3） |
| plotly | 7.0.0 | — |
| scipy | 1.17.1 | — |
| openpyxl / xlrd | 已装 | Excel 导入必需 |

Streamlit 配置（`.streamlit/config.toml`）：`enableCORS=false`、`maxUploadSize=50`、`headless=true`、`port=8501`。

---

## 6. 数据资产清单（GitHub 逐项排查结论，2026-11-21）

**核心结论：GitHub 仓库 main 分支（173 文件）与本地已跟踪文件零差异；仓库从未上传过任何 `.db`；`*_cleaned.csv` 是原始版的零独有行子集。旧库已停用，不存在"从旧服务器导出"这条路，也没有数据会因此丢失。**

### ✅ 需保留（迁移必须带走）
| 项 | 说明 |
|---|---|
| GitHub main 全部 173 文件 | 唯一事实源 |
| `lis_battery_platform/liquid_data.csv`(650) / `solid_data.csv`(600) | 灌库源，完整超集 |
| `lit_samples/lit_lis_hosts.csv`(4 条) | 原创文献样本 |
| `tools/seed_db.py` | 可复现重建 DB，幂等去重 |
| `results/*.json`、`figures/*.png`、`DFT_*/input.inp`+`POSCAR` | 已提炼结论与可重跑输入 |
| `agent/`（5 文件） | 随仓库走，本次不上线 |

### 🗑️ 可废弃（不迁）
| 项 | 体积 | 理由 |
|---|---|---|
| `results/Al2O3_*`、`Fe2O3_*`、`MoS2_*` 等 VASP 原始输出 | ~2GB | `restart`/`Hessian`/`RESTART.kp`/zip 是中间态；结论已进 JSON/PNG，输入已入库 |
| `app.py.bak` | 小 | 旧版备份 |
| `__pycache__/` | 260KB | 可自动再生 |
| 腾讯云整个环境 | — | 已停用 |

### ❓ 待确认（都有安全默认值，不阻塞）
| 项 | 默认值 |
|---|---|
| 2GB DFT 中间产物 | 不迁 |
| `lit_extracted/`（6.1MB 抽取文本） | 不迁（4 条有效样本已入 CSV） |
| agent 是否上线 | 本次不上线 |
| 仓库名 | 保持 `bf-platform` |

---

## 7. 已知坑（血泪教训，务必遵守）

| 坑 | 表现 | 对策 |
|---|---|---|
| **git 推送通道** | 本机代理 `127.0.0.1:55601` 已死（curl 返回 000），清空代理直连 github:443 也超时；git push/fetch 全线 502/128 | 用 `gh api` 的 Contents API 推文件（`PUT repos/{owner}/{repo}/contents/{path}`，payload 含 base64 content + message + branch + 现有文件 sha）。**实测可行**。 |
| **GitHub 远端有非快进提交** | 历史上有另一个会话推过 agent + 改名，直接 push 会 non-fast-forward | 先 `gh api repos/.../branches/main` 查真实 HEAD，**永远不要强推覆盖**。 |
| **本地/远端 SHA 不同** | 本地 HEAD `e38a1a4` vs 远端 `18e3755`（API 推送产生两个提交），但 tree 同为 `5e40329`、内容完全一致 | 无害标记差异，不必强行对齐。**下次要推送走 API 通道即可**。 |
| **GBK 乱码** | 中文 `.ps1` 在 Windows PowerShell 5.1 被当 GBK 读，引号断裂报 ParserError | 部署脚本必须**纯 ASCII** |
| **Streamlit 自测** | HTTP GET `/` 恒返回 200，不能判断异常 | 用 `AppTest`（`streamlit.testing.v1`）跑脚本 |
| **预览面板自动格式化** | WorkBuddy 预览打开的 md 会被自动改（表格加空格/加空行），本地显示 M | 远端保存的是干净版；`git checkout -- <file>` 丢弃即可 |
| **本地 DB 位置** | 生产 DB 由 `BF_DB_PATH` 指定，不显式设会丢 | 容器里设 `BF_DB_PATH=/app/data/platform.db`，卷挂 `./data:/app/data` |

---

## 8. 交接时需要一起给 Qoder 的文件（按优先级）

**最小集**（让它立刻能开工）：
1. 这份 `docs/交接材料-给Qoder.md`
2. `docs/迁移阿里云-资料清单与协作方案.md`（现状台账、分工、步骤、验证清单）
3. `docs/阿里云ECS与SSH连接-新手操作手册.md`（给用户的建机指南）
4. 整个仓库 `D:\锂硫电池\bf-platform`（或让它 `git clone https://github.com/momomingming/bf-platform`）

**增强集**（按需）：
- `docs/功能设计-导入-计算-数据库.md`（schema / 导入 / 指标口径）
- `docs/系统规划-平台架构与落地路线.md`（架构与 Phase 规划）
- `README.md`（项目概览）

**绝对不要发**：
- 任何 `.pem` 私钥内容（只要路径）
- 宝塔面板账号密码、服务器 Administrator 密码
- 腾讯云/阿里云的 API 密钥、AccessKey

---

## 9. 一句话交接总结

> 代码已就绪、数据已可复现重建、命名已定、旧库已确认无独有数据。
> 只等用户在阿里云建好 ECS 并给出连接信息，接手方按 §4 步骤走即可上线。
> 遇到 git 推不动就用 §7 的 API 通道，别重试到天荒地老。
