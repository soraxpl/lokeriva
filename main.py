import urllib.request
import urllib.parse
import json
import xml.etree.ElementTree as ET
import csv
import ssl
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# Memastikan output konsol mendukung karakter UTF-8 pada Windows / Pydroid 3
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ==============================================================================
# KONFIGURASI KONEKSI & HEADER HTTP (THREAD-SAFE)
# ==============================================================================
ssl_context = ssl._create_unverified_context()

# Header untuk REST API / JSON / XML
HEADERS_API = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, application/xml, */*"
}

# Header khusus HTML scraping (agar tidak terkena blokir 403 / Cloudflare)
HEADERS_HTML = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7"
}

hasil_loker = []
kunci_data = threading.Lock()


def tambah_loker(item):
    """Menambahkan data loker secara aman dari banyak thread sekaligus."""
    with kunci_data:
        hasil_loker.append(item)


def panggil_url(url, timeout=12):
    """Mengambil data API / XML / JSON."""
    req = urllib.request.Request(url, headers=HEADERS_API)
    with urllib.request.urlopen(req, context=ssl_context, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def panggil_html(url, timeout=12):
    """Mengambil halaman web HTML dengan header browser yang sesuai."""
    req = urllib.request.Request(url, headers=HEADERS_HTML)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def bersihkan_teks_html(teks):
    """Membersihkan tag HTML dan karakter entitas khusus."""
    if not teks:
        return "-"
    teks = re.sub(r"<[^>]+>", "", str(teks))
    return (
        teks.replace("&#8211;", "-")
        .replace("&#8212;", "-")
        .replace("&#038;", "&")
        .replace("&amp;", "&")
        .replace("&#8216;", "'")
        .replace("&#8217;", "'")
        .replace("&#8220;", '"')
        .replace("&#8221;", '"')
        .replace("&quot;", '"')
        .replace("&apos;", "'")
        .strip()
    )


# ==============================================================================
# 1. PUBLIC JSON API GLOBAL & WFH (7 SUMBER AKTIF TERVERIFIKASI)
# ==============================================================================
def ambil_api_jobicy(kata_kunci=""):
    tags = [kata_kunci] if kata_kunci else ["admin", "excel", "data", "medical", "support"]
    for tag in tags:
        url = f"https://jobicy.com/api/v2/remote-jobs?count=20&tag={urllib.parse.quote(tag)}"
        print(f"[API Jobicy] Mengambil tag '{tag}'...")
        try:
            data_json = json.loads(panggil_url(url))
            daftar_jobs = data_json.get("jobs", [])
            for job in daftar_jobs:
                tambah_loker({
                    "Sumber": "Jobicy API",
                    "Kategori": f"WFH / Remote ({tag.capitalize()})",
                    "Posisi": bersihkan_teks_html(job.get("jobTitle", "-")),
                    "Perusahaan": job.get("companyName", "-"),
                    "Lokasi": job.get("jobGeo", "Remote Worldwide"),
                    "Tanggal_Tayang": str(job.get("pubDate", "-"))[:10],
                    "Link": job.get("url", "-")
                })
        except Exception as e:
            print(f" -> [Jobicy '{tag}'] Lewati ({e})")


def ambil_api_remotive(kata_kunci=""):
    queries = [kata_kunci] if kata_kunci else ["data entry", "microsoft office", "administrative", "customer support", "healthcare"]
    for kw in queries:
        url = f"https://remotive.com/api/remote-jobs?search={urllib.parse.quote(kw)}&limit=20"
        print(f"[API Remotive] Mencari '{kw}'...")
        try:
            data_json = json.loads(panggil_url(url))
            daftar_jobs = data_json.get("jobs", [])
            for job in daftar_jobs:
                tambah_loker({
                    "Sumber": "Remotive API",
                    "Kategori": f"WFH / Remote ({kw})",
                    "Posisi": job.get("title", "-"),
                    "Perusahaan": job.get("company_name", "-"),
                    "Lokasi": job.get("candidate_required_location", "Remote"),
                    "Tanggal_Tayang": str(job.get("publication_date", "-"))[:10],
                    "Link": job.get("url", "-")
                })
        except Exception as e:
            print(f" -> [Remotive '{kw}'] Lewati ({e})")


def ambil_api_himalayas(kata_kunci=""):
    if kata_kunci:
        targets = [(kata_kunci, f"https://himalayas.app/jobs/api?limit=25&search={urllib.parse.quote(kata_kunci)}")]
    else:
        kategori = ["customer-support", "operations", "data", "human-resources"]
        targets = [(kat, f"https://himalayas.app/jobs/api?limit=20&category={kat}") for kat in kategori]

    for label, url in targets:
        print(f"[API Himalayas] Mengambil '{label}'...")
        try:
            data = json.loads(panggil_url(url))
            jobs = data.get("jobs", [])
            for j in jobs:
                tgl_raw = j.get("pubDate")
                if isinstance(tgl_raw, (int, float)):
                    tanggal = datetime.fromtimestamp(tgl_raw).strftime("%Y-%m-%d")
                else:
                    tanggal = str(tgl_raw or "-")[:10]

                lokasi_list = j.get("restrictedLocations") or ["Worldwide"]
                lokasi_str = "Remote (" + ", ".join(lokasi_list[:2]) + ")"

                tambah_loker({
                    "Sumber": "Himalayas API",
                    "Kategori": f"Remote ({label})",
                    "Posisi": j.get("title", "-"),
                    "Perusahaan": j.get("companyName", "-"),
                    "Lokasi": lokasi_str,
                    "Tanggal_Tayang": tanggal,
                    "Link": j.get("applicationLink") or j.get("url", "-")
                })
        except Exception as e:
            print(f" -> [Himalayas '{label}'] Lewati ({e})")


def ambil_api_working_nomads(kata_kunci=""):
    url = "https://www.workingnomads.com/api/exposed_jobs/"
    print("[API WorkingNomads] Mengunduh daftar loker remote...")
    try:
        daftar_jobs = json.loads(panggil_url(url))
        count = 0
        for j in daftar_jobs:
            posisi = j.get("title", "-")
            kategori = j.get("category_name", "General")
            if kata_kunci:
                kw_lower = kata_kunci.lower()
                if kw_lower not in posisi.lower() and kw_lower not in kategori.lower():
                    continue

            tambah_loker({
                "Sumber": "WorkingNomads API",
                "Kategori": f"Remote ({kategori})",
                "Posisi": posisi,
                "Perusahaan": j.get("company_name", "-"),
                "Lokasi": j.get("location", "Remote Worldwide") or "Remote Worldwide",
                "Tanggal_Tayang": str(j.get("pub_date", "-"))[:10],
                "Link": j.get("url", "-")
            })
            count += 1
            if count >= 35 and not kata_kunci:
                break
    except Exception as e:
        print(f" -> [WorkingNomads] Lewati ({e})")


def ambil_api_arbeitnow(kata_kunci=""):
    url = f"https://www.arbeitnow.com/api/job-board-api?search={urllib.parse.quote(kata_kunci)}" if kata_kunci else "https://www.arbeitnow.com/api/job-board-api"
    print(f"[API Arbeitnow] Mengunduh lowongan ({kata_kunci or 'Terbaru'})...")
    try:
        data = json.loads(panggil_url(url))
        daftar_jobs = data.get("data", [])
        for j in daftar_jobs[:35]:
            tgl_raw = j.get("created_at")
            if isinstance(tgl_raw, (int, float)):
                tanggal = datetime.fromtimestamp(tgl_raw).strftime("%Y-%m-%d")
            else:
                tanggal = str(tgl_raw or "-")[:10]

            tambah_loker({
                "Sumber": "Arbeitnow API",
                "Kategori": "Remote Global" if j.get("remote") else "Global Job",
                "Posisi": j.get("title", "-"),
                "Perusahaan": j.get("company_name", "-"),
                "Lokasi": j.get("location", "Global"),
                "Tanggal_Tayang": tanggal,
                "Link": j.get("url", "-")
            })
    except Exception as e:
        print(f" -> [Arbeitnow] Lewati ({e})")


def ambil_api_themuse(kata_kunci=""):
    kategori_muse = [
        "Administration and Office",
        "Customer Service",
        "Data and Analytics",
        "Healthcare"
    ]
    if kata_kunci:
        kategori_muse = [k for k in kategori_muse if kata_kunci.lower() in k.lower()] or kategori_muse[:2]

    for kat in kategori_muse:
        url = f"https://www.themuse.com/api/public/jobs?category={urllib.parse.quote(kat)}&page=1"
        print(f"[API TheMuse] Mengambil kategori '{kat}'...")
        try:
            data = json.loads(panggil_url(url))
            results = data.get("results", [])
            for j in results[:15]:
                posisi = j.get("name", "-")
                if kata_kunci and kata_kunci.lower() not in posisi.lower() and kata_kunci.lower() not in kat.lower():
                    continue
                lokasi_arr = [loc.get("name", "") for loc in j.get("locations", [])]
                lokasi_str = ", ".join(lokasi_arr) if lokasi_arr else "Flexible / Remote"
                tambah_loker({
                    "Sumber": "The Muse API",
                    "Kategori": f"Global ({kat})",
                    "Posisi": posisi,
                    "Perusahaan": j.get("company", {}).get("name", "-"),
                    "Lokasi": lokasi_str,
                    "Tanggal_Tayang": str(j.get("publication_date", "-"))[:10],
                    "Link": j.get("refs", {}).get("landing_page", "-")
                })
        except Exception as e:
            print(f" -> [TheMuse '{kat}'] Lewati ({e})")


def ambil_api_remoteok(kata_kunci=""):
    tag_param = f"?tag={urllib.parse.quote(kata_kunci.lower())}" if kata_kunci else ""
    url = f"https://remoteok.com/api{tag_param}"
    print(f"[API RemoteOK] Mengunduh lowongan remote ({kata_kunci or 'Global'})...")
    try:
        data = json.loads(panggil_url(url))
        jobs = data[1:] if len(data) > 1 else []
        for j in jobs[:25]:
            tambah_loker({
                "Sumber": "RemoteOK API",
                "Kategori": "Global Remote",
                "Posisi": j.get("position", "-"),
                "Perusahaan": j.get("company", "-"),
                "Lokasi": j.get("location", "Worldwide"),
                "Tanggal_Tayang": str(j.get("date", "-"))[:10],
                "Link": j.get("url", "-")
            })
    except Exception as e:
        print(f" -> [RemoteOK] Lewati ({e})")


# ==============================================================================
# 2. OPEN API KALIBRR (INDONESIA & ASIA TENGGARA) - BARU & 100% FREE
# ==============================================================================
def ambil_api_kalibrr_indo(kata_kunci=""):
    """
    Mengambil lowongan kerja langsung dari Public Search API Kalibrr.
    Mendukung ribuan lowongan di Indonesia (Jakarta, Surabaya, Makassar, dll).
    """
    queries = [kata_kunci] if kata_kunci else ["admin", "makassar", "kesehatan", "customer service"]
    for kw in queries:
        url = f"https://www.kalibrr.com/api/job_board/search?keyword={urllib.parse.quote(kw)}&limit=15"
        print(f"[API Kalibrr] Mencari '{kw}' di Indonesia...")
        try:
            data = json.loads(panggil_url(url))
            jobs = data.get("jobs", [])
            for j in jobs:
                posisi = j.get("name", "-")
                perusahaan = j.get("company_name") or j.get("company", {}).get("name", "-")
                comp_code = j.get("company", {}).get("code", "company")
                job_id = j.get("id", "")
                slug = j.get("slug", "")
                link = f"https://www.kalibrr.com/c/{comp_code}/jobs/{job_id}/{slug}" if job_id else "-"

                loc_info = j.get("google_location", {}).get("address_components", {})
                kota = loc_info.get("city") or loc_info.get("province") or "Indonesia"

                tgl_raw = j.get("publication_date") or j.get("created_at") or "-"

                tambah_loker({
                    "Sumber": "Kalibrr Indonesia",
                    "Kategori": f"Loker Indo ({kw.capitalize()})",
                    "Posisi": bersihkan_teks_html(posisi),
                    "Perusahaan": perusahaan,
                    "Lokasi": kota,
                    "Tanggal_Tayang": str(tgl_raw)[:10],
                    "Link": link
                })
        except Exception as e:
            print(f" -> [Kalibrr '{kw}'] Lewati ({e})")


# ==============================================================================
# 3. OPEN ATS API (PERUSAHAAN TECH & STARTUP TERVERIFIKASI AKTIF)
# ==============================================================================
def ambil_ats_greenhouse(kata_kunci=""):
    """
    Mengambil lowongan langsung dari ATS Greenhouse perusahaan terverifikasi aktif.
    (Xendit, Agoda, Kargo Technologies, Flip Indonesia).
    """
    perusahaan_tokens = [
        ("xendit", "Xendit"),
        ("agoda", "Agoda"),
        ("kargo", "Kargo Technologies"),
        ("flip", "Flip Indonesia")
    ]
    for token, nama_pt in perusahaan_tokens:
        url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
        print(f"[Greenhouse ATS] Mengecek {nama_pt}...")
        try:
            data = json.loads(panggil_url(url))
            jobs = data.get("jobs", [])
            for j in jobs:
                title = j.get("title", "-")
                lokasi = j.get("location", {}).get("name", "Indonesia / Asia")

                if kata_kunci:
                    if kata_kunci.lower() not in title.lower() and kata_kunci.lower() not in lokasi.lower():
                        continue
                else:
                    if not any(k in lokasi.lower() for k in ["indonesia", "jakarta", "makassar", "bandung", "surabaya", "remote", "asia", "thailand", "singapore"]):
                        continue

                tambah_loker({
                    "Sumber": f"Greenhouse ({nama_pt})",
                    "Kategori": "Tech & Startup ATS",
                    "Posisi": title,
                    "Perusahaan": nama_pt,
                    "Lokasi": lokasi,
                    "Tanggal_Tayang": str(j.get("updated_at", "-"))[:10],
                    "Link": j.get("absolute_url", "-")
                })
        except Exception as e:
            print(f" -> [Greenhouse {nama_pt}] Lewati ({e})")


# ==============================================================================
# 4. WORDPRESS REST API (8 PORTAL LOKER INDONESIA TERVERIFIKASI AKTIF)
# ==============================================================================
def ambil_semua_wp_json_indonesia(kata_kunci=""):
    """
    Memindai 8 portal lowongan kerja Indonesia berbasis WordPress yang 100% aktif
    menggunakan endpoint resmi /wp-json/wp/v2/posts?search=...
    """
    daftar_portal_aktif = [
        ("https://www.disnakerja.com", "Disnakerja"),
        ("https://lokerbumn.com", "LokerBUMN"),
        ("https://bursakerjadepnaker.com", "BursaDepnaker"),
        ("https://www.lokerjogja.id", "LokerJogja"),
        ("https://lokerutama.com", "LokerUtama"),
        ("https://lokerbandung.id", "LokerBandung"),
        ("https://lokerpintar.id", "LokerPintar"),
        ("https://jakartakerja.com", "JakartaKerja")
    ]

    default_keywords = ["Makassar", "Admin", "BUMN", "Kesehatan", "Bidan"]
    keywords = [kata_kunci] if kata_kunci else default_keywords

    for domain, nama_label in daftar_portal_aktif:
        for kw in keywords:
            url = f"{domain}/wp-json/wp/v2/posts?search={urllib.parse.quote(kw)}&per_page=8"
            print(f"[WP-JSON] Mencari '{kw}' di {nama_label}...")
            try:
                daftar_post = json.loads(panggil_url(url, timeout=10))
                if not isinstance(daftar_post, list):
                    continue
                for post in daftar_post:
                    judul_mentah = post.get("title", {}).get("rendered", "-")
                    judul_bersih = bersihkan_teks_html(judul_mentah)

                    tambah_loker({
                        "Sumber": f"{nama_label} (WP)",
                        "Kategori": f"Loker Indo ({kw})",
                        "Posisi": judul_bersih,
                        "Perusahaan": "Lihat di detail lowongan",
                        "Lokasi": kw if kw.lower() in ["makassar", "sulawesi selatan", "bandung", "jakarta", "jogja"] else f"Indonesia ({nama_label})",
                        "Tanggal_Tayang": str(post.get("date", "-"))[:10],
                        "Link": post.get("link", "-")
                    })
            except Exception as e:
                print(f" -> [{nama_label} - '{kw}'] Lewati ({e})")


# ==============================================================================
# 5. RSS XML FEED PARSER (FEED AKTIF DENGAN VOLUME BESAR)
# ==============================================================================
def ambil_rss_loker_lengkap(kata_kunci=""):
    """Mengambil feed XML RSS aktif dengan pembersihan entitas XML otomatis."""
    daftar_rss = [
        ("Loker Makassar / Sulsel", "https://www.disnakerja.com/tag/makassar/feed/"),
        ("Loker Medis & Kesehatan", "https://www.disnakerja.com/kategori/kesehatan-medis/feed/"),
        ("Loker BUMN Terbaru", "https://www.disnakerja.com/kategori/bumn/feed/"),
        ("WeWorkRemotely Global", "https://weworkremotely.com/remote-jobs.rss"),
        ("Remotive Remote Feed", "https://remotive.com/remote-jobs/feed"),
        ("Jobspresso Remote WFH", "https://jobspresso.co/feed/?post_type=job_listing"),
        ("NodeDesk Remote Feeds", "https://nodesk.co/remote-jobs/index.xml")
    ]

    for label, url_rss in daftar_rss:
        print(f"[RSS XML] Mengambil feed: {label}...")
        try:
            xml_teks = panggil_url(url_rss, timeout=10)
            # Membersihkan entitas XML tidak standar agar parser tidak error
            xml_bersih = re.sub(r'&(?!(?:amp|lt|gt|quot|apos);)', '&amp;', xml_teks)
            xml_bersih = re.sub(r'&#(?!\d+;|x[0-9a-fA-F]+;)', '&amp;#', xml_bersih)

            root = ET.fromstring(xml_bersih)
            items = root.findall(".//item")

            for item in items[:20]:
                judul = bersihkan_teks_html(item.findtext("title", default="-"))
                link = item.findtext("link", default="-").strip()
                tanggal = item.findtext("pubDate", default="-").strip()

                if kata_kunci:
                    if kata_kunci.lower() not in judul.lower() and kata_kunci.lower() not in label.lower():
                        continue

                tambah_loker({
                    "Sumber": "RSS Feed",
                    "Kategori": label,
                    "Posisi": judul,
                    "Perusahaan": "Cek Detail Tautan",
                    "Lokasi": "Indonesia / Remote",
                    "Tanggal_Tayang": tanggal[:16],
                    "Link": link
                })
        except Exception as e:
            print(f" -> [RSS {label}] Lewati ({e})")


# ==============================================================================
# 6. HTML SCRAPER MODERN (LOKER.ID) - PENCARIAN REAL-TIME & DETAIL LENGKAP
# ==============================================================================
def scrape_html_loker_id(kata_kunci=""):
    """
    Scraping real-time ke Loker.id menggunakan header browser dan kartu <article>.
    Mengekstrak judul, perusahaan, lokasi kota, dan link pekerjaan.
    """
    targets = []
    if kata_kunci:
        targets.append((f"Loker.id ('{kata_kunci}')", f"https://www.loker.id/cari-lowongan-kerja?q={urllib.parse.quote(kata_kunci)}", "Indonesia"))
    else:
        targets.append(("Loker Wilayah Makassar", "https://www.loker.id/lokasi-pekerjaan/makassar", "Makassar, Sulsel"))
        targets.append(("Loker Administrasi", "https://www.loker.id/cari-lowongan-kerja?q=admin", "Indonesia (Admin)"))
        targets.append(("Loker Medis & Kesehatan", "https://www.loker.id/cari-lowongan-kerja?q=medis", "Indonesia (Medis)"))

    for kategori, url, lokasi_default in targets:
        print(f"[HTML Scraper] Memindai {url}...")
        try:
            html = panggil_html(url, timeout=12)
            articles = re.findall(r'<article[^>]*>(.*?)</article>', html, re.DOTALL)
            for art in articles[:20]:
                aria_m = re.search(r'aria-label=["\']Lihat detail pekerjaan (.*?)["\']', art)
                h3_m = re.search(r'<h3[^>]*>(.*?)</h3>', art, re.DOTALL)
                posisi = aria_m.group(1).strip() if aria_m else (bersihkan_teks_html(h3_m.group(1)) if h3_m else "-")

                # URL pekerjaan
                link_m = re.search(r'href=["\'](/[^"\']*jobid=\d+[^"\']*)["\']', art)
                if not link_m:
                    link_m = re.search(r'href=["\'](/[^"\']+\.html)["\']', art)
                link = ("https://www.loker.id" + link_m.group(1).replace("&amp;", "&")) if link_m else url

                # Perusahaan
                comp_m = re.search(r'<span class="text-sm text-secondary-600">([^<]+)</span>', art)
                if not comp_m:
                    comp_m = re.search(r'alt=["\']logo ([^"\']+)["\']', art)
                perusahaan = comp_m.group(1).strip() if comp_m else "Lihat di Loker.id"

                # Lokasi kota
                loc_m = re.search(r'class="icon-tabler-map-pin[^"]*".*?<span translate="no"[^>]*>([^<]+)</span>', art, re.DOTALL)
                lokasi = loc_m.group(1).strip() if loc_m else lokasi_default

                # Tanggal
                time_m = re.search(r'dateTime=["\']([^"\']+)["\']', art)
                tanggal = time_m.group(1)[:10] if time_m else datetime.now().strftime("%Y-%m-%d")

                tambah_loker({
                    "Sumber": "Loker.id (Scrape)",
                    "Kategori": kategori,
                    "Posisi": bersihkan_teks_html(posisi),
                    "Perusahaan": bersihkan_teks_html(perusahaan),
                    "Lokasi": lokasi,
                    "Tanggal_Tayang": tanggal,
                    "Link": link
                })
        except Exception as e:
            print(f" -> [Loker.id Scraper {kategori}] Lewati ({e})")


# ==============================================================================
# 7. SIMPAN KE CSV & HTML DENGAN TAMPILAN PREMIUM & FILTER INSTAN
# ==============================================================================
def simpan_hasil(kata_kunci=""):
    if not hasil_loker:
        print("\nTidak ada data yang berhasil ditarik. Pastikan koneksi internet aktif.")
        return

    # Menghapus duplikat lowongan berdasarkan URL unik
    loker_unik = {}
    for item in hasil_loker:
        link = item.get("Link", "-")
        if link and link != "-":
            loker_unik[link] = item
    daftar_final = list(loker_unik.values())

    print("\n" + "=" * 65)
    print(f"BERHASIL MENGUMPULKAN TOTAL {len(daftar_final)} LOWONGAN KERJA UNIK!")
    if kata_kunci:
        print(f"Filter Pencarian  : '{kata_kunci}'")
    else:
        print("Filter Pencarian  : DEFAULT (Makassar, Admin, Medis, BUMN, WFH Remote)")
    print("=" * 65)
    for idx, item in enumerate(daftar_final[:10], start=1):
        print(f"{idx}. [{item['Kategori']}] {item['Posisi']}")
        print(f"   Sumber : {item['Sumber']} | Lokasi: {item['Lokasi']}")
        print(f"   Link   : {item['Link']}\n")

    # Lokasi simpan (Otomatis ke Download Android jika di Pydroid 3, atau direktori saat ini)
    folder_download_hp = "/storage/emulated/0/Download"
    if os.path.exists(folder_download_hp) and os.access(folder_download_hp, os.W_OK):
        folder_simpan = folder_download_hp
    else:
        folder_simpan = os.getcwd()

    nama_csv = os.path.join(folder_simpan, "Loker_Super_Lengkap.csv")
    nama_html = os.path.join(folder_simpan, "Portal_Loker_Interaktif.html")

    kolom = ["Sumber", "Kategori", "Posisi", "Perusahaan", "Lokasi", "Tanggal_Tayang", "Link"]

    try:
        # Simpan CSV (UTF-8 BOM agar rapi dibuka di Excel HP/PC)
        with open(nama_csv, mode="w", newline="", encoding="utf-8-sig") as file_csv:
            writer = csv.DictWriter(file_csv, fieldnames=kolom, delimiter=";")
            writer.writeheader()
            writer.writerows(daftar_final)

        # Generate Baris Tabel HTML
        baris_tabel = ""
        for no, loker in enumerate(daftar_final, start=1):
            baris_tabel += f"""
            <tr>
                <td>{no}</td>
                <td><span class="badge">{loker['Sumber']}</span></td>
                <td><span class="category-tag">{loker['Kategori']}</span></td>
                <td><b>{loker['Posisi']}</b></td>
                <td>{loker['Perusahaan']}</td>
                <td>{loker['Lokasi']}</td>
                <td>{loker['Tanggal_Tayang']}</td>
                <td><a href="{loker['Link']}" target="_blank" rel="noopener noreferrer" class="btn">Lamar / Buka</a></td>
            </tr>
            """

        judul_filter = f"Kata Kunci: '{kata_kunci}'" if kata_kunci else "Mode Default (Makassar, Bidan, Medis, Admin, BUMN, Remote)"

        isi_html = f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Portal Agregator Lowongan Kerja Aktif</title>
    <style>
        :root {{
            --primary: #2563eb;
            --primary-dark: #1d4ed8;
            --accent: #059669;
            --accent-hover: #047857;
            --bg: #f8fafc;
            --card-bg: #ffffff;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --border: #e2e8f0;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 16px;
            background: var(--bg);
            color: var(--text-main);
        }}
        .header-box {{
            background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 50%, #38bdf8 100%);
            color: white;
            padding: 24px;
            border-radius: 14px;
            margin-bottom: 20px;
            box-shadow: 0 10px 25px -5px rgba(37, 99, 235, 0.25);
        }}
        .header-box h2 {{ margin: 0 0 8px 0; font-size: 24px; font-weight: 700; }}
        .header-box p {{ margin: 0 0 12px 0; font-size: 14px; opacity: 0.95; }}
        .tag-info {{
            display: inline-block;
            background: rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(4px);
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
        }}
        .search-container {{
            margin-bottom: 16px;
            position: sticky;
            top: 12px;
            z-index: 100;
        }}
        .search-box {{
            width: 100%;
            padding: 14px 18px;
            font-size: 15px;
            border: 2px solid var(--primary);
            border-radius: 12px;
            outline: none;
            background: #ffffff;
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);
            transition: all 0.2s ease;
        }}
        .search-box:focus {{
            border-color: var(--primary-dark);
            box-shadow: 0 8px 24px rgba(37, 99, 235, 0.25);
        }}
        .stats-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            font-size: 13px;
            color: var(--text-muted);
            font-weight: 500;
            padding: 0 4px;
        }}
        .table-wrap {{
            overflow-x: auto;
            background: var(--card-bg);
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
            border: 1px solid var(--border);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            min-width: 820px;
        }}
        th, td {{
            border-bottom: 1px solid #f1f5f9;
            padding: 12px 14px;
            text-align: left;
            font-size: 13px;
            vertical-align: middle;
        }}
        th {{
            background-color: #0f172a;
            color: #f8fafc;
            font-weight: 600;
            position: sticky;
            top: 0;
            letter-spacing: 0.3px;
        }}
        tr:hover {{ background-color: #f8faff; }}
        .badge {{
            background: #eff6ff;
            color: #1d4ed8;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
            border: 1px solid #bfdbfe;
            display: inline-block;
            white-space: nowrap;
        }}
        .category-tag {{
            background: #f1f5f9;
            color: #334155;
            padding: 3px 7px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 500;
        }}
        .btn {{
            background: var(--accent);
            color: white;
            padding: 7px 14px;
            text-decoration: none;
            border-radius: 6px;
            display: inline-block;
            font-weight: 600;
            font-size: 12px;
            transition: all 0.15s ease;
            white-space: nowrap;
        }}
        .btn:hover {{
            background: var(--accent-hover);
            transform: translateY(-1px);
            box-shadow: 0 4px 10px rgba(5, 150, 105, 0.3);
        }}
    </style>
</head>
<body>
    <div class="header-box">
        <h2>🚀 Portal Agregator Lowongan Kerja Otomatis</h2>
        <p>Total data terkumpul: <b>{len(daftar_final)} lowongan kerja unik</b> | Terakhir diperbarui: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</p>
        <span class="tag-info">📌 {judul_filter}</span>
    </div>

    <div class="search-container">
        <input type="text" id="inputCari" class="search-box" onkeyup="saringTabel()" placeholder="🔍 Ketik untuk memfilter instan (contoh: Makassar, Bidan, Admin, Remote, BUMN, Jakarta, Excel)...">
    </div>

    <div class="stats-bar">
        <span id="counterTampil">Menampilkan <b>{len(daftar_final)}</b> dari <b>{len(daftar_final)}</b> lowongan</span>
        <span>💡 Klik tombol 'Lamar / Buka' untuk langsung membuka halaman resmi loker</span>
    </div>

    <div class="table-wrap">
        <table id="tabelLoker">
            <thead>
                <tr>
                    <th style="width: 45px;">No</th>
                    <th>Sumber</th>
                    <th>Kategori</th>
                    <th>Posisi / Judul Loker</th>
                    <th>Perusahaan</th>
                    <th>Lokasi</th>
                    <th>Tanggal</th>
                    <th style="width: 100px;">Aksi</th>
                </tr>
            </thead>
            <tbody>
                {baris_tabel}
            </tbody>
        </table>
    </div>

    <script>
    function saringTabel() {{
        var input = document.getElementById("inputCari");
        var filter = input.value.toLowerCase();
        var table = document.getElementById("tabelLoker");
        var tr = table.getElementsByTagName("tr");
        var count = 0;
        for (var i = 1; i < tr.length; i++) {{
            var teksBaris = tr[i].textContent || tr[i].innerText;
            if (teksBaris.toLowerCase().indexOf(filter) > -1) {{
                tr[i].style.display = "";
                count++;
            }} else {{
                tr[i].style.display = "none";
            }}
        }}
        document.getElementById("counterTampil").innerHTML = "Menampilkan <b>" + count + "</b> dari <b>{len(daftar_final)}</b> lowongan";
    }}
    </script>
</body>
</html>"""

        with open(nama_html, mode="w", encoding="utf-8") as file_html:
            file_html.write(isi_html)

        print("=" * 65)
        print(f"SELESAI! Total {len(daftar_final)} lowongan unik berhasil disimpan.")
        print(f"File CSV  : {nama_csv}")
        print(f"File HTML : {nama_html} (Buka di browser untuk fitur pencarian)")
        print("=" * 65)
    except Exception as e:
        print(f"\nCatatan: Gagal menyimpan file ke memori ({e}), namun daftar sudah tampil di layar.")


# ==============================================================================
# TITIK MASUK UTAMA (MENDUKUNG INPUT INTERAKTIF & CLI ARGUMENT)
# ==============================================================================
if __name__ == "__main__":
    kata_kunci = ""
    # Jika dijalankan dengan argumen terminal (misal: python main.py "Bidan")
    if len(sys.argv) > 1:
        kata_kunci = " ".join(sys.argv[1:]).strip()
    else:
        try:
            print("=" * 65)
            print("[LOKERIVA.VERCEL.APP] AGREGATOR LOWONGAN KERJA OTOMATIS (MULTI-SUMBER)")
            print("Created by Xnuvers007")
            print("=" * 65)
            print("Masukkan kata kunci pencarian (contoh: Makassar, Bidan, Admin, Python, BUMN)")
            user_input = input("[Tekan ENTER langsung untuk menggunakan DEFAULT]: ")
            kata_kunci = user_input.strip()
        except (EOFError, KeyboardInterrupt):
            kata_kunci = ""

    if kata_kunci:
        print(f"\n[MODE PENCARIAN] Mencari dengan kata kunci: '{kata_kunci}'")
    else:
        print("\n[MODE DEFAULT] Menggunakan kategori bawaan (Makassar, Medis, Admin, BUMN, Remote WFH)...")

    print("Memulai penarikan paralel (Multi-Threading) dari semua sumber aktif...\n")
    daftar_tugas = [
        lambda: ambil_api_jobicy(kata_kunci),
        lambda: ambil_api_remotive(kata_kunci),
        lambda: ambil_api_himalayas(kata_kunci),
        lambda: ambil_api_working_nomads(kata_kunci),
        lambda: ambil_api_arbeitnow(kata_kunci),
        lambda: ambil_api_themuse(kata_kunci),
        lambda: ambil_api_remoteok(kata_kunci),
        lambda: ambil_api_kalibrr_indo(kata_kunci),
        lambda: ambil_ats_greenhouse(kata_kunci),
        lambda: ambil_semua_wp_json_indonesia(kata_kunci),
        lambda: ambil_rss_loker_lengkap(kata_kunci),
        lambda: scrape_html_loker_id(kata_kunci)
    ]

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(fn) for fn in daftar_tugas]
        for future in futures:
            try:
                future.result()
            except Exception as err:
                print(f"Error pada salah satu tugas: {err}")

    simpan_hasil(kata_kunci)