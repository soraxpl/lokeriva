import urllib.request
import urllib.parse
import json
import xml.etree.ElementTree as ET
import ssl
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# ==============================================================================
# KONFIGURASI KONEKSI & HEADERS HTTP
# ==============================================================================
ssl_context = ssl._create_unverified_context()

HEADERS_API = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, application/xml, */*"
}

HEADERS_HTML = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7"
}


def panggil_url(url, timeout=6):
    """Mengambil data REST API / JSON / XML dengan proteksi timeout."""
    req = urllib.request.Request(url, headers=HEADERS_API)
    with urllib.request.urlopen(req, context=ssl_context, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def panggil_html(url, timeout=6):
    """Mengambil data HTML dengan header browser standar."""
    req = urllib.request.Request(url, headers=HEADERS_HTML)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def bersihkan_teks_html(teks):
    """Membersihkan entitas HTML, tag script, dan karakter kontrol khusus."""
    if not teks:
        return "-"
    # Hapus tag script & style berserta isinya jika ada
    teks = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", str(teks), flags=re.DOTALL | re.IGNORECASE)
    # Hapus seluruh tag HTML lainnya
    teks = re.sub(r"<[^>]+>", "", teks)
    # Hapus karakter kontrol
    teks = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", teks)
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


def sanitasi_link(link):
    """
    Memastikan tautan hanya menggunakan protokol HTTP/HTTPS yang valid.
    Menolak protokol berbahaya seperti javascript:, data:, file:, vbscript:.
    """
    if not link or not isinstance(link, str):
        return "#"
    link = link.strip()
    # Hapus karakter kontrol dan whitespace berbahaya
    link = re.sub(r"[\x00-\x1f\x7f\r\n\t]", "", link)
    if link.lower().startswith("https://") or link.lower().startswith("http://"):
        return link
    return "#"


# ==============================================================================
# FUNGSI PENGAMBILAN DARI SETIAP SUMBER LOKER TERUJI
# ==============================================================================

def fetch_jobicy(kata_kunci="", output_list=None):
    tags = [kata_kunci] if kata_kunci else ["admin", "excel", "data", "medical", "support"]
    for tag in tags:
        try:
            url = f"https://jobicy.com/api/v2/remote-jobs?count=20&tag={urllib.parse.quote(tag)}"
            data = json.loads(panggil_url(url, timeout=5))
            for job in data.get("jobs", []):
                output_list.append({
                    "id": f"jobicy-{job.get('id', hash(job.get('url', '')))}",
                    "sumber": "Jobicy API",
                    "kategori": f"WFH / Remote ({tag.capitalize()})",
                    "posisi": bersihkan_teks_html(job.get("jobTitle", "-")),
                    "perusahaan": bersihkan_teks_html(job.get("companyName", "-")),
                    "lokasi": job.get("jobGeo", "Remote Worldwide"),
                    "tanggal": str(job.get("pubDate", "-"))[:10],
                    "link": sanitasi_link(job.get("url", ""))
                })
        except Exception:
            continue


def fetch_remotive(kata_kunci="", output_list=None):
    queries = [kata_kunci] if kata_kunci else ["data entry", "administrative", "customer support", "healthcare"]
    for kw in queries:
        try:
            url = f"https://remotive.com/api/remote-jobs?search={urllib.parse.quote(kw)}&limit=20"
            data = json.loads(panggil_url(url, timeout=5))
            for job in data.get("jobs", []):
                output_list.append({
                    "id": f"remotive-{job.get('id', hash(job.get('url', '')))}",
                    "sumber": "Remotive API",
                    "kategori": f"WFH / Remote ({kw.capitalize()})",
                    "posisi": bersihkan_teks_html(job.get("title", "-")),
                    "perusahaan": bersihkan_teks_html(job.get("company_name", "-")),
                    "lokasi": job.get("candidate_required_location", "Remote"),
                    "tanggal": str(job.get("publication_date", "-"))[:10],
                    "link": sanitasi_link(job.get("url", ""))
                })
        except Exception:
            continue


def fetch_himalayas(kata_kunci="", output_list=None):
    if kata_kunci:
        targets = [(kata_kunci, f"https://himalayas.app/jobs/api?limit=25&search={urllib.parse.quote(kata_kunci)}")]
    else:
        kategori = ["customer-support", "operations", "data", "human-resources"]
        targets = [(kat, f"https://himalayas.app/jobs/api?limit=20&category={kat}") for kat in kategori]

    for label, url in targets:
        try:
            data = json.loads(panggil_url(url, timeout=5))
            for j in data.get("jobs", []):
                tgl_raw = j.get("pubDate")
                if isinstance(tgl_raw, (int, float)):
                    tanggal = datetime.fromtimestamp(tgl_raw).strftime("%Y-%m-%d")
                else:
                    tanggal = str(tgl_raw or "-")[:10]

                lokasi_list = j.get("restrictedLocations") or ["Worldwide"]
                lokasi_str = "Remote (" + ", ".join(lokasi_list[:2]) + ")"

                output_list.append({
                    "id": f"himalayas-{hash(j.get('applicationLink') or j.get('url', ''))}",
                    "sumber": "Himalayas API",
                    "kategori": f"Remote ({label})",
                    "posisi": bersihkan_teks_html(j.get("title", "-")),
                    "perusahaan": bersihkan_teks_html(j.get("companyName", "-")),
                    "lokasi": lokasi_str,
                    "tanggal": tanggal,
                    "link": sanitasi_link(j.get("applicationLink") or j.get("url", ""))
                })
        except Exception:
            continue


def fetch_working_nomads(kata_kunci="", output_list=None):
    try:
        url = "https://www.workingnomads.com/api/exposed_jobs/"
        daftar_jobs = json.loads(panggil_url(url, timeout=5))
        count = 0
        for j in daftar_jobs:
            posisi = j.get("title", "-")
            kategori = j.get("category_name", "General")
            if kata_kunci:
                kw_lower = kata_kunci.lower()
                if kw_lower not in posisi.lower() and kw_lower not in kategori.lower():
                    continue

            output_list.append({
                "id": f"wn-{hash(j.get('url', ''))}",
                "sumber": "WorkingNomads API",
                "kategori": f"Remote ({kategori})",
                "posisi": bersihkan_teks_html(posisi),
                "perusahaan": bersihkan_teks_html(j.get("company_name", "-")),
                "lokasi": j.get("location", "Remote Worldwide") or "Remote Worldwide",
                "tanggal": str(j.get("pub_date", "-"))[:10],
                "link": sanitasi_link(j.get("url", ""))
            })
            count += 1
            if count >= 35 and not kata_kunci:
                break
    except Exception:
        pass


def fetch_arbeitnow(kata_kunci="", output_list=None):
    try:
        url = f"https://www.arbeitnow.com/api/job-board-api?search={urllib.parse.quote(kata_kunci)}" if kata_kunci else "https://www.arbeitnow.com/api/job-board-api"
        data = json.loads(panggil_url(url, timeout=5))
        for j in data.get("data", [])[:35]:
            tgl_raw = j.get("created_at")
            if isinstance(tgl_raw, (int, float)):
                tanggal = datetime.fromtimestamp(tgl_raw).strftime("%Y-%m-%d")
            else:
                tanggal = str(tgl_raw or "-")[:10]

            output_list.append({
                "id": f"arbeitnow-{j.get('slug', hash(j.get('url', '')))}",
                "sumber": "Arbeitnow API",
                "kategori": "Remote Global" if j.get("remote") else "Global Job",
                "posisi": bersihkan_teks_html(j.get("title", "-")),
                "perusahaan": bersihkan_teks_html(j.get("company_name", "-")),
                "lokasi": j.get("location", "Global"),
                "tanggal": tanggal,
                "link": sanitasi_link(j.get("url", ""))
            })
    except Exception:
        pass


def fetch_themuse(kata_kunci="", output_list=None):
    kategori_muse = ["Administration and Office", "Customer Service", "Data and Analytics", "Healthcare"]
    if kata_kunci:
        kategori_muse = [k for k in kategori_muse if kata_kunci.lower() in k.lower()] or kategori_muse[:2]

    for kat in kategori_muse:
        try:
            url = f"https://www.themuse.com/api/public/jobs?category={urllib.parse.quote(kat)}&page=1"
            data = json.loads(panggil_url(url, timeout=5))
            for j in data.get("results", [])[:15]:
                posisi = j.get("name", "-")
                if kata_kunci and kata_kunci.lower() not in posisi.lower() and kata_kunci.lower() not in kat.lower():
                    continue
                lokasi_arr = [loc.get("name", "") for loc in j.get("locations", [])]
                lokasi_str = ", ".join(lokasi_arr) if lokasi_arr else "Flexible / Remote"

                output_list.append({
                    "id": f"themuse-{j.get('id', hash(j.get('refs', {}).get('landing_page', '')))}",
                    "sumber": "The Muse API",
                    "kategori": f"Global ({kat})",
                    "posisi": bersihkan_teks_html(posisi),
                    "perusahaan": bersihkan_teks_html(j.get("company", {}).get("name", "-")),
                    "lokasi": lokasi_str,
                    "tanggal": str(j.get("publication_date", "-"))[:10],
                    "link": sanitasi_link(j.get("refs", {}).get("landing_page", ""))
                })
        except Exception:
            continue


def fetch_remoteok(kata_kunci="", output_list=None):
    try:
        tag_param = f"?tag={urllib.parse.quote(kata_kunci.lower())}" if kata_kunci else ""
        url = f"https://remoteok.com/api{tag_param}"
        data = json.loads(panggil_url(url, timeout=5))
        jobs = data[1:] if len(data) > 1 else []
        for j in jobs[:25]:
            output_list.append({
                "id": f"remoteok-{j.get('id', hash(j.get('url', '')))}",
                "sumber": "RemoteOK API",
                "kategori": "Global Remote",
                "posisi": bersihkan_teks_html(j.get("position", "-")),
                "perusahaan": bersihkan_teks_html(j.get("company", "-")),
                "lokasi": j.get("location", "Worldwide"),
                "tanggal": str(j.get("date", "-"))[:10],
                "link": sanitasi_link(j.get("url", ""))
            })
    except Exception:
        pass


def fetch_kalibrr(kata_kunci="", output_list=None):
    queries = [kata_kunci] if kata_kunci else ["admin", "makassar", "kesehatan", "customer service"]
    for kw in queries:
        try:
            url = f"https://www.kalibrr.com/api/job_board/search?keyword={urllib.parse.quote(kw)}&limit=15"
            data = json.loads(panggil_url(url, timeout=5))
            for j in data.get("jobs", []):
                posisi = j.get("name", "-")
                perusahaan = j.get("company_name") or j.get("company", {}).get("name", "-")
                comp_code = j.get("company", {}).get("code", "company")
                job_id = j.get("id", "")
                slug = j.get("slug", "")
                link = f"https://www.kalibrr.com/c/{comp_code}/jobs/{job_id}/{slug}" if job_id else ""

                loc_info = j.get("google_location", {}).get("address_components", {})
                kota = loc_info.get("city") or loc_info.get("province") or "Indonesia"
                tgl_raw = j.get("publication_date") or j.get("created_at") or "-"

                output_list.append({
                    "id": f"kalibrr-{job_id}",
                    "sumber": "Kalibrr Indonesia",
                    "kategori": f"Loker Indo ({kw.capitalize()})",
                    "posisi": bersihkan_teks_html(posisi),
                    "perusahaan": bersihkan_teks_html(perusahaan),
                    "lokasi": kota,
                    "tanggal": str(tgl_raw)[:10],
                    "link": sanitasi_link(link)
                })
        except Exception:
            continue


def fetch_greenhouse(kata_kunci="", output_list=None):
    perusahaan_tokens = [
        ("xendit", "Xendit"),
        ("agoda", "Agoda"),
        ("kargo", "Kargo Technologies"),
        ("flip", "Flip Indonesia")
    ]
    for token, nama_pt in perusahaan_tokens:
        try:
            url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
            data = json.loads(panggil_url(url, timeout=5))
            for j in data.get("jobs", []):
                title = j.get("title", "-")
                lokasi = j.get("location", {}).get("name", "Indonesia / Asia")

                if kata_kunci:
                    if kata_kunci.lower() not in title.lower() and kata_kunci.lower() not in lokasi.lower():
                        continue
                else:
                    if not any(k in lokasi.lower() for k in ["indonesia", "jakarta", "makassar", "bandung", "surabaya", "remote", "asia"]):
                        continue

                output_list.append({
                    "id": f"gh-{j.get('id', hash(j.get('absolute_url', '')))}",
                    "sumber": f"Greenhouse ({nama_pt})",
                    "kategori": "Tech & Startup ATS",
                    "posisi": bersihkan_teks_html(title),
                    "perusahaan": nama_pt,
                    "lokasi": lokasi,
                    "tanggal": str(j.get("updated_at", "-"))[:10],
                    "link": sanitasi_link(j.get("absolute_url", ""))
                })
        except Exception:
            continue


def fetch_wordpress_indo(kata_kunci="", output_list=None):
    daftar_portal = [
        ("https://www.disnakerja.com", "Disnakerja"),
        ("https://lokerbumn.com", "LokerBUMN"),
        ("https://bursakerjadepnaker.com", "BursaDepnaker"),
        ("https://www.lokerjogja.id", "LokerJogja"),
        ("https://lokerutama.com", "LokerUtama"),
        ("https://lokerbandung.id", "LokerBandung"),
        ("https://lokerpintar.id", "LokerPintar"),
        ("https://jakartakerja.com", "JakartaKerja")
    ]
    keywords = [kata_kunci] if kata_kunci else ["Makassar", "Admin", "BUMN", "Kesehatan", "Bidan"]

    for domain, nama_label in daftar_portal:
        for kw in keywords:
            try:
                url = f"{domain}/wp-json/wp/v2/posts?search={urllib.parse.quote(kw)}&per_page=6"
                posts = json.loads(panggil_url(url, timeout=5))
                if isinstance(posts, list):
                    for p in posts:
                        judul = bersihkan_teks_html(p.get("title", {}).get("rendered", "-"))
                        output_list.append({
                            "id": f"wp-{p.get('id', hash(p.get('link', '')))}",
                            "sumber": f"{nama_label} (WP)",
                            "kategori": f"Loker Indo ({kw})",
                            "posisi": judul,
                            "perusahaan": "Lihat di situs sumber",
                            "lokasi": kw if kw.lower() in ["makassar", "sulawesi selatan", "bandung", "jakarta", "jogja"] else f"Indonesia ({nama_label})",
                            "tanggal": str(p.get("date", "-"))[:10],
                            "link": sanitasi_link(p.get("link", ""))
                        })
            except Exception:
                continue


def fetch_rss_feeds(kata_kunci="", output_list=None):
    feeds = [
        ("Loker Makassar / Sulsel", "https://www.disnakerja.com/tag/makassar/feed/"),
        ("Loker Medis & Kesehatan", "https://www.disnakerja.com/kategori/kesehatan-medis/feed/"),
        ("Loker BUMN Terbaru", "https://www.disnakerja.com/kategori/bumn/feed/"),
        ("WeWorkRemotely Global", "https://weworkremotely.com/remote-jobs.rss"),
        ("Remotive Remote Feed", "https://remotive.com/remote-jobs/feed"),
        ("Jobspresso Remote WFH", "https://jobspresso.co/feed/?post_type=job_listing"),
        ("NodeDesk Remote Feeds", "https://nodesk.co/remote-jobs/index.xml")
    ]

    for label, url_rss in feeds:
        try:
            raw_xml = panggil_url(url_rss, timeout=5)
            # Proteksi XXE dan XML Entity Expansion (Billion Laughs)
            if "<!doctype" in raw_xml.lower() or "<!entity" in raw_xml.lower():
                raw_xml = re.sub(r'<!DOCTYPE[^>]*(\[[^\]]*\])?>', '', raw_xml, flags=re.IGNORECASE)
                raw_xml = re.sub(r'<!ENTITY[^>]*>', '', raw_xml, flags=re.IGNORECASE)

            clean_xml = re.sub(r'&(?!(?:amp|lt|gt|quot|apos);)', '&amp;', raw_xml)
            clean_xml = re.sub(r'&#(?!\d+;|x[0-9a-fA-F]+;)', '&amp;#', clean_xml)

            root = ET.fromstring(clean_xml)
            for item in root.findall(".//item")[:15]:
                judul = bersihkan_teks_html(item.findtext("title", default="-"))
                link = item.findtext("link", default="").strip()
                tanggal = item.findtext("pubDate", default="-").strip()

                if kata_kunci:
                    if kata_kunci.lower() not in judul.lower() and kata_kunci.lower() not in label.lower():
                        continue

                output_list.append({
                    "id": f"rss-{hash(link)}",
                    "sumber": "RSS Feed",
                    "kategori": label,
                    "posisi": judul,
                    "perusahaan": "Cek Detail Tautan",
                    "lokasi": "Indonesia / Remote",
                    "tanggal": tanggal[:16] if tanggal != "-" else "-",
                    "link": sanitasi_link(link)
                })
        except Exception:
            continue


def fetch_loker_id(kata_kunci="", output_list=None):
    targets = []
    if kata_kunci:
        targets.append((f"Loker.id ('{kata_kunci}')", f"https://www.loker.id/cari-lowongan-kerja?q={urllib.parse.quote(kata_kunci)}", "Indonesia"))
    else:
        targets.append(("Loker Wilayah Makassar", "https://www.loker.id/lokasi-pekerjaan/makassar", "Makassar, Sulsel"))
        targets.append(("Loker Administrasi", "https://www.loker.id/cari-lowongan-kerja?q=admin", "Indonesia (Admin)"))
        targets.append(("Loker Medis & Kesehatan", "https://www.loker.id/cari-lowongan-kerja?q=medis", "Indonesia (Medis)"))

    for kategori, url, lokasi_def in targets:
        try:
            html = panggil_html(url, timeout=6)
            articles = re.findall(r'<article[^>]*>(.*?)</article>', html, re.DOTALL)
            for art in articles[:15]:
                aria_m = re.search(r'aria-label=["\']Lihat detail pekerjaan (.*?)["\']', art)
                h3_m = re.search(r'<h3[^>]*>(.*?)</h3>', art, re.DOTALL)
                posisi = aria_m.group(1).strip() if aria_m else (bersihkan_teks_html(h3_m.group(1)) if h3_m else "-")

                link_m = re.search(r'href=["\'](/[^"\']*jobid=\d+[^"\']*)["\']', art)
                if not link_m:
                    link_m = re.search(r'href=["\'](/[^"\']+\.html)["\']', art)
                link = ("https://www.loker.id" + link_m.group(1).replace("&amp;", "&")) if link_m else url

                comp_m = re.search(r'<span class="text-sm text-secondary-600">([^<]+)</span>', art)
                if not comp_m:
                    comp_m = re.search(r'alt=["\']logo ([^"\']+)["\']', art)
                perusahaan = comp_m.group(1).strip() if comp_m else "Lihat di Loker.id"

                loc_m = re.search(r'class="icon-tabler-map-pin[^"]*".*?<span translate="no"[^>]*>([^<]+)</span>', art, re.DOTALL)
                lokasi = loc_m.group(1).strip() if loc_m else lokasi_def

                time_m = re.search(r'dateTime=["\']([^"\']+)["\']', art)
                tanggal = time_m.group(1)[:10] if time_m else datetime.now().strftime("%Y-%m-%d")

                output_list.append({
                    "id": f"lokerid-{hash(link)}",
                    "sumber": "Loker.id (Scrape)",
                    "kategori": kategori,
                    "posisi": bersihkan_teks_html(posisi),
                    "perusahaan": bersihkan_teks_html(perusahaan),
                    "lokasi": lokasi,
                    "tanggal": tanggal,
                    "link": sanitasi_link(link)
                })
        except Exception:
            continue


# ==============================================================================
# CACHE MANAGER THREAD-SAFE DENGAN TTL
# ==============================================================================
class JobCacheManager:
    """Mengelola cache in-memory untuk efisiensi serverless & performa tinggi."""
    def __init__(self, ttl_seconds=900): # 15 menit TTL
        self.ttl = ttl_seconds
        self.cache_pool = []
        self.last_updated = 0
        self.lock = threading.Lock()
        self.is_fetching = False

    def get_all_jobs(self, force_refresh=False):
        now = time.time()
        with self.lock:
            if not force_refresh and self.cache_pool and (now - self.last_updated < self.ttl):
                return list(self.cache_pool), self.last_updated

        # Ambil data baru secara paralel
        raw_results = []
        tasks = [
            lambda: fetch_jobicy("", raw_results),
            lambda: fetch_remotive("", raw_results),
            lambda: fetch_himalayas("", raw_results),
            lambda: fetch_working_nomads("", raw_results),
            lambda: fetch_arbeitnow("", raw_results),
            lambda: fetch_themuse("", raw_results),
            lambda: fetch_remoteok("", raw_results),
            lambda: fetch_kalibrr("", raw_results),
            lambda: fetch_greenhouse("", raw_results),
            lambda: fetch_wordpress_indo("", raw_results),
            lambda: fetch_rss_feeds("", raw_results),
            lambda: fetch_loker_id("", raw_results),
        ]

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(fn) for fn in tasks]
            for f in futures:
                try:
                    f.result()
                except Exception:
                    pass

        # Hapus duplikat berdasarkan link
        unique_map = {}
        for item in raw_results:
            lnk = item.get("link", "")
            if lnk and lnk != "#":
                unique_map[lnk] = item

        with self.lock:
            if unique_map:
                self.cache_pool = list(unique_map.values())
                self.last_updated = time.time()
            return list(self.cache_pool), self.last_updated

    def search_jobs(self, query=""):
        all_jobs, updated_at = self.get_all_jobs()
        if not query:
            return all_jobs, updated_at

        q = query.lower().strip()
        filtered = [
            j for j in all_jobs
            if q in j.get("posisi", "").lower()
            or q in j.get("perusahaan", "").lower()
            or q in j.get("lokasi", "").lower()
            or q in j.get("kategori", "").lower()
            or q in j.get("sumber", "").lower()
        ]
        return filtered, updated_at


# Inisialisasi instance tunggal (Singleton)
cache_manager = JobCacheManager(ttl_seconds=900)
