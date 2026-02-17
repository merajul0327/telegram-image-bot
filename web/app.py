from flask import Flask, render_template, request, send_file, flash, redirect, url_for
import os
import io
import sys
from PIL import Image

# Add parent directory to path to find image_processor
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# import image_processor # Lazy imported inside functions to save memory in Gunicorn

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Ensure upload directory exists (though we process mainly in memory)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    import image_processor # Lazy import to prevent OOM on Render Free Tier
    if 'file' not in request.files:
        flash('No file part')
        return redirect(url_for('index'))
    
    file = request.files['file']
    tool = request.form.get('tool')
    
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('index'))

    # Special case for QR (Text input)
    if tool == 'qr':
        text = request.form.get('qr_text')
        # Assuming process_qr is async, in web sync context context we might need to handle it.
        # But wait, image_processor.py functions are async def? 
        # Yes they are. Flask standard is Sync. We should run async function.
        import asyncio
        out, fname = asyncio.run(image_processor.process_qr(text))
        return send_file(out, as_attachment=True, download_name=fname, mimetype='image/png')

    if file:
        img_bytes = file.read()
        try:
            img = Image.open(io.BytesIO(img_bytes))
        except:
             # PDF raw bytes
             pass
        
        import asyncio
        out = None
        fname = "result.jpg"
        mimetype = "image/jpeg"

        if tool == 'passport':
            out, fname = asyncio.run(image_processor.process_passport(img))
        elif tool == 'removebg':
            out, fname = asyncio.run(image_processor.process_remove_bg(img))
            mimetype = "image/png"
        elif tool == 'blur':
            out, fname = asyncio.run(image_processor.process_blur(img))
        elif tool == 'pdf':
            out, fname = asyncio.run(image_processor.process_pdf_create(img))
            mimetype = "application/pdf"
        elif tool == 'convert':
            out = io.BytesIO()
            img.convert("RGB").save(out, format='JPEG')
            out.seek(0)
            fname = "converted.jpg"
        
        if out:
             return send_file(out, as_attachment=True, download_name=fname, mimetype=mimetype)
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
