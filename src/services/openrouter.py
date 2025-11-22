# src/services/openrouter.py
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Global variable for caching the selected model ID
_SELECTED_MODEL = None 
# Model ID အမှန်ကို ပြင်ဆင်လိုက်ပါပြီ
DEFAULT_FALLBACK_MODEL = "google/gemini-2.0-flash-exp-free" 

def _get_best_free_model():
    """
    OpenRouter API မှ Model List ကို ခေါ်ယူပြီး Free ဖြစ်သော အကောင်းဆုံး Model တစ်ခုကို ရွေးချယ်သည်
    (Model ID ကို 404 Error မဖြစ်စေရန် စစ်ဆေးသည်)
    """
    global _SELECTED_MODEL
    if _SELECTED_MODEL:
        return _SELECTED_MODEL
    
    url = "https://openrouter.ai/api/v1/models"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": os.getenv("WEBHOOK_HOST", "https://yourbot.com"),
        "X-Title": "Thai-Myanmar Dictionary"
    }

    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        
        target_model_id = DEFAULT_FALLBACK_MODEL
        
        # 1. Target Model ကို ဦးစားပေး စစ်ဆေးခြင်း
        for model in data.get('data', []):
            input_cost = model.get('pricing', {}).get('prompt', 1) 
            output_cost = model.get('pricing', {}).get('completion', 1) 
            
            # Target Model ကို တွေ့ပြီး အခမဲ့ဖြစ်ရင် ရွေးချယ်သည်
            if model['id'] == target_model_id and input_cost == 0 and output_cost == 0:
                _SELECTED_MODEL = target_model_id
                print(f"Info: Found and selected the target model: {target_model_id}")
                return _SELECTED_MODEL
        
        # 2. Target Model မတွေ့ပါက Free Model အခြားတစ်ခုကို ရွေးခြင်း
        for model in data.get('data', []):
            input_cost = model.get('pricing', {}).get('prompt', 1) 
            output_cost = model.get('pricing', {}).get('completion', 1) 
            
            # အခမဲ့ Model များကို စစ်ထုတ်ခြင်း (ပထမဆုံးတွေ့သည်ကို ရွေးမည်)
            if input_cost == 0 and output_cost == 0:
                _SELECTED_MODEL = model['id']
                print(f"Warning: Target model not found. Using the first available free model: {_SELECTED_MODEL}")
                return _SELECTED_MODEL

        # 3. အခမဲ့ Model လုံးဝ မတွေ့ပါက Default သို့ ပြန်သွားခြင်း
        print(f"Warning: No free model found on OpenRouter. Using default fallback: {DEFAULT_FALLBACK_MODEL}")
        _SELECTED_MODEL = DEFAULT_FALLBACK_MODEL
        return _SELECTED_MODEL

    except Exception as e:
        # API ခေါ်ယူရာတွင် ပြဿနာရှိပါက Default ကိုသာ သုံးမည်
        print(f"Error fetching model list: {str(e)}. Using default fallback: {DEFAULT_FALLBACK_MODEL}")
        _SELECTED_MODEL = DEFAULT_FALLBACK_MODEL
        return _SELECTED_MODEL

# ဤနေရာမှ စတင်အသုံးပြုပါမည် (တစ်ကြိမ်သာ ခေါ်ယူပါမည်)
SELECTED_MODEL = _get_best_free_model()

# =========================================================

# Helper function to ensure prompt is reliable
def _clean_ai_output(output_text: str) -> dict:
    """AI output ကို ခွဲခြမ်းစိတ်ဖြာပြီး Dictionary အဖြစ် ပြန်ပေးသည်"""
    data = {
        'translation': '', 'romanization': '', 'definition': '',
        'thai_text': '', 'is_thai_input': False
    }
    
    # Thai input ကို ထုတ်ယူရန်အတွက် Regex ကို အသုံးပြုပါ
    thai_match = re.search(r'Thai: (.+?)\n', output_text, re.IGNORECASE)
    if thai_match:
        data['thai_text'] = thai_match.group(1).strip()
    
    # Output ကို လိုင်းအလိုက် ခွဲခြမ်းစိတ်ဖြာပြီး Data ထုတ်ယူပါ (AI က ဖွဲ့စည်းပုံ မှန်မှန်ပြန်ပေးဖို့ မျှော်လင့်ရမည်)
    # ဒါဟာ AI output ပုံစံပေါ် မူတည်ပြီး အလုပ်လုပ်ပါမယ်
    data['translation'] = re.search(r'\*\*Translation\*\*: (.+?)\n', output_text)
    if not data['translation']:
        # အကယ်၍ AI က Structured Format နဲ့ မပြန်ရင် စာသားတစ်ခုလုံးကို Translation အဖြစ်ယူပါမည်
        data['translation'] = output_text 

    # Simplified parsing logic (AI က မူရင်းစကားလုံးကို ပြန်ထည့်ပေးဖို့ မျှော်လင့်ပါသည်)
    if "Input:" in output_text:
        input_text_match = re.search(r'Input: "(.+?)"', output_text)
        if input_text_match and thai_match:
            # Input က ထိုင်းဖြစ်ကြောင်း ယူဆပါမည်
             data['is_thai_input'] = True
    
    return data

def get_translation(text: str):
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    model = SELECTED_MODEL  
    
    # Prompt ကို Structured output ရစေရန် ပိုမိုပြင်းထန်စွာ ညွှန်ကြားခြင်း
    prompt = f"""
    You are the world's best Thai ↔ Myanmar dictionary.
    Input: "{text}"
    
    Analyze the input language and provide a highly structured, step-by-step response.
    
    **Structure required:**
    **1. Detected Language:** [Detected Language]
    **2. Translation:** [The translated text]
    **3. Romanization:** [Thai Romanization only, if input was Thai]
    **4. Definition:** [A short, concise definition]
    **5. Example Sentence:** [One relevant example sentence]
    
    If input is Thai, ensure "Thai:" is explicitly stated in the Romanization section.
    If input is Myanmar, ensure "Myanmar:" is explicitly stated in the Translation section.
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
    
    model = SELECTED_MODEL 
    
    prompt = f"""
    ให้คำอธิบายเชิงลึกสำหรับคำหรือวลีนี้: "{text}"
    
    **Structure required:**
    **1. Grammar:** [Related grammar]
    **2. Usage:** [Real-life daily usage]
    **3. Similar Words:** [3-5 similar words]
    **4. Caution:** [Any caution/warning]

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
