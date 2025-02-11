import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import docker
import pytest
import yaml
from docker.errors import NotFound

from app.server_manager import TTSServerManager, PluginInfo

@pytest.mark.unit
class TestTTSServerManager:
    
    @pytest.fixture
    def manager(self, temp_config_file, mock_docker_client, mock_plugin_dir, monkeypatch):
        """创建 TTSServerManager 实例"""
        # 模拟 docker.from_env()
        monkeypatch.setattr('docker.from_env', lambda: mock_docker_client)
        
        # 创建 TTSServerManager 实例
        manager = TTSServerManager(temp_config_file)
        
        # 直接设置 plugin_dir 属性
        manager.plugin_dir = mock_plugin_dir
        
        return manager

    def test_init(self, manager):
        """测试初始化"""
        assert manager is not None
        assert hasattr(manager, 'docker_client')
        assert hasattr(manager, 'plugins')
        
    def test_scan_plugins(self, manager):
        """测试插件扫描"""
        # 验证是否找到了所有插件
        assert 'bark' in manager.plugins
        assert 'coqui' in manager.plugins
        
        # 验证插件信息是否正确
        bark_plugin = manager.plugins['bark']
        assert isinstance(bark_plugin, PluginInfo)
        assert bark_plugin.name == 'bark'
        assert bark_plugin.status == 'stopped'
        
    def test_start_plugin(self, manager, mock_docker_client):
        """测试启动插件"""
        # 模拟容器状态
        mock_container = MagicMock()
        mock_container.status = 'running'
        mock_docker_client.containers.get.return_value = mock_container
        mock_docker_client.containers.run.return_value = mock_container
        
        # 测试启动存在的插件
        assert manager.start_plugin('bark') is True
        
        # 测试启动不存在的插件
        assert manager.start_plugin('nonexistent') is False
        
    def test_stop_plugin(self, manager, mock_docker_client):
        """测试停止插件"""
        # 模拟容器状态
        mock_container = MagicMock()
        mock_container.status = 'running'
        mock_docker_client.containers.get.return_value = mock_container
        
        # 测试停止存在的插件
        assert manager.stop_plugin('bark') is True
        
        # 测试停止不存在的插件
        assert manager.stop_plugin('nonexistent') is False
        
    def test_get_plugin_status(self, manager, mock_docker_client):
        """测试获取插件状态"""
        # 模拟容器状态
        mock_container = MagicMock()
        mock_container.status = 'running'
        mock_docker_client.containers.get.return_value = mock_container
        
        # 测试运行中的插件
        assert manager.get_plugin_status('bark') == 'running'
        
        # 模拟容器不存在的情况
        mock_docker_client.containers.get.side_effect = NotFound("Container not found")
        assert manager.get_plugin_status('bark') == 'stopped'
        
        # 测试不存在的插件
        assert manager.get_plugin_status('nonexistent') is None
        
    def test_get_all_plugins(self, manager, mock_docker_client):
        """测试获取所有插件信息"""
        # 模拟容器状态
        mock_container = MagicMock()
        mock_container.status = 'running'
        mock_docker_client.containers.get.return_value = mock_container
        
        plugins = manager.get_all_plugins()
        assert len(plugins) == 2
        assert 'bark' in plugins
        assert 'coqui' in plugins
        assert plugins['bark']['status'] == 'running'
        
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
        # 模拟成功停止插件
        with patch.object(manager, 'stop_plugin', return_value=True):
            result = manager.unload_server('bark')
            assert isinstance(result, dict)
            assert result['status'] == 'unloaded'
            assert result['server_type'] == 'bark'
            # 验证 stop_plugin 被调用
            manager.stop_plugin.assert_called_once_with('bark')
        
        # 测试卸载不存在的服务器
        with pytest.raises(ValueError):
            manager.unload_server('nonexistent')
        
        # 测试停止失败的情况
        with patch.object(manager, 'stop_plugin', return_value=False):
            result = manager.unload_server('bark')
            assert isinstance(result, dict)
            assert result['status'] == 'error'
            assert result['server_type'] == 'bark'
