import io
import os
# CRITICAL: Disable Numba JIT to prevent OOM on Render Free Tier (512MB)
os.environ['NUMBA_DISABLE_JIT'] = '1'

import io
import sys
import re
import cv2
import numpy as np
from rembg import remove, new_session

# Global session for lightweight model
# u2netp is ~4MB vs u2net ~170MB
REMBG_SESSION = new_session("u2netp")
from PIL import Image, ImageOps, ImageEnhance, ImageFilter, ImageDraw
import qrcode
import fitz  # PyMuPDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import pillow_heif

# Register HEIC opener
pillow_heif.register_heif_opener()

# Target Dimensions for Passport Photo (Standard 35x45mm at 300 DPI)
TARGET_SIZE = (413, 531)

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    print("WARNING: OpenCV (cv2) not found. Face detection will be disabled.")

def compress_image_to_target(pil_img, target_kb, step=5):
    """Compresses image to be under target_kb."""
    quality = 95
    img_byte_arr = io.BytesIO()
    
    # First pass: resize if huge
    if pil_img.width > 2000 or pil_img.height > 2000:
        pil_img.thumbnail((2000, 2000))

    while quality > 5:
        img_byte_arr = io.BytesIO()
        pil_img.convert("RGB").save(img_byte_arr, format='JPEG', quality=quality)
        size_kb = img_byte_arr.tell() / 1024
        
        if size_kb <= target_kb:
            img_byte_arr.seek(0)
            return img_byte_arr, quality
        
        quality -= step
    
    # If still too big, return at lowest quality
    img_byte_arr.seek(0)
    return img_byte_arr, quality

def opencv_face_crop(pil_img):
    """Smart face cropping."""
    if not OPENCV_AVAILABLE:
        return pil_img

    img_cv = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    face_cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(face_cascade_path)
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    
    if len(faces) == 0:
        return pil_img

    x, y, w, h = max(faces, key=lambda item: item[2] * item[3])
    img_h, img_w = img_cv.shape[:2]
    
    center_x = x + w // 2
    center_y = y + h // 2
    crop_h = int(h * 2.5)
    crop_w = int(crop_h * (35/45))
    
    x1 = max(0, center_x - crop_w // 2)
    y1 = max(0, center_y - crop_h // 2)
    x2 = min(img_w, x1 + crop_w)
    y2 = min(img_h, y1 + crop_h)
    
    if y1 == 0: y2 = min(img_h, crop_h)
    
    return pil_img.crop((x1, y1, x2, y2))

async def process_passport(img, hd_mode=False):
    """Passport Photo Logic"""
    img = img.convert("RGBA")
    # Use specific session
    no_bg = remove(img, session=REMBG_SESSION)
    white_bg = Image.new("RGBA", no_bg.size, "WHITE")
    white_bg.paste(no_bg, mask=no_bg)
    rgb_img = white_bg.convert("RGB")
    cropped = opencv_face_crop(rgb_img)
    final = ImageOps.fit(cropped, TARGET_SIZE, method=Image.LANCZOS, centering=(0.5, 0.5))
    
    if hd_mode:
        out = io.BytesIO()
        final.save(out, format='JPEG', quality=100)
        out.seek(0)
        return out, "passport_hd.jpg"
    else:
        out, _ = compress_image_to_target(final, 140)
        return out, "passport_compressed.jpg"

async def process_remove_bg(img):
    """Transparent PNG"""
    img = img.convert("RGBA")
    out_img = remove(img, session=REMBG_SESSION)
    out = io.BytesIO()
    out_img.save(out, format='PNG')
    out.seek(0)
    return out, "no_bg.png"

async def process_blur(img):
    """Portrait Mode (Blur Background)"""
    img = img.convert("RGBA")
    # Get mask
    no_bg = remove(img, session=REMBG_SESSION)
    mask = no_bg.split()[3] # Alpha channel
    
    # Blur original
    blurred = img.filter(ImageFilter.GaussianBlur(10))
    
    # Composite
    img.paste(blurred, mask=ImageOps.invert(mask))
    final = img.convert("RGB")
    
    out = io.BytesIO()
    final.save(out, format='JPEG', quality=95)
    out.seek(0)
    return out, "portrait_blur.jpg"

async def process_pdf_create(img):
    """Image to PDF"""
    out = io.BytesIO()
    img.save(out, format='PDF')
    out.seek(0)
    return out, "doc.pdf"

async def process_pdf_to_image(file_bytes):
    """PDF First Page to Image"""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    page = doc.load_page(0)
    pix = page.get_pixmap()
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    out = io.BytesIO()
    img.save(out, format='JPEG')
    out.seek(0)
    return out, "page_1.jpg"

async def process_qr(text):
    """Text to QR"""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    out = io.BytesIO()
    img.save(out, format='PNG')
    out.seek(0)
    return out, "qrcode.png"

async def process_background(img, color_name):
    """Custom Background"""
    color_map = {
        'blue': (0, 0, 255),
        'white': (255, 255, 255),
        'red': (255, 0, 0),
        'grey': (128, 128, 128)
    }
    color = color_map.get(color_name.lower(), (255, 255, 255))
    
    img = img.convert("RGBA")
    no_bg = remove(img)
    bg = Image.new("RGBA", no_bg.size, color)
    bg.paste(no_bg, mask=no_bg)
    final = bg.convert("RGB")
    
    out = io.BytesIO()
    final.save(out, format='JPEG')
    out.seek(0)
    return out, f"bg_{color_name}.jpg"

def parse_size(size_str):
    """Parses '50kb', '2mb' into kilobytes."""
    size_str = size_str.lower().strip()
    match = re.match(r"(\d+(?:\.\d+)?)\s*(kb|mb)", size_str)
    if not match:
        return None
    val = float(match.group(1))
    unit = match.group(2)
    if unit == 'mb':
        return val * 1024
    return val
