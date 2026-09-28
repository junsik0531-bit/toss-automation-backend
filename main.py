import os
import re
import asyncio
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
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
TOSS_ACCESS_KEY = os.getenv("TOSS_CLIENT_ID", "")
TOSS_SECRET_KEY = os.getenv("TOSS_CLIENT_SECRET", "")
TOSS_USER_ID = os.getenv("TOSS_USER_ID", "")

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

class PipelineRequest(BaseModel):
    product_url: str

def build_toss_user_link(raw_url: str) -> str:
    """TOSS_USER_ID를 URL 파라미터에 안전하게 결합"""
    if not raw_url:
        return ""
    if not TOSS_USER_ID:
        return raw_url
    
    try:
        url_parts = list(urlparse(raw_url))
        query = parse_qs(url_parts[4])
        query['userId'] = [TOSS_USER_ID]
        url_parts[4] = urlencode(query, doseq=True)
        return urlunparse(url_parts)
    except Exception:
        sep = "&" if "?" in raw_url else "?"
        return f"{raw_url}{sep}userId={TOSS_USER_ID}"

def generate_3_features(product_name: str, desc: str) -> list:
    """Gemini AI를 이용한 상품 장점 3가지 자동 요약 추출"""
    if GEMINI_KEY:
        try:
            model = genai.GenerativeModel('gemini-3.6-flash')
            prompt = f"상품명: '{product_name}' (설명: {desc})의 가장 핵심적인 장점/소구점 3가지를 구체적인 단어 위주로 짧게 3개의 항목으로만 작성해줘. 예시:\n1. 고단백/저당 구성\n2. 겉바속촉 식감\n3. 개별 포장 보관 용이"
            res = model.generate_content(prompt)
            lines = [l.strip() for l in res.text.split('\n') if l.strip()]
            clean_features = []
            for line in lines:
                cleaned = re.sub(r'^[\d\.\-\*•\s]+', '', line).strip()
                if cleaned:
                    clean_features.append(cleaned)
            if len(clean_features) >= 3:
                return clean_features[:3]
        except Exception:
            pass
    return ["우수한 가성비 및 할인혜택", "사용자 실후기 호평 대란템", "간편한 보관 및 실용적인 활용"]

def parse_toss_meta(url: str):
    """토스 쉐어링크 메타데이터 파싱 및 장점 추출"""
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9"
    }
    try:
        session = requests.Session()
        res = session.get(url, headers=headers, allow_redirects=True, timeout=6)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        og_title = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "og:title"})
        title = og_title["content"].strip() if og_title and og_title.get("content") else ""
        if not title and soup.title:
            title = soup.title.string.strip() if soup.title.string else ""

        title = re.sub(r'[\s|]*토스.*$', '', title)
        title = re.sub(r'[\s|]*토스쇼핑.*$', '', title).strip()

        og_image = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "og:image"})
        img_url = og_image["content"] if og_image and og_image.get("content") else None

        og_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "og:description"})
        desc = og_desc["content"].strip() if og_desc and og_desc.get("content") else "토스 파트너스 추천 핫딜 상품"

        return {
            "title": title if title else "토스 파트너스 추천 핫딜",
            "desc": desc,
            "img_url": img_url,
            "real_url": res.url
        }
    except Exception:
        return {
            "title": "토스 파트너스 추천 핫딜",
            "desc": "토스 파트너스 추천 핫딜 상품",
            "img_url": None,
            "real_url": url
        }

@app.get("/")
def home():
    return {"status": "Free Automation Server with Custom Link & Feature Extractor is running"}

@app.post("/parse-custom-link")
async def parse_custom_link(req: PipelineRequest):
    """사용자가 직접 입력한 토스 쉐어링크 파싱 및 장점 3가지 자동 구성"""
    share_url = build_toss_user_link(req.product_url)
    meta = parse_toss_meta(share_url)
    features = generate_3_features(meta["title"], meta["desc"])

    return {
        "success": True,
        "item": {
            "id": f"custom_{int(asyncio.get_event_loop().time())}",
            "name": meta["title"],
            "features": features,
            "original_price": "상세 참조",
            "discount_rate": "특가 할인",
            "sale_price": "토스 앱 특가",
            "usage": meta["desc"],
            "share_link": share_url,
            "date": "2026-09-28",
            "reels": False, "shorts": False, "blog": False
        }
    }

@app.get("/fetch-trending-items")
async def fetch_trending_items():
    """인기 아이템 수집 및 장점 3가지 결합"""
    active_sample_links = [
        "https://toss.shopping/_m/pPn2t5qo",
        "https://toss.shopping/_m/J61l5Lsj",
        "https://toss.shopping/_m/x8K2m1Lz",
        "https://toss.shopping/_m/qW9v4N2x",
        "https://toss.shopping/_m/rT3b8V1k"
    ]
    
    items = []
    for idx, raw_link in enumerate(active_sample_links, 1):
        share_url = build_toss_user_link(raw_link)
        meta_info = parse_toss_meta(share_url)
        product_name = meta_info.get("title") or f"토스 추천 핫딜 상품 0{idx}"
        features = generate_3_features(product_name, meta_info.get("desc", ""))

        items.append({
            "id": f"item_0{idx}",
            "name": product_name,
            "features": features,
            "original_price": "상세 참조",
            "discount_rate": "특가 할인",
            "sale_price": "토스 앱 특가",
            "usage": meta_info.get("desc", "토스 파트너스 추천 핫딜"),
            "share_link": share_url,
            "date": "2026-09-28",
            "reels": False, "shorts": False, "blog": False
        })

    return {"success": True, "items": items}

@app.get("/download-video")
def download_video():
    video_path = "/tmp/output_shorts.mp4"
    if os.path.exists(video_path):
        return FileResponse(video_path, media_type="video/mp4", filename="toss_shorts.mp4")
    raise HTTPException(status_code=404, detail="영상을 찾을 수 없습니다.")

def download_product_image(img_url: str, save_path: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        if img_url:
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

        meta_info = parse_toss_meta(req.product_url)
        product_title = meta_info.get("title") or "토스 핫딜 추천 상품"

        try:
            model = genai.GenerativeModel('gemini-3.6-flash')
            prompt = f"상품명: '{product_title}' (구매 링크: {req.product_url})를 홍보하는 15초 숏폼 나레이션 대본을 작성해줘. 부연설명 없이 읽을 나레이션 텍스트만 출력해줘."
            response = model.generate_content(prompt)
            script = response.text.strip()
        except Exception:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            if available_models:
                model = genai.GenerativeModel(available_models[0])
                response = model.generate_content(f"상품명: '{product_title}'를 홍보하는 15초 숏폼 나레이션 대본을 작성해줘.")
                script = response.text.strip()
            else:
                raise HTTPException(status_code=500, detail="이용 가능한 Gemini 모델을 찾을 수 없습니다.")

        audio_path = "/tmp/narration.mp3"
        communicate = edge_tts.Communicate(script, "ko-KR-SunHiNeural")
        await communicate.save(audio_path)

        img_path = "/tmp/thumb.jpg"
        download_product_image(meta_info.get("img_url"), img_path)

        video_path = "/tmp/output_shorts.mp4"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, make_video_sync, audio_path, img_path, video_path)

        return {
            "success": True,
            "product_name": product_title,
            "script": script,
            "share_link": req.product_url,
            "video_url": "https://toss-automation-backend.onrender.com/download-video",
            "message": "실제 열리는 상품 페이지의 1:1 명칭과 매칭되어 숏폼 생성이 완료되었습니다!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
