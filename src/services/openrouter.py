# src/services/openrouter.py
import os
import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Model ID ကို 'google/gemma-2-9b-it:free' မှ 'google/gemma-7b-it' သို့ ပြင်ဆင်ပါမယ် (404 Error ဖြေရှင်းရန်)
NEW_MODEL = "google/gemma-7b-it" 

def get_translation(text: str):
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    # Model ID ကို ပြင်လိုက်ပါပြီ
    model = NEW_MODEL 
    
    prompt = f"""
    You are the world's best Thai ↔ Myanmar dictionary.
    Input: "{text}"
    
    - Auto-detect language
    - Translate to the other language naturally
    - Provide Romanization for Thai (in parentheses)
    - Give short definition
    - Give 1 example sentence if possible
    
    If input is Thai → respond in Myanmar
    If input is Myanmar → respond in Thai
    Be polite and natural.
    """
    
    payload = {
        "model": model,
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

def get_explanation(text: str):
    url = "https://openrouter.ai/api/v1/chat/completions"
    # Model ID ကို ပြင်လိုက်ပါပြီ
    model = NEW_MODEL 
    
    prompt = f"""
    ให้คำอธิบายเชิงลึกสำหรับคำหรือวลีนี้: "{text}"
    - ไวยากรณ์
    - การใช้จริงในชีวิตประจำวัน
    - คำที่คล้ายกัน 3-5 คำ
    - ข้อควรระวัง (ถ้ามี)
    ตอบเป็นภาษาพม่าถ้าคำถามเป็นไทย
    ตอบเป็นภาษาไทยถ้าคำถามเป็นพม่า
    """
    
    payload = {
        "model": model,
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
