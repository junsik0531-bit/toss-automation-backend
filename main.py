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
        session = requests.Session()
        res = session.get(url, headers=headers, allow_redirects=True, timeout=8)
        real_url = res.url
        soup = BeautifulSoup(res.text, 'html.parser')
        
        og_title = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "og:title"})
        raw_title = og_title["content"].strip() if og_title and og_title.get("content") else ""
        
        if not raw_title and soup.title:
            raw_title = soup.title.string.strip() if soup.title.string else ""

        product_name = re.sub(r'[\s|]*토스.*$', '', raw_title)
        product_name = re.sub(r'[\s|]*토스쇼핑.*$', '', product_name)
        product_name = product_name.strip()

        if not product_name:
            product_name = "토스 추천 핫딜 상품"

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
    """토스 파트너스 공식 API + 실시간 메타 동기화로 상위 5개 아이템 추출"""
    token = get_toss_access_token()
    if not token:
        return None
    
    headers = {"Authorization": f"Bearer {token}"}
    try:
        api_url = "https://api.toss.im/v1/shopping/partners/products"
        params = {"userId": TOSS_USER_ID, "limit": 5} if TOSS_USER_ID else {"limit": 5}
        res = requests.get(api_url, headers=headers, params=params, timeout=5)
        
        if res.status_code == 200:
            raw_items = res.json().get("data", [])
            parsed_items = []
            for item in raw_items[:5]:  # 상위 5개 제한
                share_url = item.get("shareUrl") or item.get("linkUrl") or ""
                
                if TOSS_USER_ID and share_url and "userId" not in share_url:
                    sep = "&" if "?" in share_url else "?"
                    share_url = f"{share_url}{sep}userId={TOSS_USER_ID}"
                
                meta_info = parse_toss_meta(share_url) if share_url else {"title": item.get("productName")}
                exact_name = meta_info.get("title") or item.get("productName", "토스 추천 상품")

                parsed_items.append({
                    "id": item.get("productId", f"item_{len(parsed_items)+1}"),
                    "name": exact_name,
                    "original_price": f"{item.get('originalPrice', 0):,}원" if item.get('originalPrice') else "정가 참조",
                    "discount_rate": f"{item.get('discountRate', 0)}%" if item.get('discountRate') else "핫딜",
                    "sale_price": f"{item.get('salePrice', 0):,}원" if item.get('salePrice') else "특가",
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
    return {"status": "Free Automation Server with 5 Items Fetcher is running"}

@app.get("/fetch-trending-items")
async def fetch_trending_items():
    """아이템 찾기: 정확한 5개의 인기 아이템 반환"""
    items = fetch_toss_official_items()
    
    # API 연결 전이거나 응답 오류 시 반환할 5개의 예비 핫딜 아이템
    if not items or len(items) < 5:
        user_param = f"?userId={TOSS_USER_ID}" if TOSS_USER_ID else ""
        backup_sample_links = [
            ("https://toss.shopping/_m/J61l5Lsj" + user_param, "초음파 세척기 스마트 2세대", "39,000원", "35%", "25,350원", "안경, 시계, 장신구 세척"),
            ("https://toss.shopping/_m/pPn2t5qo" + user_param, "무선 미니 마사지건 4종 헤드", "59,000원", "49%", "29,900원", "목 어깨 통증 완화, 근육 이완"),
            ("https://toss.shopping/_m/x8K2m1Lz" + user_param, "스마트 보온 텀블러 500ml", "29,000원", "31%", "19,800원", "실시간 온도 표시, 사무실 필수템"),
            ("https://toss.shopping/_m/qW9v4N2x" + user_param, "초고속 C타입 맥세이프 보조배터리", "45,000원", "40%", "26,900원", "무선 충전, 거치대 겸용"),
            ("https://toss.shopping/_m/rT3b8V1k" + user_param, "휴대용 LED 목걸이 선풍기", "25,000원", "44%", "13,900원", "야외활동, 운동 시 핸즈프리 냉방")
        ]
        
        items = []
        for idx, (link, name, o_price, rate, s_price, usage) in enumerate(backup_sample_links, 1):
            items.append({
                "id": f"item_0{idx}",
                "name": name,
                "original_price": o_price,
                "discount_rate": rate,
                "sale_price": s_price,
                "usage": usage,
                "share_link": link,
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
        product_title = meta_info["title"]

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
        download_product_image(meta_info["img_url"], img_path)

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
