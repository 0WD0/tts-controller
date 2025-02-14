import io
import torch
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import soundfile as sf
from transformers import AutoProcessor, BarkModel

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Bark TTS Service (GPU)")

# 全局变量
SAMPLE_RATE = 24000
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# 模型和处理器
processor = None
model = None

class TextToSpeechRequest(BaseModel):
    text: str
    voice_preset: str = "v2/en_speaker_6"

@app.on_event("startup")
async def startup_event():
    global processor, model
    try:
        logger.info(f"Loading Bark model on {DEVICE}...")
        processor = AutoProcessor.from_pretrained("suno/bark")
        model = BarkModel.from_pretrained("suno/bark")
        if DEVICE == "cuda":
            model = model.to(DEVICE)
        logger.info("Model loaded successfully")
    except Exception as e:
        logger.error(f"Error loading model: {e}")
        raise

@app.post("/tts")
async def text_to_speech(request: TextToSpeechRequest):
    try:
        # 生成音频
        inputs = processor(request.text, voice_preset=request.voice_preset)
        
        # 将输入移到正确的设备上
        if DEVICE == "cuda":
            inputs = {k: v.to(DEVICE) if torch.is_tensor(v) else v for k, v in inputs.items()}
        
        # 生成音频
        audio_array = model.generate(**inputs)
        audio_array = audio_array.cpu().numpy().squeeze()
        
        # 将音频数组转换为字节流
        audio_bytes = io.BytesIO()
        sf.write(audio_bytes, audio_array, SAMPLE_RATE, format='WAV')
        audio_bytes.seek(0)
        
        return audio_bytes.getvalue()
        
    except Exception as e:
        logger.error(f"Error generating audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """健康检查端点，返回设备信息"""
    device_info = {
        "status": "healthy",
        "device": DEVICE
    }
    
    if DEVICE == "cuda":
        device_info.update({
            "gpu_name": torch.cuda.get_device_name(0),
            "gpu_memory_total": torch.cuda.get_device_properties(0).total_memory,
            "gpu_memory_allocated": torch.cuda.memory_allocated(0),
            "cuda_version": torch.version.cuda
        })
    
    return device_info

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5013)
