import sys
import os
import requests
from dotenv import load_dotenv

sys.path.append(os.getcwd())
load_dotenv()

# 1. Signup/Login to get token
API_URL = "http://127.0.0.1:8000"

res = requests.post(f"{API_URL}/api/signup", json={"username": "testuser_upload", "password": "password123"})
# Ignore if already exists

res = requests.post(f"{API_URL}/api/login", json={"username": "testuser_upload", "password": "password123"})
if res.status_code != 200:
    print("Login failed")
    sys.exit(1)
    
token = res.json()["access_token"]

# 2. Create a dummy PDF
with open("dummy.pdf", "wb") as f:
    f.write(b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/Resources <<\n/Font <<\n/F1 4 0 R\n>>\n>>\n/MediaBox [0 0 612 792]\n/Contents 5 0 R\n>>\nendobj\n4 0 obj\n<<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica\n>>\nendobj\n5 0 obj\n<<\n/Length 44\n>>\nstream\nBT\n/F1 24 Tf\n100 700 Td\n(Hello World) Tj\nET\nendstream\nendobj\nxref\n0 6\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n0000000219 00000 n\n0000000307 00000 n\ntrailer\n<<\n/Size 6\n/Root 1 0 R\n>>\nstartxref\n398\n%%EOF\n")

# 3. Upload
headers = {"Authorization": f"Bearer {token}"}
with open("dummy.pdf", "rb") as f:
    files = {"file": ("dummy.pdf", f, "application/pdf")}
    res = requests.post(f"{API_URL}/api/upload-resume", params={"session_id": "test_session"}, files=files, headers=headers)
    print(res.status_code)
    print(res.text)
