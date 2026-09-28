import os
import re
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
TOSS_ACCESS_KEY = os.getenv("TOSS_CLIENT_ID", "")
TOSS_SECRET_KEY = os.getenv("TOSS_CLIENT_SECRET", "")
TOSS_USER_ID = os.getenv("TOSS_USER_ID", "")

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

class PipelineRequest(BaseModel):
    product_url: str

def parse_toss_meta(url: str):
    """토스 쉐어링크의 리다이렉션 최종 URL 추적 및 진짜 상품명/이미지 파싱"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    try:
        # 리다이렉션을 추적하여 최종 실제 상품 페이지 가져오기
        session = requests.Session()
        res = session.get(url, headers=headers, allow_redirects=True, timeout=8)
        real_url = res.url
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 1. 메타 태그 및 HTML title에서 상품명 추출
        og_title = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "og:title"})
        raw_title = og_title["content"].strip() if og_title and og_title.get("content") else ""
        
        if not raw_title and soup.title:
            raw_title = soup.title.string.strip() if soup.title.string else ""

        # 불필요한 '토스', '토스쇼핑', '공동구매' 등 수식어 정제
        product_name = re.sub(r'[\s|]*토스.*$', '', raw_title)
        product_name = re.sub(r'[\s|]*토스쇼핑.*$', '', product_name)
        product_name = product_name.strip()

        if not product_name:
            product_name = "토스 추천 핫딜 상품"

        # 2. 대표 이미지 추적
        og_image = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "og:image"})
        img_url = og_image["content"] if og_image and og_image.get("content") else None

        return {
            "title": product_name,
            "real_url": real_url,
            "img_url": img_url
        }
    except Exception:
        return {
            "title": "토스 추천 핫딜 상품",
            "real_url": url,
            "img_url": None
        }

def get_toss_access_token():
    """토스 파트너스 API Access Key/Secret Key 기반 인증 토큰 발급"""
    if not TOSS_ACCESS_KEY or not TOSS_SECRET_KEY:
        return None
    try:
        url = "https://api.toss.im/v1/oauth/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": TOSS_ACCESS_KEY,
            "client_secret": TOSS_SECRET_KEY
        }
        res = requests.post(url, json=payload, timeout=5)
        if res.status_code == 200:
            return res.json().get("access_token")
    except Exception:
        pass
    return None

def fetch_toss_official_items():
    """토스 파트너스 공식 API + 실시간 메타 동기화로 정확한 상품명 추출"""
    token = get_toss_access_token()
    if not token:
        return None
    
    headers = {"Authorization": f"Bearer {token}"}
    try:
        api_url = "https://api.toss.im/v1/shopping/partners/products"
        params = {"userId": TOSS_USER_ID} if TOSS_USER_ID else {}
        res = requests.get(api_url, headers=headers, params=params, timeout=5)
        
        if res.status_code == 200:
            raw_items = res.json().get("data", [])
            parsed_items = []
            for item in raw_items:
                share_url = item.get("shareUrl") or item.get("linkUrl") or ""
                
                # 회원 연동 ID 적용 쉐어링크 결합
                if TOSS_USER_ID and share_url and "userId" not in share_url:
                    sep = "&" if "?" in share_url else "?"
                    share_url = f"{share_url}{sep}userId={TOSS_USER_ID}"
                
                # 링크의 실제 상품 메타데이터 재검증 (1:1 매칭 보장)
                meta_info = parse_toss_meta(share_url) if share_url else {"title": item.get("productName")}
                exact_name = meta_info.get("title") or item.get("productName", "토스 추천 상품")

                parsed_items.append({
                    "id": item.get("productId", "item"),
                    "name": exact_name,
                    "original_price": f"{item.get('originalPrice', 0):,}원" if item.get('originalPrice') else "정가 참조",
                    "discount_rate": f"{item.get('discountRate', 0)}%" if item.get('discountRate') else "할인중",
                    "sale_price": f"{item.get('salePrice', 0):,}원" if item.get('salePrice') else "핫딜가",
                    "usage": item.get("categoryName", "토스 파트너스 핫딜"),
                    "share_link": share_url,
                    "date": "2026-09-28",
                    "reels": False, "shorts": False, "blog": False
                })
            return parsed_items
    except Exception:
        pass
    return None

@app.get("/")
def home():
    return {"status": "Free Automation Server with Realtime Meta Matcher is running"}

@app.get("/fetch-trending-items")
async def fetch_trending_items():
    """아이템 찾기: 1:1 정확한 상품명 매칭 데이터 반환"""
    items = fetch_toss_official_items()
    
    # API 응답 대기/오류 시 실시간 쉐어링크 주소 기반으로 매칭된 샘플
    if not items:
        target_link = f"https://toss.shopping/_m/J61l5Lsj?userId={TOSS_USER_ID}" if TOSS_USER_ID else "https://toss.shopping/_m/J61l5Lsj"
        meta = parse_toss_meta(target_link)
        items = [
            {
                "id": "item_01",
                "name": meta["title"],
                "original_price": "39,000원",
                "discount_rate": "35%",
                "sale_price": "25,350원",
                "usage": "토스 추천 핫딜 상품",
                "share_link": target_link,
                "date": "2026-09-28",
                "reels": False, "shorts": False, "blog": False
            }
        ]
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

        # 1. 리다이렉션 및 상품명 1:1 파싱
        meta_info = parse_toss_meta(req.product_url)
        product_title = meta_info["title"]

        # 2. Gemini AI 대본 작성
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

        # 3. Edge-TTS 음성 생성
        audio_path = "/tmp/narration.mp3"
        communicate = edge_tts.Communicate(script, "ko-KR-SunHiNeural")
        await communicate.save(audio_path)

        # 4. 대표 이미지 다운로드
        img_path = "/tmp/thumb.jpg"
        download_product_image(meta_info["img_url"], img_path)

        # 5. 쇼츠 영상 렌더링
        video_path = "/tmp/output_shorts.mp4"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, make_video_sync, audio_path, img_path, video_path)

        return {
            "success": True,
            "product_name": product_title,
            "script": script,
            "share_link": req.product_url,
            "video_url": "https://toss-automation-backend.onrender.com/download-video",
            "message": "링크의 실제 상품명과 1:1 매칭된 숏폼 생성이 완료되었습니다!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
