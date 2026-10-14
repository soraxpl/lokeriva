import io
import csv
import math
import re
import secrets
from datetime import datetime
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
    base_url = request.url_root.rstrip("/")
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
@app.route("/api/jobs", methods=["GET"])
@rate_limit(limit=120, per=60)
def get_jobs():
    """
    Endpoint utama pencarian dan filtering lowongan kerja.
    Parameter Query:
      - q: Kata kunci pencarian (judul, perusahaan, lokasi, dll)
      - source: Filter spesifik sumber (misal: 'Kalibrr Indonesia', 'Jobicy API')
      - category: Filter kategori (misal: 'Remote', 'Medis', 'Admin')
      - location: Filter kota/negara (misal: 'Makassar', 'Jakarta')
      - page: Nomor halaman (default 1)
      - limit: Jumlah per halaman (default 20, max 100)
      - sort: 'newest' | 'title' | 'company'
    """
    query = sanitize_query(request.args.get("q", ""))
    source = sanitize_query(request.args.get("source", ""))
    category = sanitize_query(request.args.get("category", ""))
    location = sanitize_query(request.args.get("location", ""))
    location_type = sanitize_query(request.args.get("location_type", "all")) # 'all' | 'remote' | 'onsite'
    sort_by = sanitize_query(request.args.get("sort", "newest"))

    try:
        page = max(1, int(request.args.get("page", 1)))
        limit = min(100, max(1, int(request.args.get("limit", 20))))
    except ValueError:
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
# OPENAPI JSON SPECIFICATION
# ==============================================================================
@app.route("/api/openapi.json", methods=["GET"])
@rate_limit(limit=100, per=60)
def openapi_spec():
    """Mengembalikan spesifikasi OpenAPI 3.0 untuk import Swagger/Postman."""
    spec = {
        "openapi": "3.0.0",
        "info": {
            "title": "Lokeriva.id REST API",
            "version": "1.0.0",
            "description": "API Agregasi Lowongan Kerja Multi-Sumber Real-Time di Indonesia dan Global WFH oleh Lokeriva.id. Created by Xnuvers007.",
            "contact": {
                "name": "Xnuvers007"
            }
        },
        "servers": [{"url": "/", "description": "Current Server"}],
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
            }
        }
    }
    return jsonify(spec)


# ==============================================================================
# ENTRY POINT LOKAL
# ==============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 MENJALANKAN LOKERIVA.ID FLASK SERVER")
    print("=" * 60)
    print("Akses Website  : http://localhost:5000")
    print("Dokumentasi API: http://localhost:5000/docs")
    print("REST API Jobs  : http://localhost:5000/api/jobs")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=True)
