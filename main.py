import os
import re
import json
import urllib.request
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from google import genai
import yt_dlp

app = FastAPI()

class DubRequest(BaseModel):
    youtube_url: str

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.get("/", response_class=HTMLResponse)
def read_root():
    file_path = os.path.join(BASE_DIR, "index.html")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def get_transcript_with_ytdlp(url: str) -> str:
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en', 'vi', 'ja', 'ko'],
        'quiet': True,
        'no_warnings': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        subtitles = info.get('subtitles') or info.get('automatic_captions')
        
        if not subtitles:
            raise Exception("Video này không có phụ đề để trích xuất!")
        
        # Chọn ngôn ngữ ưu tiên
        selected_lang = None
        for lang in ['en', 'vi', 'ja', 'ko']:
            if lang in subtitles:
                selected_lang = lang
                break
        if not selected_lang:
            selected_lang = list(subtitles.keys())[0]

        # Lấy link tải phụ đề (ưu tiên định dạng json3)
        formats = subtitles[selected_lang]
        sub_url = None
        for fmt in formats:
            if fmt.get('ext') == 'json3':
                sub_url = fmt.get('url')
                break
        if not sub_url:
            sub_url = formats[0].get('url')

        # Tải nội dung phụ đề
        req = urllib.request.Request(sub_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            content = response.read().decode('utf-8')

        # Bóc tách câu chữ
        try:
            data = json.loads(content)
            texts = []
            for event in data.get('events', []):
                if 'segs' in event:
                    text = "".join([seg.get('utf8', '') for seg in event['segs']]).strip()
                    if text and text != '\n':
                        texts.append(text)
            return " ".join(texts[:30])
        except Exception:
            clean_text = re.sub(r'<[^>]+>', '', content)
            lines = [l.strip() for l in clean_text.splitlines() if l.strip() and not l.startswith('WEBVTT') and '-->' not in l]
            return " ".join(lines[:30])

@app.post("/api/translate-transcript")
async def translate_transcript(req: DubRequest):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Chưa cấu hình GEMINI_API_KEY!")

    try:
        full_text = get_transcript_with_ytdlp(req.youtube_url)
        
        client = genai.Client(api_key=api_key)
        prompt = (
            "Bạn là một biên dịch viên video chuyên nghiệp. "
            "Hãy dịch đoạn văn bản phụ đề sau sang tiếng Việt tự nhiên, chuẩn văn phong lồng tiếng:\n\n"
            f"{full_text}"
        )
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        
        return {"translated_text": response.text}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
