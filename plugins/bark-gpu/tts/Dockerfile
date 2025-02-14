FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 安装 Python 和基本依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3.9 \
        python3-pip \
        python3.9-venv \
        curl \
        git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 创建并激活虚拟环境
RUN python3.9 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app/ app/

CMD ["python", "app/main.py"]
