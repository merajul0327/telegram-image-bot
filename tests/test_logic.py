import asyncio
import io
from PIL import Image, ImageDraw
import sys
import os

# Add project path to import image_processor
sys.path.append(os.path.abspath("d:/Project"))

try:
    from image_processor import (
        process_passport, 
        process_remove_bg, 
        process_qr, 
        process_pdf_create, 
        process_pdf_to_image,
        compress_image_to_target,
        process_blur,
        process_background
    )
    print("[OK] Successfully imported image_processor functions.")
except ImportError as e:
    print(f"[FAIL] Failed to import functions: {e}")
    sys.exit(1)

async def run_tests():
    print("\n--- Starting Shared Logic Tests ---\n")
    
    # 1. Create Dummy Image (Red Circle on White)
    img = Image.new('RGB', (1000, 1000), color='white')
    d = ImageDraw.Draw(img)
    d.ellipse((150, 150, 850, 850), fill='red', outline='black')
    print("[OK] Generated dummy test image.")

    # 2. Test Passport Photo
    try:
        out, name = await process_passport(img, hd_mode=False)
        print(f"[OK] Passport Photo Generated: {name} ({out.getbuffer().nbytes / 1024:.2f} KB)")
    except Exception as e:
        print(f"[FAIL] Passport Photo Failed: {e}")

    # 3. Test QR Code
    try:
        out, name = await process_qr("Hello World")
        print(f"[OK] QR Code Generated: {name} ({out.getbuffer().nbytes / 1024:.2f} KB)")
    except Exception as e:
        print(f"[FAIL] QR Code Failed: {e}")

    # 4. Test PDF Creation
    try:
        out, name = await process_pdf_create(img)
        pdf_bytes = out.getvalue()
        print(f"[OK] PDF Created: {name} ({len(pdf_bytes) / 1024:.2f} KB)")
        
        # 5. Test PDF to Image
        # Note: PyMuPDF might need the file saved or bytes stream, checking logic implementation
        out_img, name_img = await process_pdf_to_image(pdf_bytes)
        print(f"[OK] PDF -> Image Converted: {name_img}")
        
    except Exception as e:
        print(f"[FAIL] PDF Tools Failed: {e}")

    # 6. Test Custom Compressor
    try:
        target = 50 # 50 KB
        out, quality = compress_image_to_target(img, target)
        size = out.getbuffer().nbytes / 1024
        print(f"[OK] Compression Target {target}KB -> Result: {size:.2f} KB (Q={quality})")
    except Exception as e:
        print(f"[FAIL] Compressor Failed: {e}")

    # 7. Test Background Change
    try:
        out, name = await process_background(img, 'blue')
        print(f"[OK] Background Changed: {name}")
    except Exception as e:
        print(f"[FAIL] Background Tool Failed: {e}")

    print("\n--- Shared Logic Tests Completed ---")

if __name__ == "__main__":
    asyncio.run(run_tests())
