import docker
import yaml
from typing import Dict, Optional
import logging
from pathlib import Path

class TTSServerManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.docker_client = docker.from_env()
        self.port_manager = PortManager(start_port=5000)
        self.load_config()
        
    def load_config(self):
        with open(self.config_path) as f:
            self.config = yaml.safe_load(f)
        
    def load_server(self, server_type: str) -> Dict:
        """加载指定的TTS服务器"""
        if server_type not in self.config['tts_servers']:
            raise ValueError(f"Unknown server type: {server_type}")
            
        server_config = self.config['tts_servers'][server_type]
        if not server_config['enabled']:
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
            
            # 启动对应的forward服务
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
            self.unload_server(server_type)
            raise Exception(f"Failed to start server: {str(e)}")
    
    def unload_server(self, server_type: str) -> Dict:
        """卸载指定的TTS服务器"""
        try:
            # 停止并删除TTS容器
            try:
                tts_container = self.docker_client.containers.get(f'{server_type}-tts')
                tts_container.stop()
                tts_container.remove()
            except docker.errors.NotFound:
                pass
            
            # 停止并删除forward容器
            try:
                forward_container = self.docker_client.containers.get(f'{server_type}-forward')
                forward_container.stop()
                forward_container.remove()
            except docker.errors.NotFound:
                pass
            
            # 释放端口
            self.port_manager.release_ports(server_type)
            
            return {'status': 'unloaded', 'server_type': server_type}
        except Exception as e:
            return {'status': 'error', 'server_type': server_type, 'error': str(e)}
            
    def get_server_status(self, server_type: str) -> Dict:
        """获取服务器状态"""
        if server_type not in self.config['tts_servers']:
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
        while self._is_port_used(self.current_port):
            self.current_port += 1
        port = self.current_port
        self.current_port += 1
        return port
        
    def _is_port_used(self, port: int) -> bool:
        """检查端口是否已被使用"""
        for ports in self.used_ports.values():
            if port in ports:
                return True
        return False
        
    def release_ports(self, server_type: str):
        """释放指定服务器使用的所有端口"""
        if server_type in self.used_ports:
            self.used_ports.pop(server_type)
