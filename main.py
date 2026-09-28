import os
import re
import asyncio
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from PIL import Image, ImageDraw, ImageFont

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
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip, ConcatenateVideoClip

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
    if GEMINI_KEY and product_name:
        try:
            model = genai.GenerativeModel('gemini-3.6-flash')
            prompt = f"상품명: '{product_name}' (설명: {desc})의 핵심 장점 3가지를 단어/구문 형태로 출력해줘. 기호나 번호 없이 오직 텍스트 3줄만 출력해줘."
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
    return ["우수한 가성비 및 특가 혜택", "실구매자 호평 검증 아이템", "실용적인 구성 및 간편 활용"]

def parse_toss_meta(url: str):
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
        desc = og_desc["content"].strip() if og_desc and og_desc.get("content") else "토스 파트너스 추천 상품"

        return {
            "title": title if title and title != "토스" else "토스 파트너스 추천 상품",
            "desc": desc,
            "img_url": img_url,
            "real_url": res.url
        }
    except Exception:
        return {
            "title": "토스 파트너스 추천 상품",
            "desc": "토스 파트너스 추천 상품",
            "img_url": None,
            "real_url": url
        }

@app.get("/")
def home():
    return {"status": "Stable Toss AutoFlow Backend is running"}

@app.post("/parse-custom-link")
async def parse_custom_link(req: PipelineRequest):
    try:
        share_url = build_toss_user_link(req.product_url)
        meta = parse_toss_meta(share_url)
        product_name = meta.get("title") or "토스 핫딜 추천 상품"
        features = generate_3_features(product_name, meta.get("desc", ""))

        return {
            "success": True,
            "item": {
                "id": f"custom_{int(asyncio.get_event_loop().time())}",
                "name": product_name,
                "features": features,
                "usage": meta.get("desc", "토스 파트너스 추천 상품"),
                "share_link": share_url,
                "img_url": meta.get("img_url"),
                "date": "2026-09-28",
                "reels": False, "shorts": False, "blog": False
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/fetch-trending-items")
async def fetch_trending_items():
    try:
        active_sample_links = [
            "https://toss.shopping/_m/pPn2t5qo",
            "https://toss.shopping/_m/J61l5Lsj",
            "https://toss.shopping/_m/x8K2m1Lz"
        ]
        items = []
        for idx, raw_link in enumerate(active_sample_links, 1):
            share_url = build_toss_user_link(raw_link)
            meta_info = parse_toss_meta(share_url)
            product_name = meta_info.get("title") or f"토스 추천 핫딜 {idx}호"
            
            features = generate_3_features(product_name, meta_info.get("desc", ""))
            items.append({
                "id": f"item_0{idx}",
                "name": product_name,
                "features": features,
                "usage": meta_info.get("desc", "토스 파트너스 추천 핫딜"),
                "share_link": share_url,
                "img_url": meta_info.get("img_url"),
                "date": "2026-09-28",
                "reels": False, "shorts": False, "blog": False
            })

        return {"success": True, "items": items}
    except Exception as e:
        return {"success": False, "items": [], "detail": str(e)}

@app.get("/download-video")
def download_video():
    video_path = "/tmp/output_shorts.mp4"
    if os.path.exists(video_path):
        return FileResponse(video_path, media_type="video/mp4", filename="toss_shorts.mp4")
    raise HTTPException(status_code=404, detail="영상을 찾을 수 없습니다.")

@app.get("/download-image")
def download_image():
    img_path = "/tmp/thumb.jpg"
    if os.path.exists(img_path):
        return FileResponse(img_path, media_type="image/jpeg", filename="product_thumb.jpg")
    raise HTTPException(status_code=404, detail="이미지를 찾을 수 없습니다.")

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

def create_title_card_image(title_text: str, bg_color=(25, 31, 40), text_color=(255, 255, 255), save_path="/tmp/card.jpg"):
    img = Image.new('RGB', (720, 720), color=bg_color)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    
    bbox = draw.textbbox((0, 0), title_text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text(((720 - w) / 2, (720 - h) / 2), title_text, fill=text_color, font=font)
    img.save(save_path)

def make_stable_video(audio_path: str, img_path: str, output_path: str):
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration

    # 안정적인 3단계 화면 구성 (원본 이미지 ➔ 하이라이트 1 ➔ 하이라이트 2)
    card1_path = "/tmp/card1.jpg"
    card2_path = "/tmp/card2.jpg"
    
    create_title_card_image("HOT DEAL SPECIAL", bg_color=(49, 130, 246), save_path=card1_path)
    create_title_card_image("CHECK OUT TOSS SHOPPING", bg_color=(19, 115, 51), save_path=card2_path)

    clip_dur = duration / 3.0

    c1 = ImageClip(img_path).set_duration(clip_dur).resize(width=720).set_position("center")
    c2 = ImageClip(card1_path).set_duration(clip_dur).resize(width=720).set_position("center")
    c3 = ImageClip(card2_path).set_duration(clip_dur).resize(width=720).set_position("center")

    bg1 = ImageClip(img_path).resize((720, 1280)).set_duration(clip_dur)
    bg2 = ImageClip(card1_path).resize((720, 1280)).set_duration(clip_dur)
    bg3 = ImageClip(card2_path).resize((720, 1280)).set_duration(clip_dur)

    v1 = CompositeVideoClip([bg1, c1])
    v2 = CompositeVideoClip([bg2, c2])
    v3 = CompositeVideoClip([bg3, c3])

    final_video = ConcatenateVideoClip([v1, v2, v3]).set_audio(audio_clip)

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

        model = genai.GenerativeModel('gemini-3.6-flash')
        prompt = f"상품명: '{product_title}' (구매 링크: {req.product_url})를 홍보하는 15초 숏폼 나레이션 대본을 작성해줘. 설명 없이 오직 읽을 대본 문장만 출력해줘."
        response = model.generate_content(prompt)
        script = response.text.strip()

        audio_path = "/tmp/narration.mp3"
        communicate = edge_tts.Communicate(script, "ko-KR-SunHiNeural")
        await communicate.save(audio_path)

        img_path = "/tmp/thumb.jpg"
        download_product_image(meta_info.get("img_url"), img_path)

        video_path = "/tmp/output_shorts.mp4"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, make_stable_video, audio_path, img_path, video_path)

        return {
            "success": True,
            "product_name": product_title,
            "script": script,
            "share_link": req.product_url,
            "video_url": "https://toss-automation-backend.onrender.com/download-video",
            "image_url": "https://toss-automation-backend.onrender.com/download-image"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate-blog")
async def generate_blog(req: PipelineRequest):
    try:
        if not GEMINI_KEY:
            raise HTTPException(status_code=500, detail="GEMINI_API_KEY가 설정되지 않았습니다.")

        meta_info = parse_toss_meta(req.product_url)
        product_title = meta_info.get("title") or "토스 핫딜 추천 상품"

        model = genai.GenerativeModel('gemini-3.6-flash')
        prompt = f"상품명: '{product_title}' (설명: {meta_info.get('desc')})에 대한 네이버 블로그 솔직 후기 포스팅을 작성해줘. 제목, 서론, 본문 중간 이미지 들어갈 위치 [📷 대표 상품 이미지 삽입], 주요 특징 및 추천 이유, 그리고 하단에 구매 링크({req.product_url}) 안내 문구를 포함해서 완성된 원고를 작성해줘."
        response = model.generate_content(prompt)
        blog_post = response.text.strip()

        img_path = "/tmp/thumb.jpg"
        download_product_image(meta_info.get("img_url"), img_path)

        return {
            "success": True,
            "product_name": product_title,
            "blog_post": blog_post,
            "share_link": req.product_url,
            "image_url": "https://toss-automation-backend.onrender.com/download-image"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
