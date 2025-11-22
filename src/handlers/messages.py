import os
import tempfile
import asyncio
import re
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ContextTypes

# OpenRouter (Service)
from src.services.openrouter import get_translation, get_explanation
# Audio Utils (Existing)
from src.utils.audio import convert_ogg_to_mp3
from src.utils.state import is_bot_active
from src.config import ADMIN_IDS

# Audio for TTS (New)
from gtts import gTTS

# --- REGEX PATTERNS (Improved) ---
# AI က Format အမျိုးမျိုးပေးလာရင် ဖမ်းလို့ရအောင် ပြင်ထားသည်
TRANSLATION_PATTERN = re.compile(r'\*\*.*Translation\*\*:\s*(.+)', re.IGNORECASE)
ROMANIZATION_PATTERN = re.compile(r'\*\*.*Romanization\*\*:\s*(.+)', re.IGNORECASE)
DEFINITION_PATTERN = re.compile(r'\*\*.*Definition\*\*:\s*(.+)', re.IGNORECASE)
EXAMPLE_PATTERN = re.compile(r'\*\*.*Example.*?\*\*:\s*(.+)', re.IGNORECASE)

# Helper: Clean up markdown artifacts (*ဖြုတ်ရန်)
def clean_text(text):
    if text:
        return text.replace('*', '').strip()
    return ""

# Helper function for formatting
def format_ai_response(raw_text: str) -> tuple[str, str]:
    """
    AI Output ကို လှလှပပ Card ပုံစံ ပြင်မည်။
    """
    # 1. Data Extract
    translation_match = TRANSLATION_PATTERN.search(raw_text)
    romanization_match = ROMANIZATION_PATTERN.search(raw_text)
    definition_match = DEFINITION_PATTERN.search(raw_text)
    example_match = EXAMPLE_PATTERN.search(raw_text)

    # Data မတွေ့ရင် Raw အတိုင်းပြန်ပေးမယ် (Error/Chat message ဖြစ်နိုင်လို့)
    if not translation_match:
        return raw_text, ""

    trans_text = clean_text(translation_match.group(1))
    roman_text = clean_text(romanization_match.group(1)) if romanization_match else ""
    def_text = clean_text(definition_match.group(1)) if definition_match else ""
    ex_text = clean_text(example_match.group(1)) if example_match else ""

    # 2. Output Design (Visual Upgrade)
    # Header
    formatted_output = (
        f"🎯 <b>Translation</b>\n"
        f"╰┈➤ <code>{trans_text}</code>\n\n"
    )

    thai_text_for_tts = ""
    
    # Romanization & Pronunciation logic
    if roman_text:
        formatted_output += (
            f"🗣️ <b>Pronunciation</b>\n"
            f"╰┈➤ <i>{roman_text}</i>\n\n"
        )
        # Romanization ထဲက ထိုင်းစာလုံးကို ရှာဖွေခြင်း (အသံထွက်ဖွင့်ဖို့)
        thai_char_match = re.search(r'([ก-๙]+)', roman_text)
        if thai_char_match:
            thai_text_for_tts = thai_char_match.group(1)
        else:
            # Romanization မှာမပါရင် Translation ကဟာကို ယူမယ် (အကယ်၍ ထိုင်းပြန်လာတာဆိုရင်)
            if re.search(r'[ก-๙]', trans_text):
                thai_text_for_tts = trans_text

    # Definition
    if def_text:
        formatted_output += (
            f"📚 <b>Definition</b>\n"
            f"╰┈➤ {def_text}\n\n"
        )

    # Example
    if ex_text:
        formatted_output += (
            f"📝 <b>Example</b>\n"
            f"╰┈➤ {ex_text}\n"
        )

    formatted_output += "\n─────────────────"

    return formatted_output, thai_text_for_tts

