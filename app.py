import io
import csv
import html
import math
import re
import secrets
import json
import urllib.parse
import urllib.request
from datetime import datetime

try:
    import requests
except ImportError:
    requests = None

from flask import Flask, render_template, request, jsonify, make_response, send_file
from scraper import cache_manager, sanitasi_link
from pdf_generator import generate_jobs_pdf
from rate_limiter import rate_limit

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False

# Random Build Hash untuk Service Worker cache versioning (dibuat otomatis per startup/redeploy)
SW_BUILD_HASH = secrets.token_hex(4)

# ==============================================================================
# SECURITY HEADERS & CORS MIDDLEWARE
# ==============================================================================
@app.after_request
def add_security_headers(response):
    # Proteksi XSS, Clickjacking, Sniffing, dan Content-Security-Policy
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(self)"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
        "img-src 'self' data: https:; "
        "manifest-src 'self'; "
        "connect-src 'self' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none';"
    )
    # Izinkan CORS untuk API publik
    if request.path.startswith("/api/"):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"

    return response


def sanitize_query(text):
    """
    Sanitasi ketat input string pengguna:
    Menghilangkan karakter berbahaya (SQL/XSS/Command injection/Control chars).
    """
    if not text or not isinstance(text, str):
        return ""
    # Batasi panjang maksimal 80 karakter
    text = text[:80]
    # Hapus karakter kontrol dan karakter rentan injeksi: < > " ' ` ; ( ) \ { } |
    text = re.sub(r"[\x00-\x1f\x7f<>\"'`;()\\{}|]", "", text)
    return text.strip()


def clean_csv_cell(val):
    """
    Mencegah CSV / Spreadsheet Formula Injection (CWE-1236).
    Jika sel diawali simbol formula (=, +, -, @, \t, \r), tambahkan tanda kutip satu di depannya.
    """
    if val is None:
        return ""
    text = str(val).strip()
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{text}"
    return text


@app.context_processor
def inject_site_meta():
    """Injeksi metadata domain resmi https://lokeriva.vercel.app untuk SEO & Canonical."""
    host = request.host.lower() if request.host else ""
    if "localhost" in host or "127.0.0.1" in host:
        site_root = request.url_root.rstrip("/")
    else:
        site_root = "https://lokeriva.vercel.app"

    return {
        "site_url": site_root,
        "canonical_url": f"{site_root}{request.path}"
    }


# ==============================================================================
# PWA & WEB UI ROUTES
# ==============================================================================
@app.route("/manifest.json")
def manifest():
    """Menyajikan PWA Web App Manifest."""
    return send_file("static/manifest.json", mimetype="application/manifest+json")


@app.route("/sw.js")
def service_worker():
    """Menyajikan Service Worker dengan random cache version otomatis per deployment/startup."""
    try:
        with open("static/sw.js", "r", encoding="utf-8") as f:
            content = f.read()
        # Injeksi random hash ke dalam script Service Worker
        content = content.replace("{{SW_BUILD_HASH}}", SW_BUILD_HASH)
        resp = make_response(content)
        resp.headers["Content-Type"] = "application/javascript"
        resp.headers["Service-Worker-Allowed"] = "/"
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return resp
    except Exception:
        return send_file("static/sw.js", mimetype="application/javascript")


