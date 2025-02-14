import docker
from typing import Dict, Optional, Union, Tuple, List
import logging
import os
from pathlib import Path
import yaml
from dataclasses import dataclass, field
from docker.errors import NotFound

# 配置日志记录
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class PluginInfo:
    name: str
    plugin_dir: Path
    image: str
    status: str = "stopped"
    container_name: str = ""
    environment: Dict[str, str] = field(default_factory=dict)
    volumes: Dict[str, Dict[str, str]] = field(default_factory=dict)  # 修改为字典格式
    ports: Dict[str, Union[int, None, Tuple[str, int], List[int]]] = field(default_factory=dict)  # 修改为字符串键

class TTSServerManager:
    def __init__(self, config_path: str, plugin_dir: str):
        self.config_path = config_path
        self.plugin_dir = plugin_dir
        self.plugins: Dict[str, PluginInfo] = {}
        logger.info(f"Initializing TTSServerManager with config path: {config_path}")
        
        # 检查Docker socket是否存在
        if not os.path.exists('/var/run/docker.sock'):
            logger.error("Docker socket not found at /var/run/docker.sock")
            raise RuntimeError("Docker socket not found")
            
        # 检查Docker socket权限
        try:
            socket_stat = os.stat('/var/run/docker.sock')
            logger.debug(f"Docker socket permissions: {oct(socket_stat.st_mode)}")
            logger.debug(f"Docker socket owner: {socket_stat.st_uid}")
            logger.debug(f"Docker socket group: {socket_stat.st_gid}")
        except Exception as e:
            logger.error(f"Failed to check Docker socket permissions: {e}")
            
        try:
            logger.debug("Attempting to initialize Docker client...")
            self.docker_client = docker.from_env()
            logger.info("Docker client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            raise
            
        self.load_config()
        self.scan_plugins()
        
    def load_config(self):
        """加载配置文件"""
        logger.info(f"Loading configuration from {self.config_path}")
        try:
            with open(self.config_path) as f:
                self.config = yaml.safe_load(f)
            logger.debug(f"Loaded configuration: {self.config}")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise

    def scan_plugins(self):
        """扫描插件目录，查找可用的TTS插件"""
        logger.info("Scanning for TTS plugins...")
        try:
            plugins_dir = Path(self.plugin_dir)
            for plugin_dir in plugins_dir.iterdir():
                if not plugin_dir.is_dir():
                    continue
                    
                config_file = plugin_dir / "config.yaml"
                if not config_file.exists():
                    logger.warning(f"No config.yaml found in {plugin_dir}")
                    continue
                    
                try:
                    with open(config_file) as f:
                        config = yaml.safe_load(f)
                        
                    # 检查是否是 GPU 版本
                    is_gpu = "gpu" in plugin_dir.name.lower()
                    plugin_name = plugin_dir.name.replace("-gpu", "") if is_gpu else plugin_dir.name
                    
                    # 创建插件信息
                    plugin = PluginInfo(
                        name=plugin_name,
                        plugin_dir=plugin_dir,
                        image=config.get("image", ""),
                        container_name=f"tts-{plugin_dir.name}",
                        environment=config.get("environment", {}),
                        volumes=config.get("volumes", {}),
                        ports=config.get("ports", {})
                    )
                    
                    self.plugins[plugin_dir.name] = plugin
                    logger.info(f"Found plugin: {plugin_dir.name} ({plugin.image})")
                    
                except Exception as e:
                    logger.error(f"Error loading plugin config from {config_file}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error scanning plugins directory: {e}")

    def _ensure_network(self):
        """确保 TTS 网络存在"""
        try:
            self.docker_client.networks.get("tts-network")
        except NotFound:
            self.docker_client.networks.create("tts-network", driver="bridge")

    def start_plugin(self, plugin_name: str) -> bool:
        """启动指定的插件"""
        logger.info(f"Starting plugin: {plugin_name}")
        if plugin_name not in self.plugins:
            logger.error(f"Plugin {plugin_name} not found")
            return False

        plugin = self.plugins[plugin_name]
        try:
            # 确保网络存在
            self._ensure_network()

            # 检查并移除已存在的同名容器
            try:
                container = self.docker_client.containers.get(plugin.container_name)
                logger.info(f"Found existing container {plugin.container_name}, removing it...")
                container.remove(force=True)
            except NotFound:
                pass

            # 创建并启动容器
            container = self.docker_client.containers.run(
                image=plugin.image,
                name=plugin.container_name,
                detach=True,
                environment=plugin.environment,
                volumes=plugin.volumes,
                ports=plugin.ports,  # 直接使用转换后的端口配置
                network="tts-network"
            )

            plugin.status = "running"
            logger.info(f"Plugin {plugin_name} started successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to start plugin {plugin_name}: {e}")
            return False

    def stop_plugin(self, plugin_name: str) -> bool:
        """停止指定的插件"""
        logger.info(f"Stopping plugin: {plugin_name}")
        if plugin_name not in self.plugins:
            logger.error(f"Plugin {plugin_name} not found")
            return False

        plugin = self.plugins[plugin_name]
        try:
            try:
                container = self.docker_client.containers.get(plugin.container_name)
                container.stop()
                container.remove()
                logger.info(f"Container {plugin.container_name} stopped and removed")
            except NotFound:
                logger.info(f"Container {plugin.container_name} not found")

            plugin.status = "stopped"
            return True
        except Exception as e:
            logger.error(f"Failed to stop plugin {plugin_name}: {e}")
            return False

    def restart_plugin(self, plugin_name: str) -> Dict:
        """重启指定的插件"""
        logger.info(f"Restarting plugin: {plugin_name}")
        if plugin_name not in self.plugins:
            logger.error(f"Plugin {plugin_name} not found")
            raise ValueError(f"Plugin {plugin_name} not found")

        if not self.stop_plugin(plugin_name):
            logger.error(f"Failed to stop plugin: {plugin_name}")
            raise RuntimeError(f"Failed to stop plugin: {plugin_name}")

        if not self.start_plugin(plugin_name):
            logger.error(f"Failed to start plugin: {plugin_name}")
            raise RuntimeError(f"Failed to start plugin: {plugin_name}")

        return {
            "server_type": plugin_name,
            "status": "restarted",
            "plugin_info": self.plugins[plugin_name]
        }

    def get_plugin_status(self, plugin_name: str) -> Optional[str]:
        """获取插件状态"""
        if plugin_name not in self.plugins:
            return None
        
        plugin = self.plugins[plugin_name]
        try:
            container = self.docker_client.containers.get(plugin.container_name)
            status = container.status
            plugin.status = status
            return status
        except NotFound:
            plugin.status = "stopped"
            return "stopped"
        except Exception as e:
            logger.error(f"Failed to get plugin status: {e}")
            return "unknown"

    def get_all_plugins(self) -> Dict[str, Dict]:
        """获取所有插件的信息"""
        result = {}
        for name, plugin in self.plugins.items():
            status = self.get_plugin_status(name)
            result[name] = {
                "status": status,
                "image": plugin.image,
                "container_name": plugin.container_name,
                "environment": plugin.environment,
                "volumes": plugin.volumes,
                "ports": plugin.ports
            }
        return result

    def load_server(self, server_type: str) -> Dict:
        """加载指定的TTS服务器"""
        logger.info(f"Loading server: {server_type}")
        if server_type not in self.plugins:
            logger.error(f"Unknown server type: {server_type}")
            raise ValueError(f"Unknown server type: {server_type}")

        logger.info(f"Starting load server: {server_type}")
        if not self.start_plugin(server_type):
            raise RuntimeError(f"Failed to start plugin: {server_type}")

        return {
            'server_type': server_type,
            'status': 'loaded',
            'plugin_info': self.plugins[server_type]
        }

    def unload_server(self, server_type: str) -> Dict:
        """卸载指定的TTS服务器"""
        logger.info(f"Unloading server: {server_type}")
        if server_type not in self.plugins:
            logger.error(f"Unknown server type: {server_type}")
            raise ValueError(f"Unknown server type: {server_type}")

        if not self.stop_plugin(server_type):
            logger.error(f"Failed to stop plugin: {server_type}")
            return {'status': 'error', 'server_type': server_type}

        return {
            'status': 'unloaded',
            'server_type': server_type
        }

    def get_server_status(self, server_type: str) -> Dict:
        """获取服务器状态"""
        logger.info(f"Getting server status: {server_type}")
        if server_type not in self.plugins:
            logger.error(f"Unknown server type: {server_type}")
            raise ValueError(f"Unknown server type: {server_type}")

        status = self.get_plugin_status(server_type)
        return {
            'server_type': server_type,
            'status': status
        }