# --- NEW: Send Audio Directly (Memory Stream) ---
async def send_audio_pronunciation(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Google TTS ကိုသုံးပြီး Server မှာ ဖိုင်မသိမ်းဘဲ အသံပို့မည်"""
    if not text: return

    try:
        # In-memory binary stream (Zeabur storage မပြည့်အောင်)
        tts = gTTS(text=text, lang='th')
        audio_fp = BytesIO()
        tts.write_to_fp(audio_fp)
        audio_fp.seek(0)
        
        # Voice Message အနေနဲ့ ပို့မည်
        await context.bot.send_voice(
            chat_id=update.effective_chat.id, 
            voice=audio_fp, 
            caption="🔊 အသံထွက်"
        )
    except Exception as e:
        print(f"TTS Error: {e}")
        # အသံမရရင် ဘာမှမလုပ်ဘဲ ကျော်သွားမယ် (Error မပြဘူး)

# /start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 <b>မင်္ဂလာပါ! (Sawadee Krub/Ka)</b>\n\n"
        "ကျွန်တော်က ထိုင်း-မြန်မာ အပြန်အလှန် ဘာသာပြန် Bot ပါ။\n"
        "🤖 AI နည်းပညာကို သုံးထားပါတယ်။\n\n"
        "👉 <b>အသုံးပြုနည်း:</b>\n"
        "• ထိုင်း (သို့) မြန်မာလို စာရိုက်ပို့လိုက်ပါ။\n"
        "• အသံထွက်ကိုပါ တခါတည်း နားထောင်နိုင်ပါတယ်။\n\n"
        "✨ <b>Developed by @MyanmarTecharea</b>"
    )
    await update.message.reply_text(welcome_text, parse_mode=constants.ParseMode.HTML)


# Core processing function
async def _process_and_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, user_input, is_audio=False):
    MAX_RETRIES = 2
    RETRY_DELAY = 2

    # Typing action ပြမည်
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)

    for attempt in range(MAX_RETRIES + 1):
        try:
            # 1. OpenRouter Call
            raw_response_text = await asyncio.to_thread(get_translation, user_input)

            if "Error" in raw_response_text:
                raise Exception(f"API Error")

            # 2. Format Response
            formatted_text, thai_text = format_ai_response(raw_response_text)
            
            context.user_data['last_sender'] = update.effective_user.id
            context.user_data['last_query'] = user_input

            # 3. Buttons
            keyboard_rows = []
            keyboard_rows.append([InlineKeyboardButton("📝 ရှင်းလင်းချက် ထပ်ကြည့်မယ်", callback_data="explain")])
            reply_markup = InlineKeyboardMarkup(keyboard_rows)

            # 4. Send Text Reply First
            await update.message.reply_text(
                formatted_text,
                reply_markup=reply_markup,
                parse_mode=constants.ParseMode.HTML
            )

            # 5. Send Audio (အသံဖိုင်ကို သီးသန့်ပို့မည်)
            if thai_text:
                # အသံသွင်းနေသည့် Action ပြမည်
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.RECORD_VOICE)
                await send_audio_pronunciation(update, context, thai_text)

            return

        except Exception as e:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
            else:
                await update.message.reply_text(f"⚠️ ယာယီချို့ယွင်းချက်ရှိနေပါသည်။\nError: {str(e)}")


# Text message handler
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_bot_active() and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔️ Bot ပြုပြင်နေပါသည်။")
        return

    user_text = update.message.text.strip()
    if user_text:
        await _process_and_reply(update, context, user_text)


# Voice message handler (မူလအတိုင်းထားသည်)
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_bot_active() and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔️ Bot ပြုပြင်နေပါသည်။")
        return

    voice_file = update.message.voice
    if not voice_file: return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.UPLOAD_PHOTO)
    status_message = await update.message.reply_text("🎤 <b>အသံကို နားထောင်နေပါသည်...</b>", parse_mode=constants.ParseMode.HTML)

    try:
        # Temp directory helps in Cloud/PaaS environments for short-lived files
        with tempfile.TemporaryDirectory() as tmp_dir:
            ogg_path = os.path.join(tmp_dir, "voice.ogg")
            mp3_path = os.path.join(tmp_dir, "voice.mp3")

            await voice_file.download_to_drive(ogg_path)

            if convert_ogg_to_mp3(ogg_path, mp3_path):
                # Note: OpenRouter usually doesn't support direct audio upload yet in this template
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=status_message.message_id,
                    text="⚠️ Audio transcription API မရသေးပါ။ စာရိုက်ပို့ပေးပါ။"
                )
            else:
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=status_message.message_id,
                    text="❌ အသံဖိုင် Error"
                )
    except Exception as e:
        await update.message.reply_text("Error handling voice.")


# Callback Handler
async def user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data.startswith("admin_"): return
    await query.answer()

    if query.data == "explain":
        last_text = context.user_data.get('last_query')
        if last_text:
            await query.message.reply_text("⏳ ရှင်းပြနေပါသည်...")
            explanation = await asyncio.to_thread(get_explanation, last_text)
            await query.message.reply_text(f"📖 <b>ရှင်းလင်းချက်:</b>\n\n{explanation}", parse_mode=constants.ParseMode.HTML)
        else:
            await query.message.reply_text("Data မရှိတော့ပါ။")
