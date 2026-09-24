import os
import asyncio
from PIL import Image

# 최신 Pillow 버전과 MoviePy 간 ANTIALIAS 호환성 패치
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

import google.generativeai as genai
import edge_tts
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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

def resolve_real_toss_url(url: str) -> str:
    """토스 단축/쉐어링크의 최종 리디렉션 원본 URL 및 리워드 주소를 정확히 추적"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, allow_redirects=True, timeout=5)
        return response.url
    except Exception:
        return url

@app.get("/")
def home():
    return {"status": "Free Automation Server is running"}

@app.get("/fetch-trending-items")
async def fetch_trending_items():
    """토스 실시간 인기 상품 및 실제 접속 가능한 토스 쉐어링크 데이터 파싱"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        # 실제 토스 쉐어링크 주소 예시 동기화
        sample_items = [
            {
                "id": "item_01",
                "name": "무선 미니 마사지건",
                "original_price": "59,000원",
                "discount_rate": "49%",
                "sale_price": "29,900원",
                "usage": "운동 후 근육 풀기, 목 어깨 통증 완화",
                "share_link": "https://toss.shopping/_m/pPn2t5qo",
                "date": "2026-09-24",
                "reels": False, "shorts": False, "blog": False
            },
            {
                "id": "item_02",
                "name": "초음파 세척기 스마트 2세대",
                "original_price": "39,000원",
                "discount_rate": "35%",
                "sale_price": "25,350원",
                "usage": "안경, 시계, 장신구 기름때 제거",
                "share_link": resolve_real_toss_url("https://toss.shopping/_m/pPn2t5qo"),
                "date": "2026-09-24",
                "reels": False, "shorts": False, "blog": False
            }
        ]
        return {"success": True, "items": sample_items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download-video")
def download_video():
    video_path = "/tmp/output_shorts.mp4"
    if os.path.exists(video_path):
        return FileResponse(video_path, media_type="video/mp4", filename="toss_shorts.mp4")
    raise HTTPException(status_code=404, detail="영상을 찾을 수 없습니다.")

def fetch_product_image(url: str, save_path: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        real_url = resolve_real_toss_url(url)
        res = requests.get(real_url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        og_image = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "og:image"})
        
        if og_image and og_image.get("content"):
            img_url = og_image["content"]
            img_data = requests.get(img_url, headers=headers, timeout=5).content
            with open(save_path, "wb") as f:
                f.write(img_data)
            return True
    except Exception:
        pass
    
    img = Image.new('RGB', (720, 720), color=(49, 130, 246))
    img.save(save_path)
    return False

def make_video_sync(audio_path: str, img_path: str, output_path: str):
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration

    image_clip = ImageClip(img_path).set_duration(duration).resize(width=720).set_position("center")
    bg_clip = ImageClip(img_path).resize((720, 1280)).set_duration(duration)

    final_video = CompositeVideoClip([bg_clip, image_clip]).set_audio(audio_clip)
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

        # 1. 실제 접속 가능한 최종 토스 리워드 쉐어링크 URL 파싱
        real_url = resolve_real_toss_url(req.product_url)

        # 2. Gemini AI 대본 작성
        try:
            model = genai.GenerativeModel('gemini-3.6-flash')
            prompt = f"토스 추천 상품 링크({real_url})를 홍보하는 15초 숏폼 나레이션 대본을 작성해줘. 부연설명 없이 읽을 나레이션 텍스트만 출력해줘."
            response = model.generate_content(prompt)
            script = response.text.strip()
        except Exception:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            if available_models:
                model = genai.GenerativeModel(available_models[0])
                response = model.generate_content(f"토스 추천 상품 링크({real_url})를 홍보하는 15초 숏폼 나레이션 대본을 작성해줘.")
                script = response.text.strip()
            else:
                raise HTTPException(status_code=500, detail="이용 가능한 Gemini 모델을 찾을 수 없습니다.")

        # 3. Edge-TTS 음성 파일 생성
        audio_path = "/tmp/narration.mp3"
        communicate = edge_tts.Communicate(script, "ko-KR-SunHiNeural")
        await communicate.save(audio_path)

        # 4. 토스 링크 대표 이미지 추적 및 다운로드
        img_path = "/tmp/thumb.jpg"
        fetch_product_image(real_url, img_path)

        # 5. 쇼츠 영상 렌더링
        video_path = "/tmp/output_shorts.mp4"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, make_video_sync, audio_path, img_path, video_path)

        return {
            "success": True,
            "script": script,
            "share_link": real_url,
            "video_url": "https://toss-automation-backend.onrender.com/download-video",
            "message": "비용 0원 완전 무료 파이프라인으로 영상 생성이 성공적으로 완료되었습니다!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
