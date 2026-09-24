import os
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_KEY)

class PipelineRequest(BaseModel):
    product_url: str

@app.get("/")
def home():
    return {"status": "Server is running"}

@app.post("/run-pipeline")
def run_pipeline(req: PipelineRequest):
    try:
        # 1. 간단 상품 파싱 (클라우드 환경에 맞춰 가볍게 처리)
        product_title = "토스 핫딜 추천 상품"
        
        # 2. OpenAI 대본 및 TTS 생성
        prompt = f"토스 추천 상품 링크({req.product_url})를 홍보하는 15초 숏폼 나레이션 대본을 써줘. 다른 말 없이 대본만 출력해줘."
        res = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        script = res.choices[0].message.content.strip()

        # TTS 생성
        audio_path = "/tmp/narration.mp3"
        tts_res = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=script
        )
        tts_res.stream_to_file(audio_path)

        # 3. 임시 이미지 다운로드 및 영상 합성 (MoviePy)
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
        final_video.write_videofile(video_path, fps=24, codec="libx264", audio_codec="aac", logger=None)

        return {
            "success": True,
            "script": script,
            "message": "영상이 정상적으로 생성되었습니다."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))