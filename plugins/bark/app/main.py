from fastapi import FastAPI, HTTPException
import os
import uvicorn
from pydantic import BaseModel

app = FastAPI()

# 获取环境变量
TTS_TYPE = os.getenv("TTS_TYPE", "unknown")
TTS_SERVER_URL = os.getenv("TTS_SERVER_URL", "http://localhost")

class TTSRequest(BaseModel):
    text: str
    language: str = "en"
    speaker_id: str = "default"

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "tts_type": TTS_TYPE,
        "tts_server": TTS_SERVER_URL
    }

@app.get("/voices")
async def list_voices():
    # 模拟返回支持的声音列表
    voices = {
        "coqui": [
            {"id": "default", "language": "en"},
            {"id": "speaker1", "language": "zh"}
        ],
        "bark": [
            {"id": "default", "language": "en"},
            {"id": "speaker2", "language": "zh"}
        ]
    }
    return voices.get(TTS_TYPE, {"error": "Unknown TTS type"})

@app.post("/tts")
async def text_to_speech(request: TTSRequest):
    # 模拟TTS处理
    return {
        "status": "success",
        "message": f"Processed by {TTS_TYPE}",
        "text": request.text,
        "audio_url": f"{TTS_SERVER_URL}/audio/mock.wav"
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
