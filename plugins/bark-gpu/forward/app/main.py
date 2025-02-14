import os
import logging
import aiohttp
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import yaml

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(title="Bark TTS Forward Service")

class TTSRequest(BaseModel):
    text: str
    voice_preset: Optional[str] = "v2/en_speaker_6"
    temperature: Optional[float] = 0.7

# 从环境变量获取 TTS 服务器 URL
TTS_SERVER_URL = os.getenv("TTS_SERVER_URL", "http://bark-tts:5013")

@app.post("/tts")
async def forward_tts_request(request: TTSRequest):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{TTS_SERVER_URL}/tts",
                json=request.dict()
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"TTS service error: {error_text}"
                    )
                return await response.read()
                
    except aiohttp.ClientError as e:
        logger.error(f"Error connecting to TTS service: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail=f"TTS service unavailable: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{TTS_SERVER_URL}/health") as response:
                if response.status == 200:
                    return {"status": "healthy"}
                return {"status": "unhealthy", "detail": "TTS service not responding"}
    except Exception as e:
        return {"status": "unhealthy", "detail": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
