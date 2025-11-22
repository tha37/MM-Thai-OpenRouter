import os
import tempfile
import asyncio
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ContextTypes

# OpenRouter ကို သုံးဖို့
from src.services.openrouter import get_translation, get_explanation
from src.utils.audio import convert_ogg_to_mp3
from src.utils.state import is_bot_active
from src.config import ADMIN_IDS
# TTS Link အတွက် Utility အသစ်
from src.utils.tts import get_thai_tts_link

# Regular Expression to extract structured data from AI response
# AI ကို structured format နဲ့ပြန်ပေးဖို့ အားထုတ်ခိုင်းထားတဲ့အတွက် ဒီ Regex တွေနဲ့ ခွဲထုတ်ပါမယ်
TRANSLATION_PATTERN = re.compile(r'\*\*2\. Translation\*\*: (.+)', re.IGNORECASE)
ROMANIZATION_PATTERN = re.compile(r'\*\*3\. Romanization\*\*: (.+)', re.IGNORECASE)
DEFINITION_PATTERN = re.compile(r'\*\*4\. Definition\*\*: (.+)', re.IGNORECASE)
EXAMPLE_PATTERN = re.compile(r'\*\*5\. Example Sentence\*\*: (.+)', re.IGNORECASE)

# Helper function for formatting
def format_ai_response(raw_text: str) -> tuple[str, str]:
    """
    AI က ပြန်ပေးတဲ့ စာသားကို ခွဲခြမ်းစိတ်ဖြာပြီး Emoji/HTML format နဲ့ ပြန်ပေးသည်။
    :return: (formatted_text, thai_text_for_tts)
    """
    
    # 1. Data ကို ထုတ်ယူပါ
    translation = TRANSLATION_PATTERN.search(raw_text)
    romanization = ROMANIZATION_PATTERN.search(raw_text)
    definition = DEFINITION_PATTERN.search(raw_text)
    example = EXAMPLE_PATTERN.search(raw_text)
    
    thai_text_for_tts = "" # TTS အတွက် ထိုင်းစာသား သိမ်းရန်
    
    # 2. Output Formatting လုပ်ပါ
    formatted_output = ""
    
    # Translation (မဖြစ်မနေ ပါရမည့် အချက်)
    trans_text = translation.group(1).strip() if translation else raw_text
    formatted_output += f"🇲🇲 🇹🇭 <b>{trans_text}</b>\n\n"
    
    if romanization:
        # Romanization က (Thai) စာသားပါရမည်
        roman_text = romanization.group(1).strip()
        # 3. TTS အတွက် ထိုင်းစာသားကို Romanization အပိုင်းကနေ ယူသည်
        # AI က 'Thai: คำ' (သို့) 'คำ' ကိုသာ ပေးဖို့ မျှော်လင့်ပါသည်
        thai_match = re.search(r'(Thai:)?\s*([ก-๙\s\(\)]+)', roman_text)
        if thai_match:
             thai_text_for_tts = thai_match.group(2).strip().replace('(', '').replace(')', '')
        
        formatted_output += f"🗣️ Romanization: <i>{roman_text}</i>\n"
        
    if definition:
        formatted_output += f"📖 Definition: {definition.group(1).strip()}\n"
        
    if example:
        formatted_output += f"📝 Example: {example.group(1).strip()}\n"
        
    # AI က Structured Output မပေးရင် ၎င်း၏ စာသားကိုပဲ ပြန်ပို့သည်
    if not translation:
        return raw_text, ""

    return formatted_output, thai_text_for_tts


# /start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🙏 <b>မင်္ဂလာပါ! (Sawadee Krub/Ka)</b>\n\n"
        "ကျွန်တော်က ထိုင်း-မြန်မာ အပြန်အလှန် ဘာသာပြန် Bot ပါ။\n"
        "အခမဲ့ AI နည်းပညာကို သုံးထားပါတယ်။\n\n"
        "👉 <b>အသုံးပြုနည်း:</b>\n"
        "1. ထိုင်း/မြန်မာ စာသား ရိုက်ပို့ပါ။\n"
        "2. 🎤 <b>အသံဖိုင် (Voice Msg)</b> ပို့ပြီးလည်း မေးနိုင်ပါသည်။\n"
        "3. Admin များသည် /admin ဖြင့် ထိန်းချုပ်နိုင်ပါသည်။\n\n"
        "---"
        "✨ <b>Developed by @MyanmarTecharea</b>"
    )
    await update.message.reply_text(welcome_text, parse_mode=constants.ParseMode.HTML)


