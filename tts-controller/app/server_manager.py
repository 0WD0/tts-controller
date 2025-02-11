import docker
import yaml
from typing import Dict, Optional, List
import logging
import os
from pathlib import Path
import subprocess
from dataclasses import dataclass

# 配置日志记录
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class PluginInfo:
    name: str
    compose_file: Path
    status: str = "stopped"
    containers: List[str] = None

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

            compose_file = plugin_dir / "docker-compose.yml"
            if compose_file.exists():
                plugin_name = plugin_dir.name
                self.plugins[plugin_name] = PluginInfo(
                    name=plugin_name,
                    compose_file=compose_file,
                    containers=self._get_plugin_containers(compose_file)
                )
                logger.info(f"Found plugin: {plugin_name} at {compose_file}")

    def _get_plugin_containers(self, compose_file: Path) -> List[str]:
        """从docker-compose.yml文件中获取容器名称列表"""
        try:
            with open(compose_file) as f:
                compose_config = yaml.safe_load(f)
            return [
                service.get('container_name', f"{compose_config.get('name', 'unknown')}-{name}")
                for name, service in compose_config.get('services', {}).items()
            ]
        except Exception as e:
            logger.error(f"Failed to parse docker-compose.yml: {e}")
            return []

    def _run_compose_command(self, plugin_name: str, command: List[str]) -> bool:
        """执行docker-compose命令"""
        if plugin_name not in self.plugins:
            logger.error(f"Plugin {plugin_name} not found")
            return False

        plugin = self.plugins[plugin_name]
        base_cmd = ["docker", "compose", "-f", str(plugin.compose_file)]
        cmd = base_cmd + command

        try:
            logger.debug(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            logger.debug(f"Command output: {result.stdout}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {e.stderr}")
            return False

    def start_plugin(self, plugin_name: str) -> bool:
        """启动指定的插件"""
        logger.info(f"Starting plugin: {plugin_name}")
        if self._run_compose_command(plugin_name, ["up", "-d"]):
            self.plugins[plugin_name].status = "running"
            return True
        return False

    def stop_plugin(self, plugin_name: str) -> bool:
        """停止指定的插件"""
        logger.info(f"Stopping plugin: {plugin_name}")
        if self._run_compose_command(plugin_name, ["down"]):
            self.plugins[plugin_name].status = "stopped"
            return True
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
            for container_name in plugin.containers:
                container = self.docker_client.containers.get(container_name)
                if container.status != "running":
                    plugin.status = "partial"
                    return "partial"
            plugin.status = "running"
            return "running"
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
                "compose_file": str(plugin.compose_file),
                "containers": plugin.containers
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
        
        return {
            "status": "running",
            "type": server_type
        }

    def unload_server(self, server_type: str):
        """卸载指定的TTS服务器"""
        logger.info(f"Unloading server: {server_type}")
        if server_type not in self.plugins:
            logger.error(f"Unknown server type: {server_type}")
            return
            
        # 停止插件
        if not self.stop_plugin(server_type):
            logger.error(f"Failed to stop plugin: {server_type}")

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
