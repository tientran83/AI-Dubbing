import os
import re
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai

app = FastAPI()

class DubRequest(BaseModel):
    youtube_url: str

def extract_video_id(url: str) -> str:
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
    if match:
        return match.group(1)
    raise ValueError("Đường dẫn YouTube không hợp lệ!")

@app.get("/", response_class=HTMLResponse)
def read_root():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/translate-transcript")
async def translate_transcript(req: DubRequest):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Chưa cấu hình GEMINI_API_KEY!")

    try:
        video_id = extract_video_id(req.youtube_url)
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'vi', 'ja', 'ko'])
        full_text = " ".join([item['text'] for item in transcript_list[:15]])

        client = genai.Client(api_key=api_key)
        prompt = (
            "Bạn là một biên dịch viên video chuyên nghiệp. "
            "Hãy dịch đoạn văn bản phụ đề sau sang tiếng Việt tự nhiên, chuẩn văn phong lồng tiếng:\n\n"
            f"{full_text}"
        )
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        return {
            "status": "success",
            "original_text": full_text,
            "translated_text": response.text
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))