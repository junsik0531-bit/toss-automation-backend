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

# Google Gemini API 키 설정
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

class PipelineRequest(BaseModel):
    product_url: str

@app.get("/")
def home():
    return {"status": "Free Automation Server is running"}

@app.post("/run-pipeline")
async def run_pipeline(req: PipelineRequest):
    try:
        # 1. Gemini API로 무료 대본 작성
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"토스 추천 상품 링크({req.product_url})를 홍보하는 15초 숏폼 나레이션 대본을 작성해줘. 다른 부연설명 없이 영상에 들어갈 읽을 대본 텍스트만 출력해줘."
        
        response = model.generate_content(prompt)
        script = response.text.strip()

        # 2. Edge-TTS로 무료 음성 파일(.mp3) 생성 (한국어 여성 음성: ko-KR-SunHiNeural)
        audio_path = "/tmp/narration.mp3"
        communicate = edge_tts.Communicate(script, "ko-KR-SunHiNeural")
        await communicate.save(audio_path)

        # 3. 임시 이미지 다운로드 및 9:16 영상 합성 (MoviePy)
        img_path = "/tmp/thumb.jpg"
        img_bytes = requests.get("https://via.placeholder.com/1080x1080.png?text=Toss+Hotdeal").content
        with open(img_path, "wb") as f:
            f.write(img_bytes)

        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration

        image_clip = ImageClip(img_path).set_duration(duration).resize(width=1080).set_position("center")
        bg_clip = ImageClip(img_path).resize((1080, 1920)).set_duration(duration)

        final_video = CompositeVideoClip([bg_clip, image_clip]).set_audio(audio_clip)
        video_path = "/tmp/output_shorts.mp4"
        
        # 동기 작업을 비동기 스레드로 실행
        await asyncio.to_thread(
            final_video.write_videofile,
            video_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            logger=None
        )

        return {
            "success": True,
            "script": script,
            "message": "비용 0원 무료 파이프라인으로 영상 생성이 완료되었습니다!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
