from fastapi import FastAPI, HTTPException
import yaml
import httpx
from pydantic import BaseModel

app = FastAPI()

# 加载配置
with open("/config/config.yml", "r") as f:
    config = yaml.safe_load(f)

class TTSRequest(BaseModel):
    text: str
    language: str = "en"
    speaker_id: str = "default"
    tts_type: str = "coqui"  # 默认使用coqui

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/servers")
async def list_servers():
    # 返回所有可用的TTS服务器
    return {
        "servers": [
            {
                "name": name,
                "type": info["type"],
                "enabled": info["enabled"],
                "supported_languages": info["supported_languages"]
            }
            for name, info in config["tts_servers"].items()
        ]
    }

@app.post("/tts")
async def text_to_speech(request: TTSRequest):
    # 获取目标服务器信息
    server_info = config["tts_servers"].get(request.tts_type)
    if not server_info or not server_info["enabled"]:
        raise HTTPException(status_code=404, detail=f"TTS server {request.tts_type} not found or disabled")

    # 转发请求到对应的forward服务
    forward_url = server_info["forward_url"]
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{forward_url}/tts",
                json={
                    "text": request.text,
                    "language": request.language,
                    "speaker_id": request.speaker_id
                }
            )
            return response.json()
        except httpx.RequestError:
            raise HTTPException(status_code=500, detail="Failed to reach TTS server")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
