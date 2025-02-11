import docker
import yaml
from typing import Dict, Optional
import logging
import os
from pathlib import Path

# 配置日志记录
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TTSServerManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
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
            # 直接使用DockerClient并指定base_url
            self.docker_client = docker.DockerClient(base_url='unix:///var/run/docker.sock')
            logger.info("Docker client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            raise
            
        self.port_manager = PortManager(start_port=5000)
        self.load_config()
        
    def load_config(self):
        logger.info(f"Loading configuration from {self.config_path}")
        try:
            with open(self.config_path) as f:
                self.config = yaml.safe_load(f)
            logger.debug(f"Loaded configuration: {self.config}")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
        
    def load_server(self, server_type: str) -> Dict:
        """加载指定的TTS服务器"""
        logger.info(f"Loading server: {server_type}")
        if server_type not in self.config['tts_servers']:
            logger.error(f"Unknown server type: {server_type}")
            raise ValueError(f"Unknown server type: {server_type}")
            
        server_config = self.config['tts_servers'][server_type]
        if not server_config['enabled']:
            logger.error(f"Server {server_type} is disabled")
            raise ValueError(f"Server {server_type} is disabled")
        
        # 分配端口
        webui_port = self.port_manager.get_port()
        api_port = self.port_manager.get_port()
        forward_port = self.port_manager.get_port()
        
        # 构建环境变量
        tts_environment = {
            'TTS_TYPE': server_type,
            'WEBUI_PORT': str(webui_port),
            'API_PORT': str(api_port),
            'MODELS_PATH': '/models',
            'CACHE_PATH': '/cache',
            'LOG_PATH': '/logs'
        }
        
        forward_environment = {
            'TTS_TYPE': server_type,
            'TTS_SERVER_URL': f'http://{server_type}-tts:{api_port}',
            'CONFIG_PATH': '/config/config.yml',
            'LOG_PATH': '/logs',
            'PORT': str(forward_port)
        }
        
        try:
            # 启动TTS服务器
            logger.info(f"Starting TTS server: {server_type}")
            tts_container = self.docker_client.containers.run(
                f"tts-{server_type}",  # 使用正确的镜像名称
                detach=True,
                environment=tts_environment,
                ports={
                    f'{webui_port}/tcp': webui_port,
                    f'{api_port}/tcp': api_port
                },
                volumes={
                    f'/data/models/{server_type}': {'bind': '/models', 'mode': 'rw'},
                    f'/data/cache/{server_type}': {'bind': '/cache', 'mode': 'rw'},
                    f'/data/logs/{server_type}': {'bind': '/logs', 'mode': 'rw'}
                },
                network='tts-network',
                name=f'{server_type}-tts'
            )
            logger.info(f"TTS server started successfully: {server_type}")
            
            # 启动对应的forward服务
            logger.info(f"Starting forward server: {server_type}")
            forward_container = self.docker_client.containers.run(
                f"tts-{server_type}-forward",  # 使用正确的镜像名称
                detach=True,
                environment=forward_environment,
                ports={
                    f'{forward_port}/tcp': forward_port
                },
                volumes={
                    '/config': {'bind': '/config', 'mode': 'ro'},
                    f'/data/logs/{server_type}': {'bind': '/logs', 'mode': 'rw'}
                },
                network='tts-network',
                name=f'{server_type}-forward'
            )
            logger.info(f"Forward server started successfully: {server_type}")
            
            # 记录使用的端口
            if server_type not in self.port_manager.used_ports:
                self.port_manager.used_ports[server_type] = set()
            self.port_manager.used_ports[server_type].update([webui_port, api_port, forward_port])
            
            return {
                'server_type': server_type,
                'status': 'loaded',
                'webui_port': webui_port,
                'api_port': api_port,
                'forward_port': forward_port,
                'tts_container_id': tts_container.id,
                'forward_container_id': forward_container.id
            }
        except docker.errors.APIError as e:
            # 如果启动失败，清理资源
            logger.error(f"Failed to start server: {str(e)}")
            self.unload_server(server_type)
            raise Exception(f"Failed to start server: {str(e)}")
    
    def unload_server(self, server_type: str) -> Dict:
        """卸载指定的TTS服务器"""
        logger.info(f"Unloading server: {server_type}")
        try:
            # 停止并删除TTS容器
            try:
                tts_container = self.docker_client.containers.get(f'{server_type}-tts')
                logger.info(f"Stopping TTS container: {server_type}")
                tts_container.stop()
                logger.info(f"TTS container stopped: {server_type}")
                tts_container.remove()
                logger.info(f"TTS container removed: {server_type}")
            except docker.errors.NotFound:
                logger.info(f"TTS container not found: {server_type}")
                pass
            
            # 停止并删除forward容器
            try:
                forward_container = self.docker_client.containers.get(f'{server_type}-forward')
                logger.info(f"Stopping forward container: {server_type}")
                forward_container.stop()
                logger.info(f"Forward container stopped: {server_type}")
                forward_container.remove()
                logger.info(f"Forward container removed: {server_type}")
            except docker.errors.NotFound:
                logger.info(f"Forward container not found: {server_type}")
                pass
            
            # 释放端口
            self.port_manager.release_ports(server_type)
            logger.info(f"Ports released: {server_type}")
            
            return {'status': 'unloaded', 'server_type': server_type}
        except Exception as e:
            logger.error(f"Failed to unload server: {str(e)}")
            return {'status': 'error', 'server_type': server_type, 'error': str(e)}
            
    def get_server_status(self, server_type: str) -> Dict:
        """获取服务器状态"""
        logger.info(f"Getting server status: {server_type}")
        if server_type not in self.config['tts_servers']:
            logger.error(f"Unknown server type: {server_type}")
            raise ValueError(f"Unknown server type: {server_type}")
            
        try:
            tts_container = self.docker_client.containers.get(f'{server_type}-tts')
            forward_container = self.docker_client.containers.get(f'{server_type}-forward')
            
            return {
                'server_type': server_type,
                'tts_status': tts_container.status,
                'forward_status': forward_container.status
            }
        except docker.errors.NotFound:
            logger.info(f"Server not found: {server_type}")
            return {
                'server_type': server_type,
                'status': 'not_loaded'
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
