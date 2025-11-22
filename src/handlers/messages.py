import os
import tempfile
import asyncio
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ContextTypes
from gtts import gTTS  # gTTS library လိုအပ်သည်

# OpenRouter
from src.services.openrouter import get_translation, get_explanation
from src.utils.audio import convert_ogg_to_mp3
from src.utils.state import is_bot_active
from src.config import ADMIN_IDS

# Regex Patterns (OpenRouter မှ ပြန်လာမည့် Format ကို ဖမ်းရန်)
TRANSLATION_PATTERN = re.compile(r'Translation:\s*(.+)', re.IGNORECASE)
ROMANIZATION_PATTERN = re.compile(r'Romanization:\s*(.+)', re.IGNORECASE)
DEFINITION_PATTERN = re.compile(r'Definition:\s*(.+)', re.IGNORECASE)
EXAMPLE_PATTERN = re.compile(r'Example:\s*(.+)', re.IGNORECASE)

def is_thai(text):
    """စာသားထဲမှာ ထိုင်းစာလုံးပါမပါ စစ်ဆေးခြင်း"""
    return bool(re.search(r'[\u0E00-\u0E7F]', text))

def format_ai_response(raw_text: str, user_input: str) -> tuple[str, str, str]:
    """
    AI response ကို ပုံစံချခြင်း နှင့် TTS အတွက် စကားလုံးရွေးထုတ်ခြင်း
    Returns: (formatted_html, tts_text, tts_lang)
    """
    translation_match = TRANSLATION_PATTERN.search(raw_text)
    romanization_match = ROMANIZATION_PATTERN.search(raw_text)
    definition_match = DEFINITION_PATTERN.search(raw_text)
    example_match = EXAMPLE_PATTERN.search(raw_text)

    # AI က Format အတိုင်းမပေးရင် မူရင်းအတိုင်းပြန်ပြ (TTS မပါ)
    if not translation_match:
        return raw_text, "", ""

    # Data များကို ဆွဲထုတ်ခြင်း
    trans_text = translation_match.group(1).strip()
    roman_text = romanization_match.group(1).strip() if romanization_match else "-"
    def_text = definition_match.group(1).strip() if definition_match else "-"
    ex_text = example_match.group(1).strip() if example_match else "-"

    # === Logic for TTS & Formatting ===
    input_is_thai = is_thai(user_input)

    if input_is_thai:
        # Input: Thai -> Output: Myanmar
        # User က ထိုင်းလိုမေးရင် မြန်မာလိုပြန်ဖြေမယ် -> TTS က "အဖြေ" (မြန်မာ) ဖြစ်ရမယ်
        detected_lang_str = "🇹🇭 Thai (Detected)"
        tts_text = trans_text  
        tts_lang = 'my'        # Myanmar TTS
    else:
        # Input: Myanmar -> Output: Thai
        # User က မြန်မာလိုမေးရင် ထိုင်းလိုပြန်ဖြေမယ် -> TTS က "အဖြေ" (ထိုင်း) ဖြစ်ရမယ်
        detected_lang_str = "🇲🇲 Myanmar (Detected)"
        tts_text = trans_text  
        tts_lang = 'th'        # Thai TTS

    # 🎨 Output Design (ပုံထဲကအတိုင်း သပ်ရပ်အောင် ပြင်ဆင်ခြင်း)
    formatted_output = (
        f"🔍 <b>Input:</b> {user_input}\n"
        f"🏳️ <b>Language:</b> {detected_lang_str}\n"
        f"──────────────────\n"
        f"🎯 <b>Translation:</b> {trans_text}\n"
        f"🗣️ <b>Romanization:</b> <i>{roman_text}</i>\n\n"
        f"📖 <b>Definition:</b>\n{def_text}\n\n"
        f"📝 <b>Example:</b>\n{ex_text}"
    )

    return formatted_output, tts_text, tts_lang


# /start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🙏 <b>မင်္ဂလာပါ! (Sawadee Krub/Ka)</b>\n\n"
        "ကျွန်တော်က ထိုင်း-မြန်မာ အပြန်အလှန် ဘာသာပြန် Bot ပါ။\n\n"
        "👉 <b>အသုံးပြုနည်း:</b>\n"
        "1. ထိုင်းစာရိုက်ရင် -> မြန်မာလိုပြန်ဖြေပြီး မြန်မာအသံထွက်ပို့ပေးမယ်။\n"
        "2. မြန်မာစာရိုက်ရင် -> ထိုင်းလိုပြန်ဖြေပြီး ထိုင်းအသံထွက်ပို့ပေးမယ်။\n"
        "---"
        "✨ <b>Developed by @MyanmarTecharea</b>"
    )
    await update.message.reply_text(welcome_text, parse_mode=constants.ParseMode.HTML)


