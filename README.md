# 💼 Lokeriva.vercel.app — Platform Agregator Lowongan Kerja Modern (Flask & Vercel)
> **Created by Xnuvers007**  
> 🌐 **Live Website**: [https://lokeriva.vercel.app/](https://lokeriva.vercel.app/) • **API Docs**: [https://lokeriva.vercel.app/docs](https://lokeriva.vercel.app/docs)

Website dan REST API agregasi lowongan kerja otomatis multi-sumber dari portal karir Indonesia (BUMN, Medis, Admin, Startup) serta lowongan remote WFH global terverifikasi.

Dilengkapi dengan antarmuka web modern, fitur ekspor PDF dengan **hyperlink aktif (dapat diklik langsung)**, proteksi keamanan tingkat tinggi, rate limiter yang bersahabat, dan konfigurasi siap deploy ke **Vercel**.

---

## 🚀 Fitur Utama

- **Antarmuka Modern & FontAwesome Icons**:
  - Tampilan elegan, responsif, dan bebas emoji dengan ikon **FontAwesome 6** profesional.
  - Dukungan tema Gelap / Terang (*Dark/Light Mode*).
  - Tampilan ganda: Mode Kartu (*Grid Cards*) & Mode Tabel (*Data Grid*).
  - Sistem Favorit / Bookmark tersimpan di peramban (`localStorage`).
- **Progressive Web App (PWA Ready)**:
  - Dapat dipasang (*Install*) langsung di Android, iOS, dan Desktop layaknya aplikasi native.
  - Dilengkapi *Service Worker* dan *Web App Manifest* untuk performa cepat dan kemampuan *offline shell caching*.
- **Penyaringan Berdasarkan Lokasi**:
  - Filter tipe lokasi: **Semua Lokasi**, **Khusus WFH / Remote (Bebas Lokasi)**, dan **Khusus Kantor (On-Site)**.
  - Pemilihan wilayah kota populer (Makassar & Sulsel, Jakarta, Bandung, Surabaya, Jogja, Bali, Medan, dll.).
  - Tombol **"Lokasi Saya"** untuk deteksi otomatis posisi pengguna via HTML5 Geolocation API.
- **Multi-Sumber Agregasi Otomatis**:
  - **7 Public JSON API Global**: Jobicy, Remotive, Himalayas, WorkingNomads, Arbeitnow, The Muse, RemoteOK.
  - **Kalibrr Indonesia Public API**: Ribuan lowongan startup & korporasi di Indonesia.
  - **8 Portal WordPress Karir Terverifikasi**: Disnakerja, LokerBUMN, BursaDepnaker, LokerJogja, LokerUtama, LokerBandung, LokerPintar, JakartaKerja.
  - **Open ATS Perusahaan**: Greenhouse (Xendit, Agoda, Kargo Technologies, Flip).
  - **Loker.id Web Scraper Modern**: Scraping real-time dengan bypass proteksi 403.
  - **RSS Feeds Volume Besar**: WeWorkRemotely, Remotive, NoDesk, Disnakerja RSS.
- **Ekspor PDF & CSV**:
  - File PDF berformat rapi A4 dengan **tautan/hyperlink aktif** (dapat diklik langsung untuk melamar).
  - File CSV dengan format UTF-8 BOM dan delimiter `;` untuk Microsoft Excel.
- **SEO & Search Engine Indexing (Google & Bing Ready)**:
  - File `robots.txt` profesional dan endpoint XML Sitemap otomatis di `/sitemap.xml`.
  - Schema.org Structured Data (JSON-LD) untuk Google Search Sitelinks & Knowledge Graph.
  - Lengkap dengan Open Graph (OG) & Twitter Cards untuk thumbnail preview di media sosial.
  - Meta tags ramah crawler: `robots`, `canonical`, `keywords`, `geo.region`, dan heading hierarki `<h1>`-`<h3>`.
- **Keamanan (Security First)**:
  - Header keamanan: `Content-Security-Policy (CSP)`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection`.
  - Sanitasi input dan proteksi SSRF (protokol link divalidasi ketat `http://` / `https://` saja).
  - Proteksi CSV Formula Injection (CWE-1236) dan ReportLab PDF XML Injection.
- **Rate Limiting**:
  - In-memory sliding window rate limiter: **120 req/menit** (Web & API), **30 req/menit** (PDF).
- **Siap Deploy ke Vercel**:
  - Dilengkapi `vercel.json`, `api/index.py`, `.vercelignore`, dan `requirements.txt`.

---

## 🛠️ Cara Menjalankan Secara Lokal

### 1. Prasyarat
Pastikan Python 3.9+ sudah terpasang.

### 2. Install Dependensi
```bash
pip install -r requirements.txt
```

### 3. Jalankan Aplikasi Flask
```bash
python app.py
```

Buka browser Anda di:
- **Web Portal**: [http://localhost:5000](http://localhost:5000)
- **Dokumentasi REST API**: [http://localhost:5000/docs](http://localhost:5000/docs)
- **REST API Endpoint**: [http://localhost:5000/api/jobs](http://localhost:5000/api/jobs)

---

## 🌐 Cara Deploy ke Vercel

Aplikasi ini sudah dikonfigurasi menggunakan standar Serverless WSGI Vercel Python.

### Metode 1: Menggunakan Vercel CLI
1. Pastikan Anda sudah menginstall Vercel CLI:
   ```bash
   npm i -g vercel
   ```
2. Di dalam folder `websiteAPILoker`, jalankan perintah:
   ```bash
   vercel
   ```
3. Ikuti panduan di terminal (tekan Enter untuk opsi default).
4. Untuk deploy ke production:
   ```bash
   vercel --prod
   ```

### Metode 2: Melalui Dashboard Web Vercel & GitHub
1. Buat repository baru di GitHub dan upload folder ini:
   ```bash
   git init
   git add .
   git commit -m "Initial commit portal loker flask"
   git remote add origin https://github.com/USERNAME/REPO-NAME.git
   git push -u origin main
   ```
2. Buka dashboard [Vercel](https://vercel.com).
3. Klik **"Add New"** > **"Project"** > Import repository GitHub Anda.
4. Vercel akan otomatis membaca file `vercel.json` dan `requirements.txt`.
5. Klik **"Deploy"**. Web Anda akan langsung aktif dengan domain `.vercel.app`!

---

## 📚 Ringkasan Endpoint REST API

| Method | Endpoint | Deskripsi |
| :--- | :--- | :--- |
| `GET` | `/api/jobs` | Mendapatkan data lowongan dengan parameter `q`, `source`, `category`, `location`, `sort`, `page`, `limit`. |
| `GET` | `/api/sources` | Daftar semua sumber lowongan aktif beserta jumlah datanya. |
| `GET` | `/api/stats` | Statistik jumlah loker, sumber, dan waktu pembaruan. |
| `GET` | `/export/pdf` | Unduh file PDF lowongan dengan hyperlink aktif. |
| `GET` | `/export/csv` | Unduh file CSV lowongan untuk Excel. |
| `POST` | `/api/refresh` | Memperbarui pool cache data dari seluruh sumber secara manual. |
| `GET` | `/docs` | Halaman dokumentasi API interaktif. |
| `GET` | `/api/openapi.json` | Spesifikasi OpenAPI 3.0 (bisa diimpor ke Swagger / Postman). |
| `GET` | `/robots.txt` | File crawler directives untuk bot mesin pencari (Google, Bing). |
| `GET` | `/sitemap.xml` | XML Sitemap resmi untuk Google Search Console. |

---

## 📄 Lisensi & Kredit
Created with ❤️ by **Xnuvers007** • Free and Open Source for community use.
