from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import uvicorn
from pydantic import BaseModel

app = FastAPI()

class TTSRequest(BaseModel):
    text: str
    speaker_id: str = "default"

# 模拟 WebUI
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return """
    <html>
        <head>
            <title>Mock Coqui-TTS WebUI</title>
        </head>
        <body>
            <h1>Mock Coqui-TTS Web Interface</h1>
            <form>
                <textarea placeholder="Enter text here..."></textarea><br>
                <select>
                    <option value="en">English</option>
                    <option value="zh">Chinese</option>
                </select>
                <button type="button">Generate</button>
            </form>
        </body>
    </html>
    """

# API endpoints
@app.get("/api/speakers")
async def list_speakers():
    return {
        "speakers": [
            {"id": "default", "language": "en"},
            {"id": "speaker1", "language": "en"},
            {"id": "speaker2", "language": "zh"}
        ]
    }

@app.post("/api/tts")
async def text_to_speech(request: TTSRequest):
    # 模拟TTS处理
    return {
        "status": "success",
        "audio_data": "mock_audio_data_from_coqui",
        "speaker": request.speaker_id
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    # 5002端口用于WebUI，5003端口用于API
    import multiprocessing
    
    def run_webui():
        uvicorn.run(app, host="0.0.0.0", port=5002)
        
    def run_api():
        uvicorn.run(app, host="0.0.0.0", port=5003)
    
    # 启动两个进程分别处理WebUI和API
    webui_process = multiprocessing.Process(target=run_webui)
    api_process = multiprocessing.Process(target=run_api)
    
    webui_process.start()
    api_process.start()
    
    webui_process.join()
    api_process.join()
