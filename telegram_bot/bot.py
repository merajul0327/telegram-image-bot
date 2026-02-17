import logging
import io
import os
import sys
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from PIL import Image

# Add parent directory to path to find image_processor
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import shared logic
import image_processor

# ================= CONFIGURATION =================
# Token provided by user
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("Error: BOT_TOKEN not found in environment variables.")
    # For local testing, you might want to uncomment this, but NEVER commit it:
    # BOT_TOKEN = "8530977543:AAGUY_0yNCvpq4Ep4lIJnIkm7Ss0JowrHb0"
 

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ================= HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 **Passport Bot V3 Ultimate**\n\n"
        "Choose a tool or use commands:\n"
        "🆔 /passport - Passport Photo\n"
        "✂️ /removebg - Remove Background\n"
        "🎨 /background - Custom Background\n"
        "💧 /blur - Portrait Mode\n"
        "📉 /compress - Custom File Compressor\n"
        "🔄 /convert - Format Converter\n"
        "📄 /pdf - PDF Tools\n"
        "📱 /qr - QR Generator\n"
        "⚙️ /settings - HD Mode Toggle",
        parse_mode='Markdown'
    )

async def handle_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sets mode based on command."""
    cmd = update.message.text.split()[0][1:] # remove /
    context.user_data['mode'] = cmd
    
    msgs = {
        'passport': "📸 Send a photo for Passport creation.",
        'removebg': "📸 Send a photo to remove background.",
        'blur': "📸 Send a photo for Portrait Blur.",
        'compress': "📸 Send a photo you want to compress.",
        'pdf': "📄 Send an Image to convert to PDF, or a PDF to get an Image.",
        'qr': "✍️ Send text to generate a QR Code.",
        'convert': "📸 Send a photo to convert (JPG/PNG).",
        'background': "📸 Send a photo first, then I'll ask for the color.",
    }
    
    if cmd == 'settings':
        hd = context.user_data.get('hd_mode', False)
        new_hd = not hd
        context.user_data['hd_mode'] = new_hd
        status = "High Definition (HD)" if new_hd else "Compressed (<140KB)"
        await update.message.reply_text(f"⚙️ **Settings Updated**\nQuality Mode: **{status}**", parse_mode='Markdown')
        return

    msg = msgs.get(cmd, "Send a photo/file to start.")
    await update.message.reply_text(msg)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles text input (QR or Compression Size)."""
    mode = context.user_data.get('mode', '')
    text = update.message.text
    
    if mode == 'qr':
        await update.message.reply_text("⚙️ Generating QR Code...")
        out, fname = await image_processor.process_qr(text)
        await update.message.reply_document(document=out, filename=fname)
        
    elif mode == 'compress_wait_size':
        # User sent size (e.g. "50kb")
        target_kb = image_processor.parse_size(text)
        if not target_kb or target_kb <= 0:
            await update.message.reply_text("❌ Invalid format. Please use '50kb' or '1mb'.")
            return
            
        # Get cached image
        img_bytes = context.user_data.get('compress_image_bytes')
        if not img_bytes:
            await update.message.reply_text("❌ Session expired. Please send the photo again.")
            return
            
        await update.message.reply_text(f"📉 Compressing to under {target_kb}KB...")
        img = Image.open(io.BytesIO(img_bytes))
        out, quality = image_processor.compress_image_to_target(img, target_kb)
        final_size = out.getbuffer().nbytes / 1024
        
        await context.bot.send_document(
            chat_id=update.effective_chat.id, 
            document=out, 
            filename="compressed.jpg",
            caption=f"✅ Done! Size: {final_size:.1f}KB (Quality: {quality})"
        )
        context.user_data['mode'] = 'compress' # Reset to start of compress flow
        
    else:
        await update.message.reply_text("Please use a command like /qr or /compress to start.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Routes photo to processor based on mode."""
    mode = context.user_data.get('mode', 'passport') # Default to passport
    hd = context.user_data.get('hd_mode', False)
    
    file_id = update.message.photo[-1].file_id
    
    if mode == 'compress':
        # Special flow for compressor
        status_msg = await update.message.reply_text("📥 Received! Now tell me the size (e.g., '100kb', '2mb'):")
        new_file = await context.bot.get_file(file_id)
        input_buffer = io.BytesIO()
        await new_file.download_to_memory(out=input_buffer)
        context.user_data['compress_image_bytes'] = input_buffer.getvalue()
        context.user_data['mode'] = 'compress_wait_size'
        return

    await process_file(file_id, mode, hd, update, context)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles PDFs and HEIC files."""
    doc = update.message.document
    fname = doc.file_name.lower()
    mode = context.user_data.get('mode', '')
    
    if 'pdf' in fname:
        # PDF Processing
        if mode == 'pdf':
            await update.message.reply_text("⚙️ Extracting image from PDF...")
            f = await doc.get_file()
            byte_arr = io.BytesIO()
            await f.download_to_memory(out=byte_arr)
            out, name = await image_processor.process_pdf_to_image(byte_arr.getvalue())
            await update.message.reply_document(document=out, filename=name)
        else:
             await update.message.reply_text("Use /pdf mode to handle PDFs.")
             
    elif 'heic' in fname or 'heif' in fname:
        # HEIC Conversion
        await update.message.reply_text("⚙️ Converting HEIC...")
        await process_file(doc.file_id, 'convert', False, update, context)
        
    else:
        # Treat as photo if possible
        await process_file(doc.file_id, mode, False, update, context)

async def process_file(file_id, mode, hd, update, context):
    try:
        status_msg = await update.message.reply_text(f"⏳ Processing ({mode})...")
        
        new_file = await context.bot.get_file(file_id)
        input_buffer = io.BytesIO()
        await new_file.download_to_memory(out=input_buffer)
        input_bytes = input_buffer.getvalue()
        
        # Open Image
        try:
            img = Image.open(io.BytesIO(input_bytes))
        except:
             # Maybe raw bytes for PDF?
             pass

        out_data = None
        fname = "result.jpg"
        
        if mode == 'passport':
            out_data, fname = await image_processor.process_passport(img, hd)
        elif mode == 'removebg':
            out_data, fname = await image_processor.process_remove_bg(img)
        elif mode == 'blur':
            out_data, fname = await image_processor.process_blur(img)
        elif mode == 'pdf':
            out_data, fname = await image_processor.process_pdf_create(img)
        elif mode == 'convert':
            out = io.BytesIO()
            img.convert("RGB").save(out, format='JPEG', quality=95)
            out.seek(0)
            out_data, fname = out, "converted.jpg"
        elif mode == 'background':
            # Ask for color inline
            keyboard = [
                [InlineKeyboardButton("Blue", callback_data='bg_blue'), InlineKeyboardButton("White", callback_data='bg_white')],
                [InlineKeyboardButton("Red", callback_data='bg_red'), InlineKeyboardButton("Grey", callback_data='bg_grey')]
            ]
            context.user_data['image_bytes'] = input_bytes # Cache waiting for click
            await status_msg.edit_text("🎨 Choose a background color:", reply_markup=InlineKeyboardMarkup(keyboard))
            return 
            
        if out_data:
            await context.bot.send_document(chat_id=update.effective_chat.id, document=out_data, filename=fname, caption="✅ Done!")
            await status_msg.delete()
            
    except Exception as e:
        logging.error(e)
        import traceback
        logging.error(traceback.format_exc())
        await update.message.reply_text("❌ Error processing file.")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data.startswith('bg_'):
        color = data.split('_')[1]
        input_bytes = context.user_data.get('image_bytes')
        if not input_bytes:
             await query.edit_message_text("❌ Session expired. Send photo again.")
             return
             
        await query.edit_message_text(f"⏳ Applying {color} background...")
        img = Image.open(io.BytesIO(input_bytes))
        out, fname = await image_processor.process_background(img, color)
        await context.bot.send_document(chat_id=update.effective_chat.id, document=out, filename=fname)

if __name__ == '__main__':
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # commands
    for cmd in ['start', 'help', 'passport', 'removebg', 'blur', 'compress', 'pdf', 'qr', 'convert', 'background', 'settings']:
        application.add_handler(CommandHandler(cmd, getattr(sys.modules[__name__], cmd) if cmd in ['start'] else handle_commands))

    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(CallbackQueryHandler(button_click))
    
    print("Passport Bot V4.1 (Running from /telegram_bot) is running...")
    application.run_polling()
