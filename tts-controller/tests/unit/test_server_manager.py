import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from docker.errors import NotFound
from app.server_manager import TTSServerManager, PluginInfo

@pytest.fixture
def manager(temp_config_file, mock_docker_client, mock_plugin_dir, monkeypatch):
    """创建 TTSServerManager 实例"""
    # 模拟 docker.from_env()
    monkeypatch.setattr('docker.from_env', lambda: mock_docker_client)
    
    # 创建 TTSServerManager 实例
    manager = TTSServerManager(temp_config_file, mock_plugin_dir)
    return manager

class TestTTSServerManager:
    """TTSServerManager 单元测试"""

    def test_init(self, manager):
        """测试初始化"""
        assert isinstance(manager, TTSServerManager)
        assert manager.plugins is not None
        assert len(manager.plugins) > 0

    def test_scan_plugins(self, manager):
        """测试扫描插件"""
        # 测试扫描已知插件
        plugins = manager.plugins
        assert 'bark' in plugins
        assert 'bark-gpu' in plugins
        assert 'coqui' in plugins

        # 验证 CPU 版本插件信息
        bark_plugin = plugins['bark']
        assert bark_plugin.name == 'bark'
        assert bark_plugin.image is not None
        assert bark_plugin.container_name == 'tts-bark'
        assert bark_plugin.environment.get('DEVICE') == 'cpu'

        # 验证 GPU 版本插件信息
        bark_gpu_plugin = plugins['bark-gpu']
        assert bark_gpu_plugin.name == 'bark'
        assert bark_gpu_plugin.image is not None
        assert bark_gpu_plugin.container_name == 'tts-bark-gpu'
        assert bark_gpu_plugin.environment.get('DEVICE') == 'cuda'

    def test_start_plugin(self, manager, mock_docker_client):
        """测试启动插件"""
        # 测试 CPU 版本
        result = manager.start_plugin('bark')
        assert result is True
        
        # 测试 GPU 版本
        if 'bark-gpu' in manager.plugins:
            result = manager.start_plugin('bark-gpu')
            assert result is True

    def test_plugin_health_check(self, manager):
        """测试插件健康检查"""
        # 测试 CPU 版本健康检查
        health = manager.check_plugin_health('bark')
        assert health['status'] == 'healthy'
        assert health.get('device', 'cpu') == 'cpu'

        # 测试 GPU 版本健康检查
        if 'bark-gpu' in manager.plugins:
            health = manager.check_plugin_health('bark-gpu')
            assert health['status'] == 'healthy'
            assert health['device'] == 'cuda'
            assert 'gpu_name' in health

    def test_stop_plugin(self, manager, mock_docker_client):
        """测试停止插件"""
        # 模拟容器状态
        mock_container = MagicMock()
        mock_container.status = 'running'
        mock_docker_client.containers.get.return_value = mock_container

        # 测试停止存在的插件
        result = manager.stop_plugin('bark')
        assert result is True

        # 测试停止不存在的插件
        result = manager.stop_plugin('nonexistent')
        assert result is False

    def test_get_plugin_status(self, manager, mock_docker_client):
        """测试获取插件状态"""
        # 模拟容器状态
        mock_container = MagicMock()
        mock_container.status = 'running'
        mock_docker_client.containers.get.return_value = mock_container

        # 测试获取存在的插件状态
        status = manager.get_plugin_status('bark')
        assert status == 'running'

        # 测试容器不存在的情况
        mock_docker_client.containers.get.side_effect = NotFound('Container not found')
        status = manager.get_plugin_status('bark')
        assert status == 'stopped'

        # 测试获取不存在的插件状态
        status = manager.get_plugin_status('nonexistent')
        assert status is None

    def test_get_all_plugins(self, manager):
        """测试获取所有插件信息"""
        plugins = manager.get_all_plugins()
        assert isinstance(plugins, dict)
        assert len(plugins) > 0
        assert 'bark' in plugins
        assert 'bark-gpu' in plugins
        assert 'coqui' in plugins

        # 验证插件信息格式
        for plugin_info in plugins.values():
            assert 'container_name' in plugin_info
            assert 'status' in plugin_info
            assert 'image' in plugin_info

    def test_load_server(self, manager):
        """测试加载服务器"""
        # 模拟成功启动插件
        with patch.object(manager, 'start_plugin', return_value=True):
            result = manager.load_server('bark')
            assert isinstance(result, dict)
            assert result['status'] == 'loaded'
            assert result['server_type'] == 'bark'
            assert 'plugin_info' in result

        # 测试加载不存在的服务器
        with pytest.raises(ValueError):
            manager.load_server('nonexistent')

        # 测试启动失败的情况
        with patch.object(manager, 'start_plugin', return_value=False):
            with pytest.raises(RuntimeError):
                manager.load_server('bark')

    def test_restart_plugin(self, manager, mock_docker_client):
        """测试重启插件"""
        # 模拟容器状态
        mock_container = MagicMock()
        mock_container.status = 'running'
        mock_docker_client.containers.get.return_value = mock_container

        # 测试重启存在的插件
        with patch.object(manager, 'stop_plugin', return_value=True), \
             patch.object(manager, 'start_plugin', return_value=True):
            result = manager.restart_plugin('bark')
            assert isinstance(result, dict)
            assert result['status'] == 'restarted'
            assert result['server_type'] == 'bark'
            assert 'plugin_info' in result

        # 测试重启不存在的插件
        with pytest.raises(ValueError):
            manager.restart_plugin('nonexistent')

    def test_unload_server(self, manager):
        """测试卸载服务器"""
        # 测试卸载存在的服务器
        with patch.object(manager, 'stop_plugin', return_value=True):
            result = manager.unload_server('bark')
            assert isinstance(result, dict)
            assert result['status'] == 'unloaded'
            assert result['server_type'] == 'bark'

        # 测试卸载不存在的服务器
        with pytest.raises(ValueError):
            manager.unload_server('nonexistent')

        # 测试停止失败的情况
        with patch.object(manager, 'stop_plugin', return_value=False):
            result = manager.unload_server('bark')
            assert isinstance(result, dict)
            assert result['status'] == 'error'
            assert result['server_type'] == 'bark'
