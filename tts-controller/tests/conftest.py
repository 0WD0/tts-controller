import pytest
import os
import tempfile
import yaml
import docker
from pathlib import Path
from unittest.mock import MagicMock

@pytest.fixture
def mock_docker_client():
    """模拟 Docker 客户端"""
    mock_client = MagicMock(spec=docker.DockerClient)
    return mock_client

@pytest.fixture
def temp_config_file():
    """创建临时配置文件"""
    config = {
        'tts_servers': {
            'bark': {'enabled': True},
            'coqui': {'enabled': True}
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        yaml.dump(config, f)
        config_path = f.name
    
    yield config_path
    
    # 清理临时文件
    os.unlink(config_path)

@pytest.fixture
def mock_plugin_dir(tmp_path):
    """创建模拟的插件目录结构"""
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    
    # 创建 bark 插件目录
    bark_dir = plugins_dir / "bark"
    bark_dir.mkdir()
    bark_compose = bark_dir / "docker-compose.yml"
    bark_compose.write_text("""
version: '3.8'
services:
  bark-tts:
    container_name: tts-bark
    image: tts-bark
    """)
    
    # 创建 coqui 插件目录
    coqui_dir = plugins_dir / "coqui"
    coqui_dir.mkdir()
    coqui_compose = coqui_dir / "docker-compose.yml"
    coqui_compose.write_text("""
version: '3.8'
services:
  coqui-tts:
    container_name: tts-coqui
    image: tts-coqui
    """)
    
    return plugins_dir

@pytest.fixture
def mock_subprocess(mocker):
    """模拟 subprocess 调用"""
    mock = mocker.patch('subprocess.run')
    mock.return_value.returncode = 0
    mock.return_value.stdout = "Success"
    return mock