@app.route("/robots.txt")
def robots_txt():
    """Menyajikan robots.txt untuk crawler mesin pencari (Googlebot, Bingbot, dll)."""
    return send_file("static/robots.txt", mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    """Menghasilkan XML Sitemap resmi untuk indexing mesin pencari."""
    host = request.host.lower() if request.host else ""
    if "localhost" in host or "127.0.0.1" in host:
        base_url = request.url_root.rstrip("/")
    else:
        base_url = "https://lokeriva.vercel.app"
    now_str = datetime.now().strftime("%Y-%m-%d")
    sitemap_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>{base_url}/</loc>
        <lastmod>{now_str}</lastmod>
        <changefreq>hourly</changefreq>
        <priority>1.0</priority>
    </url>
    <url>
        <loc>{base_url}/docs</loc>
        <lastmod>{now_str}</lastmod>
        <changefreq>daily</changefreq>
        <priority>0.8</priority>
    </url>
    <url>
        <loc>{base_url}/api/openapi.json</loc>
        <lastmod>{now_str}</lastmod>
        <changefreq>weekly</changefreq>
        <priority>0.5</priority>
    </url>
</urlset>"""
    resp = make_response(sitemap_content)
    resp.headers["Content-Type"] = "application/xml; charset=utf-8"
    return resp


@app.route("/")
@rate_limit(limit=150, per=60)
def index():
    """Halaman antarmuka portal loker web utama."""
    return render_template("index.html")


@app.route("/docs")
@rate_limit(limit=150, per=60)
def documentation():
    """Halaman dokumentasi API interaktif."""
    return render_template("docs.html")


# ==============================================================================
# REST API ENDPOINTS
# ==============================================================================
@app.route("/api/jobs", methods=["GET", "POST"])
@rate_limit(limit=120, per=60)
def get_jobs():
    """
    Endpoint utama pencarian dan filtering lowongan kerja.
    Mendukung GET (Query Params) dan POST (JSON Request Body).
    """
    body = {}
    if request.is_json:
        try:
            body = request.get_json(silent=True) or {}
        except Exception:
            body = {}

    query = sanitize_query(request.args.get("q", body.get("q", body.get("query", ""))))
    source = sanitize_query(request.args.get("source", body.get("source", "")))
    category = sanitize_query(request.args.get("category", body.get("category", body.get("kategori", ""))))
    location = sanitize_query(request.args.get("location", body.get("location", body.get("lokasi", ""))))
    location_type = sanitize_query(request.args.get("location_type", body.get("location_type", "all")))
    sort_by = sanitize_query(request.args.get("sort", body.get("sort", "newest")))

    try:
        raw_page = request.args.get("page", body.get("page", 1))
        raw_limit = request.args.get("limit", body.get("limit", 20))
        page = max(1, int(raw_page))
        limit = min(100, max(1, int(raw_limit)))
    except (ValueError, TypeError):
        page = 1
        limit = 20

    # Whitelist parameter terkontrol
    if sort_by not in ["newest", "title", "company"]:
        sort_by = "newest"
    if location_type not in ["all", "remote", "onsite"]:
        location_type = "all"

    jobs, updated_at = cache_manager.get_all_jobs()

    # Filter Query Kata Kunci
    if query:
        q_low = query.lower()
        jobs = [
            j for j in jobs
            if q_low in j.get("posisi", "").lower()
            or q_low in j.get("perusahaan", "").lower()
            or q_low in j.get("lokasi", "").lower()
            or q_low in j.get("kategori", "").lower()
        ]

    # Filter Sumber
    if source:
        jobs = [j for j in jobs if source.lower() in j.get("sumber", "").lower()]

    # Filter Kategori
    if category:
        jobs = [j for j in jobs if category.lower() in j.get("kategori", "").lower()]

    # Filter Lokasi (Kota / Daerah)
    if location:
        loc_low = location.lower()
        jobs = [j for j in jobs if loc_low in j.get("lokasi", "").lower() or loc_low in j.get("kategori", "").lower()]

    # Filter Tipe Lokasi (Berdasarkan Lokasi Fisik / Remote Bebas Lokasi)
    if location_type == "remote":
        jobs = [j for j in jobs if any(k in j.get("kategori", "").lower() or k in j.get("lokasi", "").lower() for k in ["remote", "wfh", "anywhere", "worldwide"])]
    elif location_type == "onsite":
        jobs = [j for j in jobs if not any(k in j.get("kategori", "").lower() or k in j.get("lokasi", "").lower() for k in ["remote", "wfh", "anywhere", "worldwide"])]

    # Pengurutan
    if sort_by == "title":
        jobs = sorted(jobs, key=lambda x: x.get("posisi", "").lower())
    elif sort_by == "company":
        jobs = sorted(jobs, key=lambda x: x.get("perusahaan", "").lower())
    else: # newest
        jobs = sorted(jobs, key=lambda x: x.get("tanggal", ""), reverse=True)

    total_results = len(jobs)
    total_pages = math.ceil(total_results / limit) if total_results > 0 else 1
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_jobs = jobs[start_idx:end_idx]

    return jsonify({
        "status": "success",
        "query": query,
        "filters": {
            "source": source,
            "category": category,
            "location": location,
            "location_type": location_type,
            "sort": sort_by
        },
        "pagination": {
            "total_items": total_results,
            "total_pages": total_pages,
            "current_page": page,
            "limit": limit,
            "has_next": page < total_pages,
            "has_prev": page > 1
        },
        "updated_at": datetime.fromtimestamp(updated_at).strftime("%Y-%m-%d %H:%M:%S WIB") if updated_at else "-",
        "data": paginated_jobs
    })


@app.route("/api/sources", methods=["GET"])
@rate_limit(limit=120, per=60)
def get_sources():
    """Mengembalikan daftar semua sumber aktif beserta jumlah loker terkumpul."""
    jobs, updated_at = cache_manager.get_all_jobs()
    counts = {}
    for j in jobs:
        src = j.get("sumber", "Lainnya")
        counts[src] = counts.get(src, 0) + 1

    sources_list = [{"name": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True)]
    return jsonify({
        "status": "success",
        "total_sources": len(sources_list),
        "updated_at": datetime.fromtimestamp(updated_at).strftime("%Y-%m-%d %H:%M:%S WIB") if updated_at else "-",
        "sources": sources_list
    })


@app.route("/api/stats", methods=["GET"])
@rate_limit(limit=120, per=60)
def get_stats():
    """Mengembalikan statistik ringkas agregasi lowongan kerja."""
    jobs, updated_at = cache_manager.get_all_jobs()
    total = len(jobs)

    sources_count = len(set(j.get("sumber") for j in jobs))
    remote_count = sum(1 for j in jobs if "remote" in j.get("kategori", "").lower() or "remote" in j.get("lokasi", "").lower() or "wfh" in j.get("kategori", "").lower())
    indo_count = total - remote_count

    return jsonify({
        "status": "success",
        "stats": {
            "total_jobs": total,
            "active_sources": sources_count,
            "remote_jobs": remote_count,
            "local_indo_jobs": indo_count,
            "last_updated": datetime.fromtimestamp(updated_at).strftime("%Y-%m-%d %H:%M:%S WIB") if updated_at else "-"
        }
    })


@app.route("/api/refresh", methods=["GET", "POST"])
@rate_limit(limit=15, per=60)
def refresh_cache():
    """Memperbarui pool cache lowongan kerja secara manual (Rate limit: 15/menit)."""
    global SW_BUILD_HASH
    SW_BUILD_HASH = secrets.token_hex(4)
    jobs, updated_at = cache_manager.get_all_jobs(force_refresh=True)
    return jsonify({
        "status": "success",
        "message": f"Cache berhasil diperbarui. Total {len(jobs)} lowongan terkumpul.",
        "total_jobs": len(jobs),
        "sw_cache_version": SW_BUILD_HASH,
        "updated_at": datetime.fromtimestamp(updated_at).strftime("%Y-%m-%d %H:%M:%S WIB")
    })


# ==============================================================================
# EXPORT PDF (LINK DAPAT DIKLIK) & CSV
# ==============================================================================
@app.route("/export/pdf", methods=["GET"])
@app.route("/api/export/pdf", methods=["GET"])
@rate_limit(limit=30, per=60)
def export_pdf():
    """
    Menghasilkan file PDF dengan hyperlink yang 100% DAPAT DIKLIK.
    Mendukung filter 'q' dan 'source'.
    """
    query = sanitize_query(request.args.get("q", ""))
    source = sanitize_query(request.args.get("source", ""))
    location = sanitize_query(request.args.get("location", ""))
    location_type = sanitize_query(request.args.get("location_type", "all"))

    jobs, _ = cache_manager.get_all_jobs()
    if query:
        q_low = query.lower()
        jobs = [j for j in jobs if q_low in j.get("posisi", "").lower() or q_low in j.get("perusahaan", "").lower() or q_low in j.get("lokasi", "").lower()]
    if source:
        jobs = [j for j in jobs if source.lower() in j.get("sumber", "").lower()]
    if location:
        loc_low = location.lower()
        jobs = [j for j in jobs if loc_low in j.get("lokasi", "").lower() or loc_low in j.get("kategori", "").lower()]
    if location_type == "remote":
        jobs = [j for j in jobs if any(k in j.get("kategori", "").lower() or k in j.get("lokasi", "").lower() for k in ["remote", "wfh", "anywhere", "worldwide"])]
    elif location_type == "onsite":
        jobs = [j for j in jobs if not any(k in j.get("kategori", "").lower() or k in j.get("lokasi", "").lower() for k in ["remote", "wfh", "anywhere", "worldwide"])]

    pdf_bytes = generate_jobs_pdf(jobs, query=query, source_filter=source)

    filename = f"Lokeriva_Pilihan_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )


@app.route("/export/csv", methods=["GET"])
@app.route("/api/export/csv", methods=["GET"])
@rate_limit(limit=40, per=60)
def export_csv():
    """Ekspor daftar lowongan kerja ke CSV (UTF-8 BOM untuk Excel)."""
    query = sanitize_query(request.args.get("q", ""))
    source = sanitize_query(request.args.get("source", ""))
    location = sanitize_query(request.args.get("location", ""))
    location_type = sanitize_query(request.args.get("location_type", "all"))

    jobs, _ = cache_manager.get_all_jobs()
    if query:
        q_low = query.lower()
        jobs = [j for j in jobs if q_low in j.get("posisi", "").lower() or q_low in j.get("perusahaan", "").lower() or q_low in j.get("lokasi", "").lower()]
    if source:
        jobs = [j for j in jobs if source.lower() in j.get("sumber", "").lower()]
    if location:
        loc_low = location.lower()
        jobs = [j for j in jobs if loc_low in j.get("lokasi", "").lower() or loc_low in j.get("kategori", "").lower()]
    if location_type == "remote":
        jobs = [j for j in jobs if any(k in j.get("kategori", "").lower() or k in j.get("lokasi", "").lower() for k in ["remote", "wfh", "anywhere", "worldwide"])]
    elif location_type == "onsite":
        jobs = [j for j in jobs if not any(k in j.get("kategori", "").lower() or k in j.get("lokasi", "").lower() for k in ["remote", "wfh", "anywhere", "worldwide"])]

    output = io.StringIO()
    # UTF-8 BOM
    output.write("\ufeff")
    writer = csv.DictWriter(output, fieldnames=["sumber", "kategori", "posisi", "perusahaan", "lokasi", "tanggal", "link"], delimiter=";")
    writer.writeheader()
    for j in jobs:
        writer.writerow({
            "sumber": clean_csv_cell(j.get("sumber", "")),
            "kategori": clean_csv_cell(j.get("kategori", "")),
            "posisi": clean_csv_cell(j.get("posisi", "")),
            "perusahaan": clean_csv_cell(j.get("perusahaan", "")),
            "lokasi": clean_csv_cell(j.get("lokasi", "")),
            "tanggal": clean_csv_cell(j.get("tanggal", "")),
            "link": clean_csv_cell(j.get("link", ""))
        })

    mem = io.BytesIO()
    mem.write(output.getvalue().encode("utf-8-sig"))
    mem.seek(0)

    filename = f"Lokeriva_Lengkap_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return send_file(
        mem,
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename
    )


# ==============================================================================
# TELEGRAM BOT WEBHOOK INTEGRATION (@lokeriva_bot)
# ==============================================================================
TELEGRAM_BOT_TOKEN = "8983682440:AAHg3gz-Zap30_e8Qkt9tPmNJM9iH_ka3nQ"


def send_telegram_message(chat_id, text, reply_markup=None):
    """Kirim pesan ke pengguna Telegram via REST Bot API dengan fallback zero-dependency."""
    if not TELEGRAM_BOT_TOKEN:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    
    # 1. Gunakan requests jika tersedia
    if requests is not None:
        try:
            resp = requests.post(url, json=payload, timeout=8)
            return resp.status_code == 200
        except Exception as e:
            print(f"Error sending telegram message (requests): {e}")
            return False

    # 2. Fallback zero-dependency menggunakan standard library urllib.request
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "LokerivaBot/1.0"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"Error sending telegram message (urllib): {e}")
        return False


@app.route("/api/telegram/webhook", methods=["POST"])
def telegram_webhook():
    """Webhook handler untuk bot Telegram @lokeriva_bot."""
    update = request.get_json(silent=True) or {}
    
    chat_id = None
    text = ""
    user_name = "Kawan"

    if "callback_query" in update:
        cb = update["callback_query"]
        chat_id = cb.get("message", {}).get("chat", {}).get("id")
        text = cb.get("data", "").strip()
        user_name = cb.get("from", {}).get("first_name") or cb.get("from", {}).get("username") or "Kawan"
        # Acknowledge callback query to stop loading spinner in Telegram
        try:
            cb_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
            cb_payload = {"callback_query_id": cb.get("id")}
            if requests is not None:
                requests.post(cb_url, json=cb_payload, timeout=4)
            else:
                req = urllib.request.Request(
                    cb_url,
                    data=json.dumps(cb_payload).encode("utf-8"),
                    headers={"Content-Type": "application/json", "User-Agent": "LokerivaBot/1.0"}
                )
                with urllib.request.urlopen(req, timeout=4):
                    pass
        except Exception:
            pass
    elif "message" in update:
        msg = update["message"]
        chat_id = msg.get("chat", {}).get("id")
        text = msg.get("text", "").strip()
        user_name = msg.get("from", {}).get("first_name") or msg.get("from", {}).get("username") or "Kawan"

    if not chat_id or not text:
        return jsonify({"ok": True, "note": "no message/chat_id"})

    clean_text = text.strip()
    cmd = clean_text.lower().split()[0] if clean_text else ""

    # Perintah /start atau /help
    if cmd in ["/start", "/help", "help", "bantuan", "menu"]:
        welcome_text = (
            f"👋 <b>Halo, {html.escape(user_name)}! Selamat datang di Lokeriva Bot</b> 🚀\n\n"
            "Bot resmi dari <b>Lokeriva.vercel.app</b> untuk mencari lowongan kerja teragregasi otomatis dari 20+ portal karir di Indonesia dan platform Remote WFH Global.\n\n"
            "📌 <b>Cara Cepat Menggunakan:</b>\n"
            "• Ketik langsung kata kunci pencarian, contoh:\n"
            "  👉 <code>Jakarta</code>, <code>Makassar</code>, <code>Admin</code>, <code>Python</code>, <code>Akuntansi</code>\n"
            "• /terbaru — 5 lowongan kerja paling baru hari ini\n"
            "• /wfh — Lowongan kerja WFH / Remote\n"
            "• /stats — Statistik agregasi loker & portal aktif\n"
            "• /web — Kunjungi website Lokeriva\n\n"
            "🌐 <i>Akses website lengkap dengan filter lokasi, unduh PDF/CSV, & Generator Surat Lamaran:</i>\n"
            "👉 https://lokeriva.vercel.app"
        )
        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "💼 Lowongan Terbaru", "callback_data": "/terbaru"},
                    {"text": "💻 Remote / WFH", "callback_data": "/wfh"}
                ],
                [
                    {"text": "🌐 Kunjungi Lokeriva.vercel.app", "url": "https://lokeriva.vercel.app"}
                ]
            ]
        }
        send_telegram_message(chat_id, welcome_text, reply_markup=reply_markup)
        return jsonify({"ok": True})

    jobs, updated_at = cache_manager.get_all_jobs()

    # Perintah /terbaru
    if cmd in ["/terbaru", "terbaru", "latest"]:
        sorted_jobs = sorted(jobs, key=lambda x: x.get("tanggal", ""), reverse=True)[:5]
        if not sorted_jobs:
            send_telegram_message(chat_id, "⚠️ Belum ada data lowongan kerja tersedia saat ini.")
            return jsonify({"ok": True})

        lines = ["🔥 <b>5 Lowongan Kerja Terbaru Hari Ini:</b>\n"]
        for i, j in enumerate(sorted_jobs, 1):
            pos = html.escape(j.get("posisi", "Posisi"))
            per = html.escape(j.get("perusahaan", "Perusahaan"))
            lok = html.escape(j.get("lokasi", "Indonesia"))
            sumb = html.escape(j.get("sumber", "Portal"))
            link = j.get("link", "https://lokeriva.vercel.app")
            tgl = html.escape(j.get("tanggal", ""))
            tgl_str = f" • <i>{tgl}</i>" if tgl else ""
            lines.append(
                f"{i}. <b>{pos}</b>\n"
                f"   🏢 {per}\n"
                f"   📍 {lok} | 🏷️ {sumb}{tgl_str}\n"
                f"   🔗 <a href=\"{link}\">Lamar / Detail Loker</a>\n"
            )
        lines.append("🔎 <i>Cari ratusan loker lainnya di: https://lokeriva.vercel.app</i>")

        reply_markup = {
            "inline_keyboard": [
                [{"text": "🚀 Lihat Ratusan Loker di Web", "url": "https://lokeriva.vercel.app"}]
            ]
        }
        send_telegram_message(chat_id, "\n".join(lines), reply_markup=reply_markup)
        return jsonify({"ok": True})

    # Perintah /wfh atau /remote
    if cmd in ["/wfh", "/remote", "wfh", "remote"]:
        remote_jobs = [j for j in jobs if any(k in j.get("kategori", "").lower() or k in j.get("lokasi", "").lower() for k in ["remote", "wfh", "anywhere", "worldwide"])]
        sorted_remote = sorted(remote_jobs, key=lambda x: x.get("tanggal", ""), reverse=True)[:5]
        if not sorted_remote:
            send_telegram_message(chat_id, "⚠️ Saat ini belum ada loker remote tersimpan di cache.")
            return jsonify({"ok": True})

        lines = ["💻 <b>5 Lowongan Kerja WFH / Remote Pilihan:</b>\n"]
        for i, j in enumerate(sorted_remote, 1):
            pos = html.escape(j.get("posisi", "Posisi"))
            per = html.escape(j.get("perusahaan", "Perusahaan"))
            lok = html.escape(j.get("lokasi", "Remote"))
            sumb = html.escape(j.get("sumber", "Portal"))
            link = j.get("link", "https://lokeriva.vercel.app")
            lines.append(
                f"{i}. <b>{pos}</b>\n"
                f"   🏢 {per}\n"
                f"   📍 {lok} | 🏷️ {sumb}\n"
                f"   🔗 <a href=\"{link}\">Lamar / Detail Loker</a>\n"
            )
        lines.append("🌐 <i>Semua lowongan remote: https://lokeriva.vercel.app</i>")

        reply_markup = {
            "inline_keyboard": [
                [{"text": "💻 Buka Semua Loker Remote di Web", "url": "https://lokeriva.vercel.app/?location_type=remote"}]
            ]
        }
        send_telegram_message(chat_id, "\n".join(lines), reply_markup=reply_markup)
        return jsonify({"ok": True})

    # Perintah /stats
    if cmd in ["/stats", "stats", "statistik"]:
        counts = {}
        for j in jobs:
            src = j.get("sumber", "Lainnya")
            counts[src] = counts.get(src, 0) + 1
        top_sources = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:8]
        src_text = "\n".join([f"• <b>{html.escape(k)}</b>: {v} loker" for k, v in top_sources])
        last_up = datetime.fromtimestamp(updated_at).strftime("%d %b %Y %H:%M WIB") if updated_at else "-"
        stats_msg = (
            f"📊 <b>Statistik Portal Lokeriva:</b>\n\n"
            f"💼 Total Lowongan Tersedia: <b>{len(jobs):,}</b> loker\n"
            f"🌐 Total Portal Sumber: <b>{len(counts)}</b> portal\n\n"
            f"<b>Portal Terbanyak:</b>\n{src_text}\n\n"
            f"🕒 Pembaruan Terakhir: {last_up}\n"
            f"🔗 https://lokeriva.vercel.app"
        )
        reply_markup = {
            "inline_keyboard": [
                [{"text": "🌐 Kunjungi Website", "url": "https://lokeriva.vercel.app"}]
            ]
        }
        send_telegram_message(chat_id, stats_msg, reply_markup=reply_markup)
        return jsonify({"ok": True})

    # Perintah /web
    if cmd in ["/web", "web", "website"]:
        send_telegram_message(
            chat_id,
            "🌐 <b>Website Resmi Lokeriva:</b>\n👉 https://lokeriva.vercel.app\n\n"
            "Gunakan fitur pencarian filter kota, tipe pekerjaan, unduh PDF/CSV, dan Generator Surat Lamaran Kerja!"
        )
        return jsonify({"ok": True})

    # Pencarian bebas kata kunci
    q_low = clean_text.lower()
    matches = [
        j for j in jobs
        if q_low in j.get("posisi", "").lower()
        or q_low in j.get("perusahaan", "").lower()
        or q_low in j.get("lokasi", "").lower()
        or q_low in j.get("kategori", "").lower()
    ]

    web_search_url = f"https://lokeriva.vercel.app/?q={urllib.parse.quote_plus(clean_text)}"

    if not matches:
        not_found_msg = (
            f"❌ Belum ditemukan lowongan dengan kata kunci: <b>{html.escape(clean_text)}</b>\n\n"
            "💡 <b>Tips Pencarian:</b>\n"
            "• Gunakan kata yang lebih umum (misal: <code>Admin</code>, <code>Jakarta</code>, <code>Makassar</code>, <code>Sales</code>)\n"
            "• Atau periksa langsung di website kami untuk filter lebih lengkap:\n"
            f"👉 {web_search_url}"
        )
        reply_markup = {
            "inline_keyboard": [
                [{"text": "🔍 Cek di Website Lokeriva", "url": web_search_url}]
            ]
        }
        send_telegram_message(chat_id, not_found_msg, reply_markup=reply_markup)
        return jsonify({"ok": True})

    total_found = len(matches)
    top_5 = matches[:5]
    lines = [
        f"🔍 Ditemukan <b>{total_found}</b> lowongan untuk: <b>{html.escape(clean_text)}</b>\n",
        "<i>Menampilkan 5 lowongan teratas:</i>\n"
    ]
    for i, j in enumerate(top_5, 1):
        pos = html.escape(j.get("posisi", "Posisi"))
        per = html.escape(j.get("perusahaan", "Perusahaan"))
        lok = html.escape(j.get("lokasi", "Indonesia"))
        sumb = html.escape(j.get("sumber", "Portal"))
        link = j.get("link", "https://lokeriva.vercel.app")
        lines.append(
            f"{i}. <b>{pos}</b>\n"
            f"   🏢 {per}\n"
            f"   📍 {lok} | 🏷️ {sumb}\n"
            f"   🔗 <a href=\"{link}\">Lamar / Detail Loker</a>\n"
        )

    if total_found > 5:
        lines.append(f"\n✨ <i>Masih ada {total_found - 5} loker lainnya untuk kata kunci ini!</i>")

    reply_markup = {
        "inline_keyboard": [
            [{"text": f"🔎 Buka Semua ({total_found}) Loker di Web", "url": web_search_url}]
        ]
    }
    send_telegram_message(chat_id, "\n".join(lines), reply_markup=reply_markup)
    return jsonify({"ok": True})


# ==============================================================================
# OPENAPI JSON SPECIFICATION
# ==============================================================================
@app.route("/api/openapi.json", methods=["GET"])
@rate_limit(limit=100, per=60)
def openapi_spec():
    """Mengembalikan spesifikasi OpenAPI 3.0 untuk import Swagger/Postman."""
    spec = {
        "openapi": "3.0.0",
        "info": {
            "title": "Lokeriva.vercel.app REST API",
            "version": "1.0.0",
            "description": "API Agregasi Lowongan Kerja Multi-Sumber Real-Time di Indonesia dan Global WFH oleh Lokeriva.vercel.app. Created by Xnuvers007.",
            "contact": {
                "name": "Xnuvers007"
            }
        },
        "servers": [
            {"url": "https://lokeriva.vercel.app", "description": "Production Server (Vercel)"},
            {"url": "/", "description": "Local / Current Server"}
        ],
        "paths": {
            "/api/jobs": {
                "get": {
                    "summary": "Mencari & menyaring lowongan kerja",
                    "parameters": [
                        {"name": "q", "in": "query", "description": "Kata kunci pencarian", "schema": {"type": "string"}},
                        {"name": "source", "in": "query", "description": "Nama sumber data", "schema": {"type": "string"}},
                        {"name": "category", "in": "query", "description": "Kategori lowongan", "schema": {"type": "string"}},
                        {"name": "location", "in": "query", "description": "Lokasi kota / negara", "schema": {"type": "string"}},
                        {"name": "page", "in": "query", "description": "Halaman ke-n", "schema": {"type": "integer", "default": 1}},
                        {"name": "limit", "in": "query", "description": "Jumlah data per halaman", "schema": {"type": "integer", "default": 20}},
                        {"name": "sort", "in": "query", "description": "Urutkan ('newest' | 'title' | 'company')", "schema": {"type": "string", "default": "newest"}}
                    ],
                    "responses": {
                        "200": {"description": "Berhasil mendapatkan lowongan kerja"}
                    }
                }
            },
            "/api/sources": {
                "get": {
                    "summary": "Mendapatkan daftar semua sumber aktif",
                    "responses": {"200": {"description": "Daftar sumber data"}}
                }
            },
            "/api/stats": {
                "get": {
                    "summary": "Mendapatkan ringkasan statistik",
                    "responses": {"200": {"description": "Metrik agregasi loker"}}
                }
            },
            "/api/export/pdf": {
                "get": {
                    "summary": "Unduh dokumen PDF lowongan dengan hyperlink aktif",
                    "parameters": [
                        {"name": "q", "in": "query", "description": "Kata kunci pencarian", "schema": {"type": "string"}},
                        {"name": "source", "in": "query", "description": "Filter sumber", "schema": {"type": "string"}}
                    ],
                    "responses": {"200": {"description": "File PDF stream"}}
                }
            },
            "/api/export/csv": {
                "get": {
                    "summary": "Unduh data lowongan dalam format CSV",
                    "responses": {"200": {"description": "File CSV stream"}}
                }
            },
            "/api/refresh": {
                "post": {
                    "summary": "Memperbarui data cache dari semua sumber",
                    "responses": {"200": {"description": "Status pembaruan cache"}}
                }
            },
            "/api/telegram/webhook": {
                "post": {
                    "summary": "Telegram Bot Webhook (@lokeriva_bot)",
                    "description": "Menerima update webhook dari server Telegram untuk interaksi bot pencarian lowongan kerja.",
                    "responses": {"200": {"description": "Status proses webhook Telegram"}}
                }
            }
        }
    }
    return jsonify(spec)


# ==============================================================================
# ENTRY POINT LOKAL
# ==============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 MENJALANKAN LOKERIVA.VERCEL.APP FLASK SERVER")
    print("=" * 60)
    print("Akses Website  : http://localhost:5000 (Production: https://lokeriva.vercel.app)")
    print("Dokumentasi API: http://localhost:5000/docs")
    print("REST API Jobs  : http://localhost:5000/api/jobs")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=True)
