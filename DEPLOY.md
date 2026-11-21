# 部署指南 · 硫芯LitAgent（锂硫电池科研智能体）

> 目标服务器：**阿里云 ECS（Ubuntu 22.04 LTS, 2C2G）+ Docker**。
> 服务端口 **8501**，健康检查 `/_stcore/health`。
> 配套文档：[`docs/阿里云ECS与SSH连接-新手操作手册.md`](docs/阿里云ECS与SSH连接-新手操作手册.md)（建机）、[`docs/迁移阿里云-资料清单与协作方案.md`](docs/迁移阿里云-资料清单与协作方案.md)（方案）。

---

## 1. 目标布局

```
/opt/litagent/                 ← git clone 出来的仓库
├─ Dockerfile / docker-compose.yml
├─ lis_battery_platform/       ← 应用代码（镜像里 COPY 这一层）
├─ tools/seed_db.py            ← 灌库脚本（幂等）
├─ lit_samples/                ← 文献样本 CSV
└─ data/                       ← 挂载进容器，持久化
   ├─ platform.db              ← SQLite 主库
   └─ models/                  ← 模型产物 (joblib)
```

**两个必须显式设置的环境变量**（已在 `docker-compose.yml` 里配好，别删）：

| 变量 | 值 | 不设会怎样 |
|---|---|---|
| `BF_DB_PATH` | `/app/data/platform.db` | 库落在容器内层，`--build` 重建即丢 |
| `BF_MODELS_DIR` | `/app/data/models` | 模型产物同理丢失 |

---

## 2. 一次性部署（首次）

### 2.1 前置检查

- 安全组已放行 **TCP 22**（SSH）和 **TCP 8501**（网页）
- 实例已分配**公网 IPv4**
- 本机有私钥 `.pem`（只给路径，不要外发内容）

### 2.2 上传并执行部署脚本

本机（Git Bash 或 PowerShell）：

```bash
scp -i "C:/Users/HJ/.ssh/litagent-key.pem" \
  "D:/锂硫电池/bf-platform/deploy/deploy_linux.sh" \
  root@<公网IP>:/root/deploy_linux.sh
```

服务器上：

```bash
chmod +x /root/deploy_linux.sh
bash /root/deploy_linux.sh
```

脚本会依次完成：装 Docker → clone 仓库 → 构建镜像 → 灌库（1254 条，幂等）→ 起容器 → 健康检查。
全部输出为 ASCII，失败会打印最近 50 行容器日志。

<details>
<summary>不想用脚本时，手动等价命令</summary>

```bash
apt-get update && apt-get install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
apt-get update && apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

mkdir -p /opt/litagent && cd /opt/litagent
git clone --branch main https://github.com/momomingming/bf-platform.git .
mkdir -p data
docker compose build

docker run --rm --entrypoint python -v /opt/litagent:/repo -w /repo \
  -e BF_DB_PATH=/repo/data/platform.db bf-platform:latest tools/seed_db.py

docker compose up -d
curl -fsS http://127.0.0.1:8501/_stcore/health   # 期望输出 ok
```

</details>

### 2.3 无 EIP / VPC 内网部署（本次实例走这条）

本实例**没有公网 IP，也没有 NAT 网关**，所以 §2.2 的 `scp` + `git clone` 全部不可用：
GitHub、Docker Hub、pypi.org 在 VPC 内都出不去。对应的做法是：

| 环节 | 公网方案 | VPC 内网方案 |
|---|---|---|
| 传代码 | `scp` / `git clone` | **阿里云云助手 RunCommand 分块传输**（把仓库打成 tar.gz，base64 分片追加到服务器再解包） |
| 基础镜像 | `docker pull python:3.11-slim` | Docker Hub 拉不到 → 用内部 apt 源 **自建** 等价镜像（`deploy/build_base_image.sh`） |
| Python 依赖 | pypi.org | `mirrors.cloud.aliyuncs.com/pypi/simple`（写进 `/etc/pip.conf` 与 `PIP_INDEX_URL`） |
| 访问 | 公网 IP:8501 | **内网 IP:8501**，需 VPN / 云企业网 / 同 VPC 跳板机 |

服务器上只跑这一条（源码已由外部传进 `/opt/litagent`）：

```bash
bash /opt/litagent/deploy/deploy_alicloud_vpc.sh
```

脚本会：装/复用 Docker → 写 `daemon.json`（含容器 DNS `100.100.2.136/138`）→ 写 `/etc/pip.conf` →
基础镜像（优先 `docker pull`，失败则 debootstrap 自建）→ `docker compose build` → 灌库 → 起容器 → 健康检查。

> **容器 DNS 必须显式配**：宿主机的 `resolv.conf` 是 `127.0.0.53`（systemd-resolved 桩），
> 容器继承后解析不了域名，因此 `daemon.json` 里要写死阿里云 VPC 解析器。

