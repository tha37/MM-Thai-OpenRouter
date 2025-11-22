import os
import requests
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# API Key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ================================
#  Gemini 2.0 Flash Experimental (Free)
# ================================
NEW_MODEL = "google/gemini-2.0-flash-exp:free"

# -------------------------------------------------
#  Thai ↔ Myanmar Translation Function
# -------------------------------------------------
def get_translation(text: str):
    url = "https://openrouter.ai/api/v1/chat/completions"

    # Prompt: Format အတိအကျရအောင် ခိုင်းစေခြင်း
    prompt = f"""
    You are a professional Thai-Myanmar dictionary.
    Input: "{text}"

    INSTRUCTIONS:
    1. Detect input language (Thai or Myanmar).
    2. If Input is Thai -> Translate to Myanmar.
    3. If Input is Myanmar -> Translate to Thai.
    4. Provide the output strictly in the following format.

    REQUIRED FORMAT:
    Translation: [The translated text]
    Romanization: [Pronunciation]
    Definition: [Short definition]
    Example: [One example sentence]
    """

    payload = {
        "model": NEW_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 800,
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": os.getenv("WEBHOOK_HOST", "https://yourbot.com"),
        "X-Title": "Thai-Myanmar Dictionary"
    }

    try:
        # TIMEOUT INCREASED: 60 seconds
        # Free model တွေက ကြာတတ်လို့ စက္ကန့် ၆၀ အထိ စောင့်ခိုင်းလိုက်တာပါ
        r = requests.post(url, json=payload, headers=headers, timeout=60)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    except Exception as e:
        print(f"❌ Translation API Error: {e}")
        return f"Error: {str(e)}"


# -------------------------------------------------
#  Word/phrase Explanation Function
# -------------------------------------------------
def get_explanation(text: str):
    url = "https://openrouter.ai/api/v1/chat/completions"

    prompt = f"""
    Explain this word/phrase in detail: "{text}"
    - Usage
    - Synonyms (3-5 words)
    - Example
    - Caution (if any)

    Language Rule:
    - If input is Thai, explain in Myanmar.
    - If input is Myanmar, explain in Thai.
    """

    payload = {
        "model": NEW_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5,
        "max_tokens": 1000
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": os.getenv("WEBHOOK_HOST", "https://yourbot.com"),
        "X-Title": "Thai-Myanmar Dictionary"
    }

    try:
        # TIMEOUT INCREASED: 60 seconds
        r = requests.post(url, json=payload, headers=headers, timeout=60)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    except Exception as e:
        print(f"❌ Explanation API Error: {e}")
        return "မေးမြန်းမှု များပြားနေပါသဖြင့် ခေတ္တစောင့်ဆိုင်းပေးပါ။"
