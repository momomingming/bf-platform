#!/bin/bash
# 玻尔沙箱启动脚本：把平台跑在持久化个人盘 /data/litagent 上
# 沙箱销毁后重新创建并执行本脚本即可恢复服务（数据与模型不丢）。
set -e

APP_DIR=/data/litagent
ENVDIR=/opt/mamba/envs/li311
export BF_DB_PATH="$APP_DIR/data/platform.db"
export BF_MODELS_DIR="$APP_DIR/data/models"

if [ ! -x "$ENVDIR/bin/python" ]; then
  /opt/mamba/bin/mamba create -n li311 python=3.11 -y
  "$ENVDIR/bin/pip" install --index-url https://mirrors.aliyun.com/pypi/simple/ \
    numpy==2.4.6 pandas==3.1.1 xgboost==3.2.0 scikit-learn==1.7.2 \
    openpyxl==3.1.5 "plotly>=5.18.0" "kaleido>=0.2.1" "streamlit==1.67.0"
fi

mkdir -p "$BF_MODELS_DIR" /root/.streamlit
cp -f "$APP_DIR/.streamlit/config.toml" /root/.streamlit/config.toml

if [ ! -f "$BF_DB_PATH" ]; then
  cd "$APP_DIR" && "$ENVDIR/bin/python" tools/seed_db.py
fi

cd "$APP_DIR/lis_battery_platform"
exec "$ENVDIR/bin/streamlit" run app.py \
  --server.port 8501 --server.address 0.0.0.0 --server.headless true \
  --browser.gatherUsageStats false
