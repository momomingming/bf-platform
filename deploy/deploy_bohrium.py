"""在玻尔沙箱上部署硫芯LitAgent 平台（一条命令重建 + 拿到公网地址）。

用法：
    python deploy_bohrium.py                 # 用默认模板创建常驻沙箱并启动
    python deploy_bohrium.py --template scicomp-4090
    python deploy_bohrium.py --kill default--scicomp-ml-xxxx   # 销毁沙箱

数据与模型落在沙箱挂载的个人盘 /data/litagent（跨沙箱持久），
所以重建沙箱只需重跑 start.sh，不需要重新上传代码或重新灌库。
"""
import argparse
import json
import subprocess
import sys
import time

HERE = __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0]
BHR = f"{HERE}/bhr.py"
DOMAIN = "bohr-sandbox.bohrium.com"
START_SH = f"{HERE}/start_bf_platform.sh"


def bhr(*args, check=True):
    cmd = [sys.executable, BHR] + list(args)
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and p.returncode != 0:
        raise SystemExit(f"sdbx {' '.join(args)} failed:\n{p.stdout}\n{p.stderr}")
    return p.stdout


def bhr_json(*args):
    return json.loads(bhr(*args))


def public_url(sandbox_id, port=8501):
    return f"https://{port}-{sandbox_id}.{DOMAIN}"


def wait_http(url, timeout=420):
    import urllib.request
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url + "/_stcore/health", timeout=10) as r:
                if r.status == 200 and r.read().decode().strip() == "ok":
                    return True
                last = f"http {r.status}"
        except Exception as exc:  # noqa: BLE001
            last = str(exc)[:120]
        time.sleep(10)
    print(f"[warn] health check not green yet: {last}")
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", default="scicomp-ml")
    ap.add_argument("--timeout", default="0", help="0 = 不限时（常驻，按量计费）")
    ap.add_argument("--kill", default=None, help="销毁指定 sandbox_id")
    args = ap.parse_args()

    if args.kill:
        bhr("kill", args.kill, "--force", "--json")
        print(f"killed {args.kill}")
        return

    info = bhr_json("create", args.template, "--timeout", args.timeout,
                    "--mount-user-storage", "--json")
    sid = info["sandboxID"]
    print(f"sandbox: {sid}")
    print(f"public url: {public_url(sid)}")

    bhr("files", "write", "--source", START_SH, sid, "/data/litagent/start.sh", "--json")
    # 首次启动要建 py3.11 环境（mamba + pip，约 5~6 分钟），给足等待时间
    bhr("exec", "--background", sid,
        "mkdir -p /root/out && /data/litagent/start.sh > /root/out/start.log 2>&1")

    ok = wait_http(public_url(sid), timeout=900)
    print("health:", "ok" if ok else "check manually")
    print(public_url(sid))


if __name__ == "__main__":
    main()
