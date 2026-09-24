import os
import asyncio
import requests
import google.generativeai as genai
import edge_tts
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

class PipelineRequest(BaseModel):
    product_url: str

@app.get("/")
def home():
    return {"status": "Free Automation Server is running"}

def get_working_model():
    """현재 API 키에서 지원하는 사용 가능한 Gemini 모델을 자동으로 탐색"""
    try:
        available_models = [
            m.name for m in genai.list_models() 
            if 'generateContent' in m.supported_generation_methods
        ]
        # 우선순위: flash -> pro -> 첫 번째 이용 가능한 모델
        for target in ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro']:
            if target in available_models:
                return genai.GenerativeModel(target)
        
        if available_models:
            return genai.GenerativeModel(available_models[0])
    except Exception:
        pass
    # 기본 폴백 모델
    return genai.GenerativeModel('gemini-1.5-flash')

def make_video_sync(audio_path: str, img_path: str, output_path: str):
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration

    image_clip = ImageClip(img_path).set_duration(duration).resize(width=1080).set_position("center")
    bg_clip = ImageClip(img_path).resize((1080, 1920)).set_duration(duration)

    final_video = CompositeVideoClip([bg_clip, image_clip]).set_audio(audio_clip)
    final_video.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        logger=None
    )

@app.post("/run-pipeline")
async def run_pipeline(req: PipelineRequest):
    try:
        if not GEMINI_KEY:
            raise HTTPException(status_code=500, detail="GEMINI_API_KEY가 설정되지 않았습니다.")

        # 사용 가능한 모델 자동 감지 및 로드
        model = get_working_model()
        prompt = f"토스 추천 상품 링크({req.product_url})를 홍보하는 15초 숏폼 나레이션 대본을 작성해줘. 부연설명 없이 읽을 나레이션 텍스트만 출력해줘."
        
        response = model.generate_content(prompt)
        script = response.text.strip()

        # Edge-TTS 무료 음성 파일 생성
        audio_path = "/tmp/narration.mp3"
        communicate = edge_tts.Communicate(script, "ko-KR-SunHiNeural")
        await communicate.save(audio_path)

        # 이미지 다운로드 및 쇼츠 영상 합성
        img_path = "/tmp/thumb.jpg"
        img_bytes = requests.get("https://via.placeholder.com/1080x1080.png?text=Toss+Hotdeal").content
        with open(img_path, "wb") as f:
            f.write(img_bytes)

        video_path = "/tmp/output_shorts.mp4"
        
        await asyncio-to_thread(make_video_sync, audio_path, img_path, video_path) if hasattr(asyncio, "to_thread") else await asyncio.get_event_loop().run_in_executor(None, make_video_sync, audio_path, img_path, video_path)

        return {
            "success": True,
            "script": script,
            "message": "비용 0원 무료 파이프라인으로 영상 생성이 완료되었습니다!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
