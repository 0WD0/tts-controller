# TTS Service Management System

一个基于 Docker 的 TTS（文本转语音）服务管理系统，支持动态加载和管理多个 TTS 引擎。

## 功能特点

- 动态加载/卸载 TTS 引擎
- 基于 Docker 的插件化架构
- RESTful API 接口
- 支持多种 TTS 引擎（Coqui-TTS, Bark 等）
- 自动化的服务发现和健康检查
- 容器化部署和管理

## 系统架构

系统由以下主要组件构成：

1. **Controller Service**：
   - 核心控制服务
   - 管理 TTS 插件的生命周期
   - 提供 RESTful API 接口
   - 处理服务发现和健康检查

2. **Plugin System**：
   - 基于 Docker 的插件化系统
   - 每个 TTS 引擎作为独立插件
   - 支持动态加载和卸载
   - 配置文件驱动的插件管理

## 快速开始

### 前置要求

- Docker
- Docker Compose
- Python 3.9+

### 安装

1. 克隆仓库：
```bash
git clone <repository-url>
cd tts-service
```

2. 构建服务：
```bash
docker compose build
```

3. 启动服务：
```bash
docker compose up -d
```

### 使用方法

1. 加载 TTS 服务：
```bash
curl -X POST http://localhost:8000/api/servers/<engine-name>/load
```

2. 卸载 TTS 服务：
```bash
curl -X POST http://localhost:8000/api/servers/<engine-name>/unload
```

3. 查看服务状态：
```bash
curl http://localhost:8000/api/servers/<engine-name>/status
```

## 添加新的 TTS 引擎

1. 在 `plugins` 目录下创建新的插件目录
2. 创建 `config.yaml` 配置文件：
```yaml
image: your-tts-image:tag
environment:
  MODEL_NAME: your-model
  DEVICE: cuda
volumes:
  - /data/models:/app/models
  - /data/cache:/app/cache
ports:
  8001: 8000  # host_port: container_port
```

## API 文档

### 服务管理 API

- `POST /api/servers/{name}/load` - 加载指定的 TTS 服务
- `POST /api/servers/{name}/unload` - 卸载指定的 TTS 服务
- `GET /api/servers/{name}/status` - 获取服务状态
- `GET /api/servers` - 获取所有服务列表

## 配置说明

### 主配置文件

`config.yml` 包含以下配置：

```yaml
tts_servers:
  coqui:
    name: coqui-tts
    type: coqui
    image: coqui-tts
    enabled: true
    supported_languages: 
      - en
      - zh
      - ja
  bark:
    name: bark-tts
    type: bark
    image: bark-tts
    enabled: true
    supported_languages:
      - en
      - zh

controller:
  host: 0.0.0.0
  port: 8000
  health_check_interval: 60

forward_server:
  timeout: 30
  retry_count: 3
```

### 插件配置

每个插件目录下的 `config.yaml` 定义了插件的具体配置：

```yaml
image: tts-engine:latest
environment:
  MODEL_NAME: model-name
  DEVICE: cuda
volumes:
  - /data/models:/app/models
  - /data/cache:/app/cache
ports:
  8001: 8000  # host_port: container_port
```

## 开发指南

### 项目结构

```
.
├── docker-compose.yml
├── README.md
├── tts-controller/
│   ├── app/
│   │   ├── main.py
│   │   └── server_manager.py
│   ├── Dockerfile
│   └── requirements.txt
└── plugins/
    ├── coqui/
    │   └── config.yaml
    └── bark/
        └── config.yaml
```

### 开发新功能

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 创建 Pull Request

## 许可证

[MIT License](LICENSE)
