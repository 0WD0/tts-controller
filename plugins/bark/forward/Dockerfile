FROM python:3.9-slim

WORKDIR /app

# 安装基本依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app/ app/

# 设置环境变量
ENV PYTHONUNBUFFERED=1

CMD ["python", "app/main.py"]
