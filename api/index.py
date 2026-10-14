import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
for p in [current_dir, parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from app import app

# Top-level WSGI / ASGI entry point untuk Vercel Python Runtime
app = app
application = app
handler = app
