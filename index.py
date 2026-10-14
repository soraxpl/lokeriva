import sys
import os

root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app import app

# Top-level WSGI / ASGI entry point untuk Vercel Python Runtime
app = app
application = app
handler = app
