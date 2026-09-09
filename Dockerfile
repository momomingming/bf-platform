FROM python:3.11-slim

LABEL maintainer="momomingming"
LABEL description="Li-S battery basalt fiber ML prediction platform"

# System deps (curl for healthcheck, gcc as fallback for compiled wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps first (better layer caching)
COPY lis_battery_platform/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir -r requirements.txt

# App code
COPY lis_battery_platform/ ./

# Streamlit server config
RUN mkdir -p /root/.streamlit
COPY .streamlit/config.toml /root/.streamlit/config.toml

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

ENV STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

ENTRYPOINT ["streamlit", "run", "app.py"]
