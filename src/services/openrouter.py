import os
import requests
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# API Key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ================================
#  Gemini 2.0 Flash Experimental FREE MODEL
# ================================
NEW_MODEL = "google/gemini-2.0-flash-exp:free"

# -------------------------------------------------
#  Thai ↔ Myanmar Translation Function
# -------------------------------------------------
def get_translation(text: str):
    url = "https://openrouter.ai/api/v1/chat/completions"

    prompt = f"""
    You are the world's best Thai ↔ Myanmar dictionary.
    Input: "{text}"

    - Auto-detect input language
    - Translate naturally
    - Provide Romanization for Thai
    - Give short definition
    - Provide at least 1 example sentence

    If input is Thai → answer in Myanmar
    If input is Myanmar → answer in Thai
    """

    payload = {
        "model": NEW_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 600
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": os.getenv("WEBHOOK_HOST", "https://yourbot.com"),
        "X-Title": "Thai-Myanmar Dictionary"
    }

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    except Exception as e:
        return f"ขออภัย ระบบมีปัญหาชั่วคราว: {str(e)}"


# -------------------------------------------------
#  Word/phrase Explanation Function
# -------------------------------------------------
def get_explanation(text: str):
    url = "https://openrouter.ai/api/v1/chat/completions"

    prompt = f"""
    ให้คำอธิบายเชิงลึกสำหรับคำหรือวลีนี้: "{text}"
    - ไวยากรณ์ที่เกี่ยวข้อง
    - การใช้จริงในชีวิตประจำวัน
    - คำที่มีความหมายใกล้เคียง 3-5 คำ
    - ข้อควรระวัง (ถ้ามี)

    ตอบเป็นภาษาพม่าถ้าคำถามเป็นไทย  
    ตอบเป็นภาษาไทยถ้าคำถามเป็นพม่า
    """

    payload = {
        "model": NEW_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5,
        "max_tokens": 800
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": os.getenv("WEBHOOK_HOST", "https://yourbot.com"),
        "X-Title": "Thai-Myanmar Dictionary"
    }

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=40)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    except Exception as e:
        return "ไม่สามารถอธิบายเพิ่มเติมได้ในขณะนี้"
