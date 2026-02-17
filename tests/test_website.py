import unittest
import io
import os
import sys
from PIL import Image

# Add project path to import app
sys.path.append(os.path.abspath("d:/Project"))
sys.path.append(os.path.abspath("d:/Project/web"))

try:
    from app import app
    print("[OK] Successfully imported Flask app.")
except ImportError as e:
    print(f"[FAIL] Failed to import app: {e}")
    sys.exit(1)

class TestFlaskWebsite(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def create_dummy_image(self):
        """Helper to create a dummy image bytes"""
        img = Image.new('RGB', (100, 100), color='white')
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG')
        img_byte_arr.seek(0)
        return img_byte_arr

    def test_homepage(self):
        """Test if homepage loads"""
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Passport AI', response.data)
        print("[OK] Homepage load test passed.")

    def test_upload_passport(self):
        """Test passport photo processing endpoint"""
        img_bytes = self.create_dummy_image()
        data = {
            'file': (img_bytes, 'test.jpg'),
            'tool': 'passport'
        }
        response = self.app.post('/process', data=data, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'image/jpeg')
        print("[OK] Passport upload test passed.")

    def test_upload_removebg(self):
        """Test remove background processing endpoint"""
        img_bytes = self.create_dummy_image()
        data = {
            'file': (img_bytes, 'test.jpg'),
            'tool': 'removebg'
        }
        response = self.app.post('/process', data=data, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'image/png')
        print("[OK] RemoveBG upload test passed.")

if __name__ == '__main__':
    unittest.main()
