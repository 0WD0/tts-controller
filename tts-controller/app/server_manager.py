import docker
from typing import Dict, Optional, List
import logging
import os
from pathlib import Path
import yaml
from dataclasses import dataclass, field

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
    volumes: List[str] = field(default_factory=list)
    ports: Dict[int, int] = field(default_factory=dict)

class TTSServerManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
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
            
        self.port_manager = PortManager(start_port=5000)
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
        plugins_dir = Path("/plugins")
        if not plugins_dir.exists():
            logger.error("Plugins directory not found")
            return

        for plugin_dir in plugins_dir.iterdir():
            if not plugin_dir.is_dir():
                continue

            config_file = plugin_dir / "config.yaml"
            if config_file.exists():
                try:
                    with open(config_file) as f:
                        plugin_config = yaml.safe_load(f)
                    
                    plugin_name = plugin_dir.name
                    self.plugins[plugin_name] = PluginInfo(
                        name=plugin_name,
                        plugin_dir=plugin_dir,
                        image=plugin_config['image'],
                        container_name=f"tts-{plugin_name}",
                        environment=plugin_config.get('environment', {}),
                        volumes=plugin_config.get('volumes', []),
                        ports=plugin_config.get('ports', {})
                    )
                    logger.info(f"Found plugin: {plugin_name} at {plugin_dir}")
                except Exception as e:
                    logger.error(f"Failed to load plugin config for {plugin_dir}: {e}")

    def _ensure_network(self):
        """确保 TTS 网络存在"""
        try:
            self.docker_client.networks.get("tts-network")
        except docker.errors.NotFound:
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

            # 创建并启动容器
            container = self.docker_client.containers.run(
                image=plugin.image,
                name=plugin.container_name,
                detach=True,
                environment=plugin.environment,
                volumes=plugin.volumes,
                ports={f"{container}/tcp": host for container, host in plugin.ports.items()},
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
            except docker.errors.NotFound:
                logger.warning(f"Container {plugin.container_name} not found")

            plugin.status = "stopped"
            return True
        except Exception as e:
            logger.error(f"Failed to stop plugin {plugin_name}: {e}")
            return False

    def restart_plugin(self, plugin_name: str) -> bool:
        """重启指定的插件"""
        logger.info(f"Restarting plugin: {plugin_name}")
        return self.stop_plugin(plugin_name) and self.start_plugin(plugin_name)

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
        except docker.errors.NotFound:
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
            
        # 启动插件
        if not self.start_plugin(server_type):
            raise RuntimeError(f"Failed to start plugin: {server_type}")
            
        # 等待服务就绪
        # TODO: 实现服务就绪检查
        status = self.get_plugin_status(server_type)
        
        return {
            "status": status,
            "type": server_type,
            "container": self.plugins[server_type].container_name
        }

    def unload_server(self, server_type: str) -> Dict:
        """卸载指定的TTS服务器"""
        logger.info(f"Unloading server: {server_type}")
        if server_type not in self.plugins:
            logger.error(f"Unknown server type: {server_type}")
            raise ValueError(f"Unknown server type: {server_type}")
            
        # 停止插件
        if not self.stop_plugin(server_type):
            logger.error(f"Failed to stop plugin: {server_type}")
            raise RuntimeError(f"Failed to stop plugin: {server_type}")
            
        return {
            "status": "stopped",
            "type": server_type
        }

class PortManager:
    def __init__(self, start_port: int = 5000):
        self.start_port = start_port
        self.used_ports: Dict[str, set] = {}
        self.current_port = start_port
        
    def get_port(self) -> int:
        """获取下一个可用端口"""
        logger.debug(f"Getting next available port")
        while self._is_port_used(self.current_port):
            self.current_port += 1
        port = self.current_port
        self.current_port += 1
        logger.debug(f"Port {port} is available")
        return port
        
    def _is_port_used(self, port: int) -> bool:
        """检查端口是否已被使用"""
        logger.debug(f"Checking if port {port} is used")
        for ports in self.used_ports.values():
            if port in ports:
                logger.debug(f"Port {port} is used")
                return True
        logger.debug(f"Port {port} is not used")
        return False
        
    def release_ports(self, server_type: str):
        """释放指定服务器使用的所有端口"""
        logger.info(f"Releasing ports for server: {server_type}")
        if server_type in self.used_ports:
            self.used_ports.pop(server_type)
            logger.info(f"Ports released for server: {server_type}")
