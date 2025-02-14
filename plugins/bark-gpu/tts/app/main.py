import os
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import torch
from bark import SAMPLE_RATE, generate_audio, preload_models
import numpy as np
import io
import soundfile as sf

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(title="Bark TTS Service (GPU)")

class TTSRequest(BaseModel):
    text: str
    voice_preset: Optional[str] = "v2/en_speaker_6"
    temperature: Optional[float] = 0.7

# 预加载模型
@app.on_event("startup")
async def startup_event():
    logger.info("Loading Bark models...")
    # 确保 CUDA 可用
    if not torch.cuda.is_available():
        logger.error("CUDA is not available! This is the GPU version and requires CUDA.")
        raise RuntimeError("CUDA is not available")
    
    device = os.getenv("DEVICE", "cuda")
    logger.info(f"Using device: {device}")
    logger.info(f"CUDA Device: {torch.cuda.get_device_name()}")
    preload_models()
    logger.info("Models loaded successfully")

@app.post("/tts")
async def text_to_speech(request: TTSRequest):
    try:
        # 生成音频
        audio_array = generate_audio(
            request.text,
            history_prompt=request.voice_preset,
            temperature=request.temperature
        )
        
        # 将音频数组转换为字节流
        audio_bytes = io.BytesIO()
        sf.write(audio_bytes, audio_array, SAMPLE_RATE, format='WAV')
        audio_bytes.seek(0)
        
        return audio_bytes.getvalue()
        
    except Exception as e:
        logger.error(f"Error generating audio: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    gpu_info = {
        "device": "cuda",
        "cuda_available": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name() if torch.cuda.is_available() else None,
        "gpu_memory": f"{torch.cuda.memory_allocated() / 1024**2:.2f}MB allocated" if torch.cuda.is_available() else None
    }
    return {"status": "healthy", **gpu_info}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5013)
