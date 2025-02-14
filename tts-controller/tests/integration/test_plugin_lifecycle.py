import pytest
import time
from pathlib import Path
from app.server_manager import TTSServerManager

@pytest.mark.integration
class TestPluginLifecycle:
    
    @pytest.fixture(scope="class")
    def manager(self):
        """创建真实的 TTSServerManager 实例"""
        config_path = "/config/config.yml"
        plugin_dir = "/plugins"
        manager = TTSServerManager(config_path, plugin_dir)
        yield manager
        
        # 清理：确保所有插件都被停止
        for plugin_name in manager.plugins:
            manager.stop_plugin(plugin_name)
    
    def test_plugin_lifecycle(self, manager):
        """测试插件的完整生命周期"""
        # 测试 CPU 版本
        self._test_plugin_lifecycle(manager, "bark")
        # 测试 GPU 版本（如果可用）
        if "bark-gpu" in manager.plugins:
            self._test_plugin_lifecycle(manager, "bark-gpu")
    
    def _test_plugin_lifecycle(self, manager, plugin_name):
        """测试单个插件的生命周期"""
        # 1. 确保插件最初是停止状态
        initial_status = manager.get_plugin_status(plugin_name)
        assert initial_status in ['stopped', None]

        # 2. 启动插件
        result = manager.start_plugin(plugin_name)
        assert result is True

        # 3. 检查插件状态
        status = manager.get_plugin_status(plugin_name)
        assert status == 'running'

        # 4. 检查健康状态
        health = manager.check_plugin_health(plugin_name)
        assert health['status'] == 'healthy'
        if 'gpu' in plugin_name:
            assert 'device' in health
            assert health['device'] == 'cuda'
        else:
            assert health.get('device', 'cpu') == 'cpu'

        # 5. 停止插件
        stop_result = manager.stop_plugin(plugin_name)
        assert stop_result is True

        # 6. 最后检查状态
        final_status = manager.get_plugin_status(plugin_name)
        assert final_status == 'stopped'

    def test_multiple_plugins(self, manager):
        """测试多个插件的并发操作"""
        plugins = ['bark', 'coqui']

        # 1. 同时启动多个插件
        for plugin in plugins:
            result = manager.start_plugin(plugin)
            assert result is True

            # 验证插件状态
            status = manager.get_plugin_status(plugin)
            assert status == 'running'

        # 2. 检查所有插件信息
        all_plugins = manager.get_all_plugins()
        for plugin in plugins:
            assert plugin in all_plugins
            assert all_plugins[plugin]['status'] == 'running'

        # 3. 停止所有插件
        for plugin in plugins:
            result = manager.stop_plugin(plugin)
            assert result is True

            # 验证插件已停止
            status = manager.get_plugin_status(plugin)
            assert status == 'stopped'

    def test_error_handling(self, manager):
        """测试错误处理"""
        # 1. 测试启动不存在的插件
        result = manager.start_plugin('nonexistent')
        assert result is False

        # 2. 测试停止不存在的插件
        result = manager.stop_plugin('nonexistent')
        assert result is False

        # 3. 测试获取不存在插件的状态
        status = manager.get_plugin_status('nonexistent')
        assert status is None

        # 4. 测试重启不存在的插件
        with pytest.raises(ValueError):
            manager.restart_plugin('nonexistent')

        # 5. 测试加载不存在的服务器
        with pytest.raises(ValueError):
            manager.load_server('nonexistent')
