import os
import requests
import logging
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Logging Setup (Terminal မှာ Error တွေကို ထင်ထင်ရှားရှားပြဖို့)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
NEW_MODEL = "google/gemini-2.0-flash-exp:free"

def get_translation(text: str):
    url = "https://openrouter.ai/api/v1/chat/completions"

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
        logger.info(f"Sending request to OpenRouter... Input: {text[:20]}...")
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        
        # API က 200 OK မပြန်ရင် Error အကြောင်းရင်းကို Terminal မှာ ထုတ်ပြမယ်
        if response.status_code != 200:
            error_msg = response.text
            logger.error(f"❌ API Request Failed: Status {response.status_code}")
            logger.error(f"❌ Error Details: {error_msg}")
            return f"Error: API returned {response.status_code}"

        return response.json()["choices"][0]["message"]["content"]

    except requests.exceptions.Timeout:
        logger.error("❌ Request Timed Out (60s)")
        return "Error: Connection Timed Out"
    except Exception as e:
        logger.error(f"❌ Unexpected Error: {str(e)}")
        return f"Error: {str(e)}"


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
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        if response.status_code != 200:
            logger.error(f"❌ Explanation API Failed: {response.text}")
            return "Error: API Failed"
            
        return response.json()["choices"][0]["message"]["content"]

    except Exception as e:
        logger.error(f"❌ Explanation Error: {e}")
        return "မေးမြန်းမှု များပြားနေပါသဖြင့် ခေတ္တစောင့်ဆိုင်းပေးပါ။"
