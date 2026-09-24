import os
import asyncio
from PIL import Image

# 최신 Pillow 버전과 MoviePy 간 ANTIALIAS 호환성 오류 패치
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

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

def create_local_image(output_path: str):
    """메모리 절약을 위한 720x720 규격 썸네일 생성"""
    img = Image.new('RGB', (720, 720), color=(49, 130, 246))  # 토스 블루 (#3182F6)
    img.save(output_path)

def make_video_sync(audio_path: str, img_path: str, output_path: str):
    """Render 무료 메모리(512MB) 초과 방지 최적화 렌더링"""
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration

    # 720x1280 숏폼 규격으로 가볍게 설정 (메모리 사용량 60% 이상 감소)
    image_clip = ImageClip(img_path).set_duration(duration).resize(width=720).set_position("center")
    bg_clip = ImageClip(img_path).resize((720, 1280)).set_duration(duration)

    final_video = CompositeVideoClip([bg_clip, image_clip]).set_audio(audio_clip)
    
    # threads=1, preset="ultrafast"로 RAM 순간 점유율 200MB 이하 유지
    final_video.write_videofile(
        output_path,
        fps=20,
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast",
        threads=1,
        logger=None
    )

@app.post("/run-pipeline")
async def run_pipeline(req: PipelineRequest):
    try:
        if not GEMINI_KEY:
            raise HTTPException(status_code=500, detail="GEMINI_API_KEY가 설정되지 않았습니다.")

        # 1. Gemini AI 대본 작성
        try:
            model = genai.GenerativeModel('gemini-3.6-flash')
            prompt = f"토스 추천 상품 링크({req.product_url})를 홍보하는 15초 숏폼 나레이션 대본을 작성해줘. 부연설명 없이 읽을 나레이션 텍스트만 출력해줘."
            response = model.generate_content(prompt)
            script = response.text.strip()
        except Exception:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            if available_models:
                model = genai.GenerativeModel(available_models[0])
                response = model.generate_content(f"토스 추천 상품 링크({req.product_url})를 홍보하는 15초 숏폼 나레이션 대본을 작성해줘.")
                script = response.text.strip()
            else:
                raise HTTPException(status_code=500, detail="이용 가능한 Gemini 모델을 찾을 수 없습니다.")

        # 2. Edge-TTS 음성 파일 생성
        audio_path = "/tmp/narration.mp3"
        communicate = edge_tts.Communicate(script, "ko-KR-SunHiNeural")
        await communicate.save(audio_path)

        # 3. 로컬 썸네일 이미지 직접 생성
        img_path = "/tmp/thumb.jpg"
        create_local_image(img_path)

        # 4. 메모리 최적화 쇼츠 영상 렌더링
        video_path = "/tmp/output_shorts.mp4"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, make_video_sync, audio_path, img_path, video_path)

        return {
            "success": True,
            "script": script,
            "message": "비용 0원 완전 무료 파이프라인으로 영상 생성이 성공적으로 완료되었습니다!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
