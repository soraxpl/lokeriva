import time
import re
import threading
from functools import wraps
from flask import request, jsonify, make_response


class SimpleRateLimiter:
    """
    Rate limiter in-memory berbasis sliding window dengan proteksi memory exhaustion.
    Ramah resource, aman untuk serverless/Vercel dan lingkungan multi-threaded.
    """
    def __init__(self, max_tracked_ips=5000):
        self.requests = {}
        self.max_tracked_ips = max_tracked_ips
        self.lock = threading.Lock()

    def get_client_ip(self):
        # Mendeteksi IP asli di belakang reverse proxy Vercel / Cloudflare
        raw_ip = ""
        if request.headers.get("CF-Connecting-IP"):
            raw_ip = request.headers.get("CF-Connecting-IP").strip()
        elif request.headers.get("True-Client-IP"):
            raw_ip = request.headers.get("True-Client-IP").strip()
        elif request.headers.get("X-Forwarded-For"):
            raw_ip = request.headers.get("X-Forwarded-For").split(",")[0].strip()
        elif request.headers.get("X-Real-IP"):
            raw_ip = request.headers.get("X-Real-IP").strip()
        else:
            raw_ip = request.remote_addr or "127.0.0.1"

        # Sanitasi format IP (Hanya izinkan karakter hex, digit, titik, dan titik dua)
        sanitized_ip = re.sub(r"[^0-9a-fA-F:.]", "", raw_ip)[:45]
        return sanitized_ip or "127.0.0.1"

    def is_allowed(self, key, limit, period):
        now = time.time()
        with self.lock:
            # Proteksi Memory Exhaustion: Bersihkan entri lama jika melampaui batas
            if len(self.requests) > self.max_tracked_ips:
                self.requests = {
                    k: [t for t in v if now - t < 120]
                    for k, v in list(self.requests.items())[-2500:]
                }

            timestamps = self.requests.get(key, [])
            valid_timestamps = [t for t in timestamps if now - t < period]

            if len(valid_timestamps) >= limit:
                self.requests[key] = valid_timestamps
                return False, int(period - (now - valid_timestamps[0]))

            valid_timestamps.append(now)
            self.requests[key] = valid_timestamps
            return True, 0


limiter = SimpleRateLimiter()


def rate_limit(limit=120, per=60):
    """
    Decorator rate limit yang fleksibel dan bersahabat (tidak terlalu ketat).
    Default: 120 permintaan per 60 detik (2 req/detik).
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            client_ip = limiter.get_client_ip()
            key = f"{client_ip}:{request.endpoint}"
            allowed, retry_after = limiter.is_allowed(key, limit, per)

            if not allowed:
                # Respon JSON jika request API
                if request.path.startswith("/api/") or "application/json" in request.headers.get("Accept", ""):
                    resp = make_response(jsonify({
                        "status": "error",
                        "code": 429,
                        "message": f"Terlalu banyak permintaan. Silakan coba kembali dalam {retry_after} detik.",
                        "retry_after_seconds": retry_after
                    }), 429)
                    resp.headers["Retry-After"] = str(retry_after)
                    return resp

                # Respon HTML ramah pengguna
                html_msg = f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>429 - Terlalu Banyak Permintaan</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; text-align: center; padding: 60px 20px; background: #f8fafc; color: #1e293b; }}
        .box {{ background: white; max-width: 480px; margin: 0 auto; padding: 32px; border-radius: 12px; box-shadow: 0 4px 16px rgba(0,0,0,0.06); border: 1px solid #e2e8f0; }}
        h2 {{ color: #dc2626; margin-top: 0; }}
        p {{ line-height: 1.6; color: #64748b; font-size: 0.95rem; }}
        .btn {{ display: inline-block; margin-top: 20px; padding: 10px 24px; background: #2563eb; color: white; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 0.9rem; }}
    </style>
</head>
<body>
    <div class="box">
        <h2>Batas Permintaan Tercapai (429)</h2>
        <p>Anda telah mencapai batas wajar permintaan. Demi menjaga performa dan keadilan akses, silakan tunggu sekitar <b>{retry_after} detik</b> sebelum memuat ulang.</p>
        <a href="javascript:location.reload()" class="btn">Muat Ulang Halaman</a>
    </div>
</body>
</html>"""
                resp = make_response(html_msg, 429)
                resp.headers["Retry-After"] = str(retry_after)
                return resp

            return f(*args, **kwargs)
        return wrapped
    return decorator
