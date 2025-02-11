from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
import yaml
import httpx
from .server_manager import TTSServerManager

app = FastAPI()
server_manager = TTSServerManager("/config/config.yml")

class TTSRequest(BaseModel):
    text: str
    language: str = "en"
    speaker_id: str = "default"
    tts_type: str = "coqui"

@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/api/servers")
async def get_all_servers() -> Dict:
    try:
        return server_manager.get_all_plugins()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/servers/{server_type}/load")
async def load_server(server_type: str) -> Dict:
    try:
        return server_manager.load_server(server_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/servers/{server_type}/unload")
async def unload_server(server_type: str) -> Dict:
    try:
        return server_manager.unload_server(server_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/servers/{server_type}/status")
async def get_server_status(server_type: str) -> Dict:
    try:
        return server_manager.get_plugin_status(server_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tts")
async def text_to_speech(request: TTSRequest):
    """处理TTS请求"""
    # 检查服务器状态
    status = server_manager.get_plugin_status(request.tts_type)
    if status.get("status") == "not_loaded":
        # 如果服务器未加载，尝试加载它
        try:
            server_manager.load_server(request.tts_type)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # 转发请求到对应的forward服务
    forward_url = f"http://{request.tts_type}-forward:8080/tts"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                forward_url,
                json={
                    "text": request.text,
                    "language": request.language,
                    "speaker_id": request.speaker_id
                }
            )
            return response.json()
        except httpx.RequestError:
            raise HTTPException(status_code=500, detail="Failed to reach TTS server")
