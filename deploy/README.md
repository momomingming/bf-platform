# Windows 部署脚本

> 适用：Windows Server 2019/2022 + 宝塔面板 + 2GB 内存
> 目的：把锂硫电池平台（bf-platform）跑成 Windows 服务，长期可访问

## 一次性部署

通过宝塔面板的"终端"或远程桌面 PowerShell（管理员权限）执行：

```powershell
# 1. 克隆代码
cd C:\apps
git clone https://github.com/momomingming/bf-platform.git
cd bf-platform

# 2. 跑部署脚本（首次会自动装 Python + nssm + 依赖 + 注册服务）
powershell -ExecutionPolicy Bypass -File deploy\deploy.ps1
```

全程 5-10 分钟。完成后访问 `http://82.156.43.223:8501`。

## 日常更新

```powershell
cd C:\apps\bf-platform
git pull
nssm restart BFPlatform
# 或者（重启服务）
nssm stop BFPlatform && nssm start BFPlatform
```

## 常用操作

| 需求 | 命令 |
|------|------|
| 查看服务状态 | `nssm status BFPlatform` 或 `Get-Service BFPlatform` |
| 重启服务 | `nssm restart BFPlatform` |
| 停止服务 | `nssm stop BFPlatform` |
| 查看日志 | `Get-Content C:\apps\bf-platform\logs\streamlit.log -Tail 50` |
| 查错日志 | `Get-Content C:\apps\bf-platform\logs\streamlit.err.log -Tail 50` |
| 完全卸载 | `nssm stop BFPlatform; nssm remove BFPlatform confirm` |

## 防火墙

Lighthouse 防火墙（已在腾讯云层面开 8501）和 Windows 防火墙需要同时开：

```powershell
New-NetFirewallRule -DisplayName "Streamlit 8501" -Direction Inbound -Protocol TCP -LocalPort 8501 -Action Allow -Profile Any
```

## 内存提示

2GB 内存紧张，模型训练时会卡（XGBoost 跑满 650 条数据约 1-2 分钟）。
**应对**：避免同时开宝塔面板的"网站监控"等高内存插件。

## 进阶：加 HTTPS + 域名

在宝塔面板里建网站 → 反向代理 127.0.0.1:8501 → 申请 Let's Encrypt 证书。
