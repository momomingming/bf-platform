# 部署指南 · 锂硫电池平台

> 目标：让本平台在腾讯云 Lighthouse 上长期可访问、可更新、可扩展。

## 1. 前置条件

- 腾讯云 Lighthouse 实例（Ubuntu 22.04 推荐，2C2G 配置即可）
- 实例已放通 TCP 8501 端口（或通过 Nginx 反代 80/443）
- 本机有 Git、Docker 客户端

## 2. 一次性初始化服务器

```bash
# SSH 登录
ssh root@<LIGHTHOUSE_IP>

# 安装 Docker
apt-get update
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

## 3. 部署应用

```bash
# 克隆代码
mkdir -p /opt && cd /opt
git clone https://github.com/momomingming/bf-platform.git
cd bf-platform

# 构建并后台启动
docker compose up -d --build

# 验证
docker compose ps
docker compose logs -f bf-platform
curl http://127.0.0.1:8501/_stcore/health
```

完成后访问 `http://<LIGHTHOUSE_IP>:8501`。

## 4. 配置 HTTPS + 域名（推荐）

```bash
apt-get install -y nginx certbot python3-certbot-nginx

cat > /etc/nginx/sites-available/bf-platform <<'EOF'
server {
    listen 80;
    server_name your.domain.com;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400;
    }
}
EOF

ln -s /etc/nginx/sites-available/bf-platform /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

certbot --nginx -d your.domain.com
```

## 5. 日常更新流程

**本地修改 → 推送：**
```bash
git add .
git commit -m "update: ..."
git push
```

**服务器拉取 → 重启：**
```bash
ssh root@<LIGHTHOUSE_IP>
cd /opt/bf-platform
git pull
docker compose up -d --build
docker image prune -f
```

## 6. 数据备份

Phase 2 启用数据库后，数据将存放在 `./data/` 目录：
```bash
# 备份
tar czf /backup/bf-platform-$(date +%Y%m%d).tar.gz data/

# 恢复
cd /opt/bf-platform
tar xzf /backup/bf-platform-YYYYMMDD.tar.gz
docker compose restart bf-platform
```

## 7. 故障排查

| 现象 | 检查点 |
|------|--------|
| 启动失败 | `docker compose logs bf-platform` 看 Python 报错 |
| 端口没起来 | `ss -tlnp \| grep 8501` |
| 502 Bad Gateway | Nginx 配错了，先 `nginx -t`，再 `systemctl status nginx` |
| 应用报 401/CORS | `.streamlit/config.toml` 里 CORS 设置 |
| 健康检查失败 | `curl -v http://127.0.0.1:8501/_stcore/health` |

## 8. 升级路径（Phase 2+ 准备）

- Phase 1（当前）：只跑 `lis_battery_platform/`，数据用合成 CSV
- Phase 2：启用 SQLite 数据库，加数据录入页
- Phase 3：计算逻辑参数化，模型缓存

升级时只需改 `docker-compose.yml` 挂载 `./data:/app/data` 并改 `Dockerfile` COPY 范围，向后兼容。
