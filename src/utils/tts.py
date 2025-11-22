import urllib.parse
import re

# Google TTS API Endpoint ကို အသုံးပြုသည်။
# ၎င်းသည် Thai စာသားကို လက်ခံပြီး Audio file ၏ URL ကို ပြန်ပေးသည်။
TTS_URL = "https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&tl=th&q="

def get_thai_tts_link(thai_text: str) -> str:
    """
    ထိုင်းဘာသာစကား စာသားကို Google TTS မှတဆင့် MP3 URL ထုတ်ပေးသည်။
    
    Args:
        thai_text: ထိုင်းဘာသာစကား စာသား (Romanization မဟုတ်ပါ)
        
    Returns:
        MP3 file ၏ တိုက်ရိုက် URL
    """
    # စာသားကို URL-safe ဖြစ်အောင် Encode လုပ်သည်
    encoded_text = urllib.parse.quote(thai_text)
    
    # Complete URL ကို ပြန်ပေးသည်
    return f"{TTS_URL}{encoded_text}"
