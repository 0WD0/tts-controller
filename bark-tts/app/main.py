from fastapi import FastAPI
import uvicorn
from pydantic import BaseModel

app = FastAPI()

class TTSRequest(BaseModel):
    text: str
    speaker_id: str = "default"

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/tts")
async def text_to_speech(request: TTSRequest):
    # 模拟Bark TTS处理
    return {
        "status": "success",
        "audio_data": "mock_audio_data",
        "speaker": request.speaker_id
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