> **基础镜像为什么自建**：`registry-vpc.cn-beijing.aliyuncs.com` 是 ACR 的 VPC 端点，
> 只能拉 ACR 自己的仓库，匿名 token 没有 Docker Hub 的授权，拉 `python` 会报
> `pull access denied`。所以用 `debootstrap` 从内网 apt 源装出 Python 3.11，
> 再 `docker import` 成 `python:3.11-slim`。

### 2.4 无公网时如何从本机把代码送上去

用阿里云 **云助手 RunCommand**（OpenAPI `RunCommand` + `DescribeInvocations`），
不需要 SSH、不需要公网 IP。本机脚本把仓库打包后按 ~14KB base64 分片追加：

```python
# 本机（需 pip install alibabacloud_tea_openapi alibabacloud_ecs20140526）
# 1) 打包（排除大文件与运行期数据）
cd "D:/锂硫电池/bf-platform"
tar czf /tmp/bf_payload.tgz --exclude=.git --exclude='DFT_*' --exclude=results \
    --exclude=figures --exclude=data --exclude=lit_extracted --exclude=__pycache__ .
# 2) base64 分片下发 → 服务器 base64 -d | tar xzf
```

服务器端校验：`sha256sum payload.tgz` 必须与本机一致，再解包。

---

## 3. 日常更新（一条命令）

服务器上：

```bash
bash /opt/litagent/deploy/update_litagent.sh
```

它会：备份 `data/platform.db` → `git pull` → `docker compose up -d --build` → 健康检查。
**不会**动 `data/`，导入和计算结果都不丢。

**VPC 内网实例（无 GitHub 通道）**：服务器上 `git pull` 用不了，改成两步——

```bash
# 1) 本机：重新打包并分片下发（见 §2.4），服务器解包覆盖 /opt/litagent
# 2) 服务器：重建 + 灌库 + 重启（备份、自动健康检查）
bash /opt/litagent/deploy/update_alicloud_vpc.sh
```

---

## 4. 上线后验收清单

- [ ] `docker compose ps` → 状态 `Up`，`restart: unless-stopped` 生效
- [ ] `curl http://127.0.0.1:8501/_stcore/health` → `ok`
- [ ] 浏览器打开 `http://<公网IP>:8501`，标题为 **硫芯LitAgent：锂硫电池科研智能体**
- [ ] 首页均值卡片带 `(n=...)` 和 `±标准差`，低样本显示"样本不足"
- [ ] 场景选择器含"玄武岩纤维(BF)"与"LDH"，无"揭榜挂帅"
- [ ] Tab 切换正常，特别是 Tab9「模型版本」
- [ ] 数据源页显示液态 654 / 固态 600
- [ ] **持久化验证**：`docker compose restart` 后样本数不变
- [ ] 安全组只放行 22 / 8501，其他端口未误开

---

## 5. 依赖红线（改 Dockerfile/requirements 前必读）

| 项 | 要求 | 原因 |
|---|---|---|
| `xgboost` | **必须 ≥ 3.0.0** | 2.x 加载 3.x 训练的 UBJ 模型**不报错但预测全错**（实测 −12.5 vs 68.24） |
| `pandas` | **保持 3.x** | 代码已用 `is_numeric_dtype` 适配 pandas 3 的 `str` dtype，不要降到 2 |
| `streamlit` | 配置见 `.streamlit/config.toml` | `enableCORS=false`、`maxUploadSize=50`、`headless=true` |
| `Python` | 3.11（镜像 `python:3.11-slim`） | 与生产实测环境一致 |

---

## 6. 故障排查

| 现象 | 检查 |
|---|---|
| 容器起不来 | `docker compose logs --tail 100 bf-platform` |
| 健康检查不过 | `curl -v http://127.0.0.1:8501/_stcore/health` |
| 端口没监听 | `ss -tlnp | grep 8501` |
| 浏览器打不开 | ① 安全组 8501 规则 ② 容器在跑 ③ 服务器本地 curl 通不通 |
| 样本数为 0 | 灌库没跑或路径不对：`docker run --rm --entrypoint python -v /opt/litagent:/repo -w /repo -e BF_DB_PATH=/repo/data/platform.db bf-platform:latest tools/seed_db.py` |
| 数据疑似丢失 | `ls -l /opt/litagent/data/`；备份在 `/opt/litagent/backups/` |

---

## 7. 备份与回滚

```bash
# 备份
tar czf /opt/litagent/backups/data-$(date +%Y%m%d).tar.gz -C /opt/litagent data

# 回滚代码到上一个版本
cd /opt/litagent && git log --oneline -5
git checkout <上一个 commit> && bash deploy/update_litagent.sh
```

> VPC 内网实例没有 GitHub 通道，回滚 = 从本机把旧版本重新打包下发（§2.4），
> 再跑 `deploy/update_alicloud_vpc.sh`；数据库回滚用 `backups/platform.db.<时间戳>`。

---

## 8. 后续可做

- 域名 + HTTPS：Nginx 反代 80/443 + certbot（需 ICP 备案）
- 定时备份：`cron` 每日 `tar` 打包 `data/`
- agent 上线：代码在 `agent/`，本次未部署，平台稳定后再单独安排