# Core function to handle request logic with Retries and User Notification
async def _process_and_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, user_input, is_audio=False):
    MAX_RETRIES = 2
    RETRY_DELAY = 10

    # 1. Initial typing indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)

    for attempt in range(MAX_RETRIES + 1):
        try:
            # OpenRouter ကနေ ဘာသာပြန်ယူတယ်
            raw_response_text = await asyncio.to_thread(get_translation, user_input)

            # OpenRouter က Error ဖြစ်ရင် ပြန်ပို့သော စာသားကို စစ်ဆေးပြီး Error ထုတ်
            if "ขออภัย ระบบมีปัญหาชั่วคราว" in raw_response_text or "Error" in raw_response_text:
                raise Exception(f"API Response Error: {raw_response_text}")

            # 2. စာသားကို Format လုပ်ခြင်း
            formatted_text, thai_text = format_ai_response(raw_response_text)
            
            # Save last query for "Explain More"
            context.user_data['last_sender'] = update.effective_user.id
            context.user_data['last_query'] = user_input

            # 3. Keyboard ကို ဖန်တီးခြင်း
            keyboard_rows = []
            
            # TTS Button ထည့်သွင်းခြင်း (ထိုင်းစာသားပါမှသာ ထည့်မည်)
            if thai_text:
                tts_link = get_thai_tts_link(thai_text)
                keyboard_rows.append([InlineKeyboardButton("🔊 ထိုင်းအသံထွက် နားထောင်မယ်", url=tts_link)])
            
            # Explain More Button (မူလအတိုင်း)
            keyboard_rows.append([InlineKeyboardButton("📝 ရှင်းလင်းချက် ထပ်ကြည့်မယ်", callback_data="explain")])
            
            reply_markup = InlineKeyboardMarkup(keyboard_rows)

            await update.message.reply_text(
                formatted_text,
                reply_markup=reply_markup,
                parse_mode=constants.ParseMode.HTML
            )
            return

        except Exception as e:
            error_message = str(e)
            
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
            else:
                final_error_msg = "⚠️ ယာယီချို့ယွင်းချက်ရှိနေပါသည်။ ခဏနောက် ထပ်ကြိုးစားကြည့်ပါ။"
                
                # Admin များအတွက် Debugging
                if update.effective_user.id in ADMIN_IDS:
                    final_error_msg += f"\n\n**[DEBUG]** Final API Error: <code>{error_message[:400]}...</code>"
                
                await update.message.reply_text(final_error_msg, parse_mode=constants.ParseMode.HTML)


# Text message handler (No changes needed)
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_bot_active() and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔️ Bot ကို ပြုပြင်နေပါသည်။ ခဏစောင့်ပါ။")
        return

    user_text = update.message.text.strip()
    if len(user_text) == 0:
        return

    await _process_and_reply(update, context, user_text, is_audio=False)


# Voice message handler (No changes needed, as TTS is still unsupported by OpenRouter)
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_bot_active() and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔️ Bot ကို ပြုပြင်နေပါသည်။ ခဏစောင့်ပါ။")
        return

    voice_file = update.message.voice
    if not voice_file:
        await update.message.reply_text("အသံဖိုင်မတွေ့ပါ။")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.UPLOAD_PHOTO)
    status_message = await update.message.reply_text("🎤 **အသံကို စာသားအဖြစ် ပြောင်းလဲပြီး ဘာသာပြန်နေပါသည်...**") 

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            ogg_path = os.path.join(tmp_dir, "voice.ogg")
            mp3_path = os.path.join(tmp_dir, "voice.mp3")

            await voice_file.download_to_drive(ogg_path)

            if convert_ogg_to_mp3(ogg_path, mp3_path):
                # Conversion အောင်မြင်သော်လည်း OpenRouter က Transcription ကို တိုက်ရိုက်မပံ့ပိုးပါ။
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=status_message.message_id,
                    text="⚠️ **အသံကို စာသားအဖြစ် ပြောင်းလဲခြင်း မအောင်မြင်ပါ။** ဤ API သည် Audio Transcription ကို တိုက်ရိုက်မပံ့ပိုးပါ။ စာသားရိုက်ပြီး ပို့ပေးပါ။"
                )
            else:
                # Conversion မအောင်မြင်ပါက (ffmpeg error)
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=status_message.message_id,
                    text="❌ **အသံဖိုင်ပြောင်းလဲရာတွင် ချို့ယွင်းချက်ရှိနေပါသည်။** (Server တွင် `ffmpeg` ထည့်သွင်းမှု ပြဿနာရှိနိုင်သည်)"
                )

    except Exception as e:
        await update.message.reply_text(f"အသံဖိုင်ကိုင်တွယ်ရာတွင် ပြဿနာရှိနေပါသည်။ {str(e)}")


# Callback Handler for "Explain More" (No changes needed)
async def user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if query.data.startswith("admin_"):
        return

    await query.answer()

    if query.data == "explain":
        last_text = context.user_data.get('last_query')
        last_sender = context.user_data.get('last_sender')

        if last_sender != query.from_user.id:
            await query.message.reply_text("သင့်ရဲ့ မေးခွန်းဟောင်းမဟုတ်ပါ။")
            return

        if last_text:
            await query.message.reply_text("⏳ အသေးစိတ်ရှင်းပြခဲ့ပါသည်...")
            explanation = await asyncio.to_thread(get_explanation, last_text)
            await query.message.reply_text(f"📖 <b>ရှင်းလင်းချက်:</b>\n\n{explanation}", parse_mode=constants.ParseMode.HTML)
        else:
            await query.message.reply_text("အရင်မေးခွန်း မတွေ့ပါ။")
