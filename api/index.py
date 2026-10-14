import sys
import os

# Menambahkan root project ke sys.path agar modul utama dapat diimpor oleh Vercel
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from app import app

# Top-level WSGI / ASGI entry point untuk Vercel Python Runtime
app = app
application = app
handler = app
