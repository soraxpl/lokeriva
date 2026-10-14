import sys
import os
import traceback

# Menambahkan root project ke sys.path agar modul utama dapat diimpor oleh Vercel
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from app import app
except Exception:
    err_tb = traceback.format_exc()
    print("FATAL ERROR STARTING APP:", err_tb)
    from flask import Flask, Response
    app = Flask(__name__)
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def catch_all(path):
        return Response(
            f"<h3>Lokeriva Serverless Startup Error</h3><pre style='color:#dc2626;background:#fef2f2;padding:16px;border-radius:8px;'>{err_tb}</pre>",
            status=500,
            mimetype="text/html"
        )
