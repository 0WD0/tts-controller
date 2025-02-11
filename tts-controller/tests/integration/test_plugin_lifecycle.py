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
        manager = TTSServerManager(config_path)
        yield manager
        
        # 清理：确保所有插件都被停止
        for plugin_name in manager.plugins:
            manager.stop_plugin(plugin_name)
    
    def test_plugin_lifecycle(self, manager):
        """测试插件的完整生命周期"""
        plugin_name = "bark"  # 使用 bark 插件进行测试
        
        # 1. 确保插件最初是停止状态
        initial_status = manager.get_plugin_status(plugin_name)
        assert initial_status in ['stopped', None]
        
        # 2. 启动插件
        assert manager.start_plugin(plugin_name) is True
        time.sleep(5)  # 等待容器完全启动
        
        # 3. 验证插件状态
        status = manager.get_plugin_status(plugin_name)
        assert status == 'running'
        
        # 4. 检查容器是否真实运行
        plugin_info = manager.plugins[plugin_name]
        for container_name in plugin_info.containers:
            container = manager.docker_client.containers.get(container_name)
            assert container.status == 'running'
        
        # 5. 重启插件
        assert manager.restart_plugin(plugin_name) is True
        time.sleep(5)  # 等待容器重启
        
        # 6. 验证重启后状态
        status = manager.get_plugin_status(plugin_name)
        assert status == 'running'
        
        # 7. 停止插件
        assert manager.stop_plugin(plugin_name) is True
        time.sleep(2)  # 等待容器停止
        
        # 8. 验证停止状态
        status = manager.get_plugin_status(plugin_name)
        assert status == 'stopped'
        
    def test_multiple_plugins(self, manager):
        """测试多个插件的并发操作"""
        plugins = ['bark', 'coqui']
        
        # 1. 同时启动多个插件
        for plugin in plugins:
            assert manager.start_plugin(plugin) is True
        
        time.sleep(10)  # 等待所有容器启动
        
        # 2. 验证所有插件状态
        for plugin in plugins:
            status = manager.get_plugin_status(plugin)
            assert status == 'running'
        
        # 3. 获取所有插件信息
        all_plugins = manager.get_all_plugins()
        assert len(all_plugins) >= len(plugins)
        
        # 4. 停止所有插件
        for plugin in plugins:
            assert manager.stop_plugin(plugin) is True
            
        time.sleep(5)  # 等待所有容器停止
        
        # 5. 验证所有插件已停止
        for plugin in plugins:
            status = manager.get_plugin_status(plugin)
            assert status == 'stopped'
            
    def test_error_handling(self, manager):
        """测试错误处理"""
        # 1. 测试启动不存在的插件
        assert manager.start_plugin('nonexistent') is False
        
        # 2. 测试重启不存在的插件
        assert manager.restart_plugin('nonexistent') is False
        
        # 3. 测试获取不存在插件的状态
        assert manager.get_plugin_status('nonexistent') is None
        
        # 4. 测试加载不存在的服务器
        with pytest.raises(ValueError):
            manager.load_server('nonexistent')