async def send_tts_voice(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, lang: str):
    """ gTTS အသုံးပြုပြီး အသံထွက် ပို့ပေးခြင်း (lang = 'th' or 'my') """
    if not text: return

    try:
        # Clean text for TTS (remove brackets, special chars mainly for Thai/Burmese)
        # ရိုးရိုးရှင်းရှင်း စာသားပဲကျန်အောင် ရှင်းထုတ်ခြင်း
        clean_text = re.sub(r'[^\w\s\u0E00-\u0E7F\u1000-\u109F]', '', text).strip()
        
        if not clean_text: return

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.RECORD_VOICE)
        
        # gTTS ဖြင့် အသံဖိုင်ထုတ်ခြင်း
        tts = gTTS(text=clean_text, lang=lang)
        
        # Temp file သုံးပြီး ပို့ခြင်း
        with tempfile.NamedTemporaryFile(delete=True, suffix='.mp3') as fp:
            tts.save(fp.name)
            fp.seek(0)
            caption_text = "🗣️ ထိုင်းအသံထွက်" if lang == 'th' else "🗣️ မြန်မာအသံထွက်"
            await update.message.reply_voice(voice=open(fp.name, 'rb'), caption=caption_text)
            
    except Exception as e:
        print(f"TTS Error: {e}")
        # TTS error တက်ရင် User ကို အသိမပေးဘဲ ကျော်သွားပါမယ်


async def _process_and_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, user_input, is_audio=False):
    MAX_RETRIES = 2
    RETRY_DELAY = 5

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)

    for attempt in range(MAX_RETRIES + 1):
        try:
            # 1. OpenRouter မှ ဘာသာပြန်ရယူခြင်း
            raw_response_text = await asyncio.to_thread(get_translation, user_input)

            if "Error" in raw_response_text:
                raise Exception(f"API Error: {raw_response_text}")

            # 2. Format လုပ်ခြင်း (TTS ဘာသာစကားပါ ခွဲခြားခြင်း)
            formatted_text, tts_text, tts_lang = format_ai_response(raw_response_text, user_input)
            
            # Save context for "Explain More"
            context.user_data['last_sender'] = update.effective_user.id
            context.user_data['last_query'] = user_input

            # 3. Keyboard
            keyboard = [[InlineKeyboardButton("📝 ရှင်းလင်းချက် ထပ်ကြည့်မယ်", callback_data="explain")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # 4. စာသားပြန်ပို့ခြင်း
            await update.message.reply_text(
                formatted_text,
                reply_markup=reply_markup,
                parse_mode=constants.ParseMode.HTML
            )

            # 5. TTS အသံဖိုင် ပို့ခြင်း
            if tts_text and tts_lang:
                await send_tts_voice(update, context, tts_text, tts_lang)
            
            return

        except Exception as e:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
            else:
                await update.message.reply_text("⚠️ ယာယီချို့ယွင်းချက်ရှိနေပါသည်။ ခဏနောက် ထပ်ကြိုးစားကြည့်ပါ။")


# Text Handler
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_bot_active() and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔️ Bot ကို ပြုပြင်နေပါသည်။")
        return

    user_text = update.message.text.strip()
    if user_text:
        await _process_and_reply(update, context, user_text)


# Voice Handler (Speech-to-Text မပါသေးပါ)
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_bot_active() and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔️ Bot ကို ပြုပြင်နေပါသည်။")
        return

    voice_file = update.message.voice
    if not voice_file: return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.UPLOAD_PHOTO)
    status_msg = await update.message.reply_text("🎤 **အသံကို ဘာသာပြန်နေပါသည်...**")

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            ogg_path = os.path.join(tmp_dir, "voice.ogg")
            mp3_path = os.path.join(tmp_dir, "voice.mp3")
            await voice_file.download_to_drive(ogg_path)

            if convert_ogg_to_mp3(ogg_path, mp3_path):
                # ယာယီအားဖြင့် STT မရသေးကြောင်း အကြောင်းပြန်သည်
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=status_msg.message_id,
                    text="⚠️ Speech-to-Text API မရှိသေးပါ။ စာရိုက်ပေးပို့ပါ။"
                )
            else:
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=status_msg.message_id,
                    text="❌ Error converting audio."
                )
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")


# Callback Handler
async def user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data.startswith("admin_"): return
    await query.answer()

    if query.data == "explain":
        last_text = context.user_data.get('last_query')
        if last_text:
            await query.message.reply_text("⏳ အသေးစိတ်ရှင်းပြနေသည်...")
            explanation = await asyncio.to_thread(get_explanation, last_text)
            await query.message.reply_text(f"📖 <b>ရှင်းလင်းချက်:</b>\n\n{explanation}", parse_mode=constants.ParseMode.HTML)
        else:
            await query.message.reply_text("အရင်မေးခွန်း မတွေ့ပါ။")
