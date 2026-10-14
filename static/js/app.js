/**
 * Portal Loker - Frontend Reactive Application Logic with PWA & Location Filtering
 */

let state = {
  query: "",
  source: "",
  category: "",
  location: "",
  locationType: "all", // 'all' | 'remote' | 'onsite'
  sort: "newest",
  page: 1,
  limit: 20,
  view: "grid", // 'grid' | 'table'
  bookmarks: JSON.parse(localStorage.getItem("loker_bookmarks") || "[]"),
  filterMode: "all"
};

let deferredPrompt = null;

document.addEventListener("DOMContentLoaded", () => {
  initPWA();
  initOfflineDetection();
  initTheme();
  loadStats();
  loadSources();
  loadJobs();
  setupEventListeners();
});

// ==============================================================================
// 1. PWA REGISTRATION & INSTALL PROMPT BANNER
// ==============================================================================
function initPWA() {
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker
        .register("/sw.js")
        .then((reg) => {
          console.log("[PWA] Service Worker terdaftar dengan scope:", reg.scope);
        })
        .catch((err) => {
          console.log("[PWA] Pendaftaran Service Worker gagal:", err);
        });
    });
  }

  // Cek apakah sudah berjalan di mode standalone (sudah terpasang)
  const isStandalone = window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
  if (isStandalone) {
    return;
  }

  const shouldShowBanner = () => {
    const dismissedTime = localStorage.getItem("lokeriva_pwa_dismissed");
    if (!dismissedTime) return true;
    return Date.now() - parseInt(dismissedTime, 10) > 24 * 60 * 60 * 1000;
  };

  const dismissBanner = () => {
    const banner = document.getElementById("pwaInstallBanner");
    if (banner) banner.style.display = "none";
    localStorage.setItem("lokeriva_pwa_dismissed", Date.now().toString());
  };

  const triggerInstall = async () => {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      const { outcome } = await deferredPrompt.userChoice;
      if (outcome === "accepted") {
        showToast("Aplikasi Lokeriva.id berhasil dipasang!");
        dismissBanner();
      }
      deferredPrompt = null;
      const installBtn = document.getElementById("btnInstallPwa");
      if (installBtn) installBtn.style.display = "none";
    } else {
      showToast("Gunakan menu browser lalu pilih 'Tambahkan ke Layar Utama'");
    }
  };

  // Pasang listener tombol tutup & nanti
  const btnClose = document.getElementById("btnDismissPwa");
  if (btnClose) btnClose.addEventListener("click", dismissBanner);
  const btnLater = document.getElementById("btnDismissPwaLater");
  if (btnLater) btnLater.addEventListener("click", dismissBanner);
  const btnInstallBanner = document.getElementById("btnActionPwaInstall");
  if (btnInstallBanner) btnInstallBanner.addEventListener("click", triggerInstall);

  // Tombol di navbar
  const installBtn = document.getElementById("btnInstallPwa");
  if (installBtn) installBtn.addEventListener("click", triggerInstall);

  // Menangkap event sebelum prompt install PWA muncul (Android, Chrome, Edge)
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredPrompt = e;
    if (installBtn) installBtn.style.display = "flex";

    // Tampilkan banner mengambang dengan delay halus jika belum di-dismiss
    if (shouldShowBanner()) {
      setTimeout(() => {
        const banner = document.getElementById("pwaInstallBanner");
        if (banner) banner.style.display = "block";
      }, 1500);
    }
  });

  // Dukungan panduan khusus iOS Safari
  const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
  if (isIOS && shouldShowBanner()) {
    setTimeout(() => {
      const banner = document.getElementById("pwaInstallBanner");
      const title = document.getElementById("pwaBannerTitle");
      const desc = document.getElementById("pwaBannerDesc");
      const actionBtn = document.getElementById("btnActionPwaInstall");
      if (banner && desc) {
        banner.style.display = "block";
        if (title) title.innerText = "Pasang Lokeriva di iPhone/iPad";
        desc.innerHTML = "Ketuk ikon <b>Bagikan (Share)</b> <i class='fa-solid fa-arrow-up-from-bracket'></i> di Safari, lalu pilih <b>'Tambah ke Layar Utama'</b>.";
        if (actionBtn) {
          actionBtn.innerHTML = "<i class='fa-solid fa-check'></i> Saya Mengerti";
          actionBtn.onclick = dismissBanner;
        }
      }
    }, 2000);
  }

  window.addEventListener("appinstalled", () => {
    showToast("Aplikasi Lokeriva.id telah terpasang di perangkat Anda.");
    deferredPrompt = null;
    dismissBanner();
    if (installBtn) installBtn.style.display = "none";
  });
}

// ==============================================================================
// 1.1 DETEKSI JARINGAN OFFLINE & ONLINE
// ==============================================================================
function initOfflineDetection() {
  const statusBar = document.getElementById("offlineStatusBar");
  const updateOfflineUI = () => {
    if (!navigator.onLine) {
      if (statusBar) statusBar.style.display = "flex";
    } else {
      if (statusBar) statusBar.style.display = "none";
    }
  };

  window.addEventListener("online", () => {
    updateOfflineUI();
    showToast("Koneksi internet terhubung kembali! Memperbarui lowongan...");
    loadStats();
    loadJobs();
  });

  window.addEventListener("offline", () => {
    updateOfflineUI();
    showToast("Perangkat dalam Mode Offline. Menampilkan data tersimpan.");
  });

  updateOfflineUI();
}

// ==============================================================================
// 2. TEMA GELAP / TERANG (FONTAWESOME)
// ==============================================================================
function initTheme() {
  const savedTheme = localStorage.getItem("loker_theme") || "light";
  document.documentElement.setAttribute("data-theme", savedTheme);
  updateThemeIcon(savedTheme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "light";
  const next = current === "light" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("loker_theme", next);
  updateThemeIcon(next);
}

function updateThemeIcon(theme) {
  const btn = document.getElementById("themeToggleBtn");
  if (btn) {
    btn.innerHTML = theme === "dark" ? '<i class="fa-solid fa-sun"></i>' : '<i class="fa-solid fa-moon"></i>';
  }
}

function showToast(message) {
  const toast = document.getElementById("toast");
  const toastMsg = document.getElementById("toastMsg");
  if (!toast) return;
  if (toastMsg) toastMsg.innerText = message;
  toast.classList.add("show");
  setTimeout(() => {
    toast.classList.remove("show");
  }, 2800);
}

// ==============================================================================
// 3. EVENT LISTENERS & FILTER LOKASI
// ==============================================================================
function setupEventListeners() {
  // Search input debounce
  const searchInput = document.getElementById("searchInput");
  let debounceTimer;
  searchInput.addEventListener("input", (e) => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      state.query = e.target.value.trim();
      state.page = 1;
      updateExportLinks();
      loadJobs();
    }, 350);
  });

  // Source selector
  const sourceSelect = document.getElementById("sourceSelect");
  sourceSelect.addEventListener("change", (e) => {
    state.source = e.target.value;
    state.page = 1;
    updateExportLinks();
    loadJobs();
  });

  // Location Type selector (Remote vs On-Site vs All)
  const locationTypeSelect = document.getElementById("locationTypeSelect");
  locationTypeSelect.addEventListener("change", (e) => {
    state.locationType = e.target.value;
    state.page = 1;
    updateExportLinks();
    loadJobs();
  });

  // City selector (Wilayah / Kota)
  const citySelect = document.getElementById("citySelect");
  citySelect.addEventListener("change", (e) => {
    state.location = e.target.value;
    state.page = 1;
    updateExportLinks();
    loadJobs();
  });

  // Deteksi Lokasi GPS Saya
  const btnDetect = document.getElementById("btnDetectLocation");
  if (btnDetect) {
    btnDetect.addEventListener("click", detectUserLocation);
  }

  // Sort selector
  const sortSelect = document.getElementById("sortSelect");
  sortSelect.addEventListener("change", (e) => {
    state.sort = e.target.value;
    state.page = 1;
    loadJobs();
  });

  // Quick filter pills
  document.querySelectorAll(".pill-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".pill-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const filter = btn.dataset.filter;
      state.filterMode = filter;
      state.page = 1;

      if (filter === "all") {
        state.category = "";
        state.locationType = "all";
      } else if (filter === "remote") {
        state.category = "";
        state.locationType = "remote";
        if (locationTypeSelect) locationTypeSelect.value = "remote";
      } else if (filter === "medis") {
        state.category = "medis";
      } else if (filter === "admin") {
        state.category = "admin";
      } else if (filter === "bumn") {
        state.category = "bumn";
      } else if (filter === "tech") {
        state.category = "tech";
      } else if (filter === "bookmarks") {
        renderBookmarksView();
        return;
      }
      updateExportLinks();
      loadJobs();
    });
  });

  // View toggle
  document.getElementById("btnGridView").addEventListener("click", () => {
    state.view = "grid";
    document.getElementById("btnGridView").classList.add("active");
    document.getElementById("btnTableView").classList.remove("active");
    document.getElementById("jobsGrid").style.display = "grid";
    document.getElementById("jobsTableWrap").style.display = "none";
  });

  document.getElementById("btnTableView").addEventListener("click", () => {
    state.view = "table";
    document.getElementById("btnTableView").classList.add("active");
    document.getElementById("btnGridView").classList.remove("active");
    document.getElementById("jobsGrid").style.display = "none";
    document.getElementById("jobsTableWrap").style.display = "block";
  });

  // Theme toggle
  document.getElementById("themeToggleBtn").addEventListener("click", toggleTheme);
}

// ==============================================================================
// 4. DETEKSI LOKASI OTOMATIS (GEOLOCATION API)
// ==============================================================================
function detectUserLocation() {
  if (!navigator.geolocation) {
    showToast("Peramban Anda tidak mendukung deteksi lokasi.");
    return;
  }

  showToast("Mendeteksi lokasi Anda...");
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const lat = pos.coords.latitude;
      const lon = pos.coords.longitude;
      const kota = matchClosestIndonesianCity(lat, lon);
      
      state.location = kota;
      const citySelect = document.getElementById("citySelect");
      if (citySelect) {
        citySelect.value = kota;
      }
      state.page = 1;
      updateExportLinks();
      loadJobs();
      showToast(`Lokasi terdeteksi: ${kota}! Menyaring lowongan...`);
    },
    (err) => {
      console.warn("Geolocation gagal:", err);
      showToast("Izin lokasi tidak diberikan. Silakan pilih kota manual.");
    },
    { timeout: 7000 }
  );
}

function matchClosestIndonesianCity(lat, lon) {
  // Koordinat kota-kota besar di Indonesia
  const daftarKota = [
    { nama: "Makassar", lat: -5.1477, lon: 119.4327 },
    { nama: "Jakarta", lat: -6.2088, lon: 106.8456 },
    { nama: "Bandung", lat: -6.9175, lon: 107.6191 },
    { nama: "Surabaya", lat: -7.2575, lon: 112.7521 },
    { nama: "Jogja", lat: -7.7956, lon: 110.3695 },
    { nama: "Bali", lat: -8.6705, lon: 115.2126 },
    { nama: "Medan", lat: 3.5952, lon: 98.6722 },
    { nama: "Semarang", lat: -6.9667, lon: 110.4167 }
  ];

  let terdekat = "Makassar";
  let minJarak = Infinity;

  daftarKota.forEach((k) => {
    const d = Math.hypot(lat - k.lat, lon - k.lon);
    if (d < minJarak) {
      minJarak = d;
      terdekat = k.nama;
    }
  });

  return terdekat;
}

function updateExportLinks() {
  const pdfBtn = document.getElementById("btnExportPdf");
  const csvBtn = document.getElementById("btnExportCsv");
  const params = new URLSearchParams();
  if (state.query) params.set("q", state.query);
  if (state.source) params.set("source", state.source);
  if (state.location) params.set("location", state.location);
  if (state.locationType && state.locationType !== "all") params.set("location_type", state.locationType);

  const queryStr = params.toString() ? `?${params.toString()}` : "";
  if (pdfBtn) pdfBtn.href = `/export/pdf${queryStr}`;
  if (csvBtn) csvBtn.href = `/export/csv${queryStr}`;
}

async function loadStats() {
  try {
    const res = await fetch("/api/stats");
    const data = await res.json();
    if (data.status === "success") {
      document.getElementById("statTotalJobs").innerText = data.stats.total_jobs.toLocaleString();
      document.getElementById("statActiveSources").innerText = data.stats.active_sources;
      document.getElementById("statRemoteJobs").innerText = data.stats.remote_jobs.toLocaleString();
      document.getElementById("statLocalJobs").innerText = data.stats.local_indo_jobs.toLocaleString();
      document.getElementById("lastUpdatedText").innerHTML = `<i class="fa-solid fa-clock-rotate-left"></i> Pembaruan data: ${escapeHtml(data.stats.last_updated)}`;
      try {
        localStorage.setItem("lokeriva_cached_stats", JSON.stringify(data.stats));
      } catch (e) {}
    }
  } catch (err) {
    console.warn("Gagal memuat stats online, memuat cache offline...", err);
    const saved = localStorage.getItem("lokeriva_cached_stats");
    if (saved) {
      try {
        const stats = JSON.parse(saved);
        document.getElementById("statTotalJobs").innerText = stats.total_jobs.toLocaleString();
        document.getElementById("statActiveSources").innerText = stats.active_sources;
        document.getElementById("statRemoteJobs").innerText = stats.remote_jobs.toLocaleString();
        document.getElementById("statLocalJobs").innerText = stats.local_indo_jobs.toLocaleString();
        document.getElementById("lastUpdatedText").innerHTML = `<i class="fa-solid fa-clock-rotate-left"></i> Data tersimpan offline: ${escapeHtml(stats.last_updated)}`;
      } catch (e) {}
    }
  }
}

async function loadSources() {
  try {
    const res = await fetch("/api/sources");
    const data = await res.json();
    if (data.status === "success") {
      const select = document.getElementById("sourceSelect");
      // Simpan pilihan pertama
      select.innerHTML = '<option value="">Semua Sumber Karir</option>';
      data.sources.forEach((s) => {
        const opt = document.createElement("option");
        opt.value = s.name;
        opt.innerText = `${s.name} (${s.count})`;
        select.appendChild(opt);
      });
      try {
        localStorage.setItem("lokeriva_cached_sources", JSON.stringify(data.sources));
      } catch (e) {}
    }
  } catch (err) {
    console.warn("Gagal memuat sources online, memuat cache offline...", err);
    const saved = localStorage.getItem("lokeriva_cached_sources");
    if (saved) {
      try {
        const sources = JSON.parse(saved);
        const select = document.getElementById("sourceSelect");
        select.innerHTML = '<option value="">Semua Sumber Karir</option>';
        sources.forEach((s) => {
          const opt = document.createElement("option");
          opt.value = s.name;
          opt.innerText = `${s.name} (${s.count})`;
          select.appendChild(opt);
        });
      } catch (e) {}
    }
  }
}

async function loadJobs() {
  showSkeletons();
  try {
    const params = new URLSearchParams({
      q: state.query,
      source: state.source,
      category: state.category,
      location: state.location,
      location_type: state.locationType,
      sort: state.sort,
      page: state.page,
      limit: state.limit
    });

    const res = await fetch(`/api/jobs?${params.toString()}`);
    const result = await res.json();

    if (result.status === "success" && result.data) {
      // Simpan data pencarian default ke cache lokal perangkat
      if (!state.query && !state.source && !state.location && state.page === 1) {
        try {
          localStorage.setItem("lokeriva_cached_jobs", JSON.stringify(result));
        } catch (e) {}
      }

      renderJobs(result.data);
      renderPagination(result.pagination);
      
      let infoLokasi = "";
      if (state.locationType === "remote") infoLokasi = " • Mode WFH Remote";
      if (state.locationType === "onsite") infoLokasi = " • Mode On-Site Kantor";
      if (state.location) infoLokasi += ` • Wilayah: ${escapeHtml(state.location)}`;
      if (!navigator.onLine || result.is_offline) {
        infoLokasi += " • <span style='color: #ea580c; font-weight: 600;'><i class='fa-solid fa-plane'></i> Mode Offline (Data Tersimpan)</span>";
      }

      document.getElementById("resultsInfoText").innerHTML = 
        `<i class="fa-solid fa-briefcase"></i> Menampilkan <b>${Number(result.data.length)}</b> dari total <b>${Number(result.pagination.total_items)}</b> lowongan kerja${infoLokasi}`;
    } else {
      handleOfflineJobsFallback();
    }
  } catch (err) {
    console.warn("Gagal memuat lowongan online, mengaktifkan penanganan offline:", err);
    handleOfflineJobsFallback();
  }
}

function handleOfflineJobsFallback() {
  // Coba tampilkan data tersimpan di localStorage jika ada
  const cachedDataStr = localStorage.getItem("lokeriva_cached_jobs");
  if (cachedDataStr) {
    try {
      const cachedObj = JSON.parse(cachedDataStr);
      if (cachedObj.data && cachedObj.data.length > 0) {
        renderJobs(cachedObj.data);
        renderPagination(cachedObj.pagination);
        document.getElementById("resultsInfoText").innerHTML = 
          `<i class="fa-solid fa-plane" style="color: #ea580c;"></i> <b>Mode Offline:</b> Menampilkan <b>${Number(cachedObj.data.length)}</b> lowongan yang tersimpan di memori perangkat Anda`;
        return;
      }
    } catch (e) {}
  }

  // Jika belum ada data lowongan tersimpan sama sekali, tampilkan kartu ramah offline dengan opsi ke Favorit
  document.getElementById("jobsGrid").innerHTML = `
    <div style="grid-column: 1/-1; text-align: center; padding: 50px 20px;">
      <div style="font-size: 2.5rem; color: #ea580c; margin-bottom: 12px;"><i class="fa-solid fa-plane"></i></div>
      <h3 style="font-size: 1.25rem; font-weight: 700; margin-bottom: 8px;">Aplikasi Lokeriva Terbuka Offline</h3>
      <p style="color: var(--text-muted); font-size: 0.92rem; max-width: 480px; margin: 0 auto 20px auto; line-height: 1.6;">
        Anda dapat menggunakan Lokeriva langsung dari layar utama perangkat. Untuk filter ini data belum tersimpan, namun lowongan yang Anda tandai bintang selalu tersedia di <b>Favorit Saya</b>.
      </p>
      <button class="pill-btn active" id="btnGoOfflineBookmarks" style="display: inline-flex; margin: 0 auto;">
        <i class="fa-solid fa-star"></i> Buka Lowongan Favorit Saya (${state.bookmarks.length})
      </button>
    </div>`;

  const btnBm = document.getElementById("btnGoOfflineBookmarks");
  if (btnBm) {
    btnBm.addEventListener("click", () => {
      document.querySelectorAll(".pill-btn").forEach((p) => p.classList.remove("active"));
      const bmPill = document.querySelector('[data-filter="bookmarks"]');
      if (bmPill) bmPill.classList.add("active");
      state.filterMode = "bookmarks";
      renderBookmarksView();
    });
  }
  document.getElementById("resultsInfoText").innerHTML = `<i class="fa-solid fa-plane" style="color: #ea580c;"></i> Mode Offline: Membuka data tersimpan`;
}

function showSkeletons() {
  const grid = document.getElementById("jobsGrid");
  grid.innerHTML = "";
  for (let i = 0; i < 6; i++) {
    const sk = document.createElement("div");
    sk.className = "skeleton-card";
    grid.appendChild(sk);
  }
}

function sanitizeUrl(url) {
  if (!url || typeof url !== "string") return "#";
  const trimmed = url.trim();
  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      return escapeHtml(parsed.href);
    }
  } catch (e) {
    if (/^https?:\/\/[a-zA-Z0-9\-._~:/?#[\]@!$&'()*+,;=%]+$/i.test(trimmed)) {
      return escapeHtml(encodeURI(trimmed));
    }
  }
  return "#";
}

function renderJobs(jobs) {
  const grid = document.getElementById("jobsGrid");
  const tableBody = document.getElementById("tableBody");
  grid.innerHTML = "";
  tableBody.innerHTML = "";

  if (!jobs || jobs.length === 0) {
    const emptyMsg = `
      <div style="grid-column: 1/-1; text-align: center; padding: 50px 20px;">
        <div style="font-size: 2.2rem; color: var(--text-subtle); margin-bottom: 10px;"><i class="fa-solid fa-magnifying-glass"></i></div>
        <h3 style="font-size: 1.15rem; font-weight: 700; margin-bottom: 6px;">Tidak ada lowongan yang cocok</h3>
        <p style="color: var(--text-muted); font-size: 0.9rem;">Coba gunakan kata kunci lain, pilih kota yang lebih luas, atau ganti tipe lokasi.</p>
      </div>`;
    grid.innerHTML = emptyMsg;
    tableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 30px;">Tidak ada lowongan yang ditemukan.</td></tr>`;
    return;
  }

  jobs.forEach((job, index) => {
    const isBookmarked = state.bookmarks.some((b) => b.link === job.link);
    const initial = (job.perusahaan || "L").charAt(0).toUpperCase();
    const safeLink = sanitizeUrl(job.link);

    // Render Grid Card
    const card = document.createElement("div");
    card.className = "job-card";
    card.innerHTML = `
      <div class="job-header">
        <div class="company-avatar">${escapeHtml(initial)}</div>
        <div class="job-title-group">
          <h3 class="job-title">${escapeHtml(job.posisi)}</h3>
          <div class="company-name"><i class="fa-regular fa-building"></i> ${escapeHtml(job.perusahaan)}</div>
        </div>
      </div>
      <div class="job-badges">
        <span class="badge badge-source"><i class="fa-solid fa-circle-check"></i> ${escapeHtml(job.sumber)}</span>
        <span class="badge badge-cat">${escapeHtml(job.kategori)}</span>
        <span class="badge badge-loc"><i class="fa-solid fa-location-dot"></i> ${escapeHtml(job.lokasi)}</span>
      </div>
      <div class="job-footer">
        <span class="job-date"><i class="fa-regular fa-calendar-days"></i> ${escapeHtml(job.tanggal)}</span>
        <div class="job-actions">
          <button class="btn-bookmark ${isBookmarked ? "active" : ""}" title="Simpan ke Favorit">
            <i class="${isBookmarked ? "fa-solid fa-star" : "fa-regular fa-star"}"></i>
          </button>
          <button class="btn-icon btn-copy-link" style="width: 32px; height: 32px;" title="Salin Tautan">
            <i class="fa-solid fa-share-nodes"></i>
          </button>
          <a href="${safeLink}" target="_blank" rel="noopener noreferrer" class="btn-apply">
            Lamar <i class="fa-solid fa-arrow-up-right-from-square"></i>
          </a>
        </div>
      </div>
    `;

    // Pasang Event Listener Aman (Bebas Inline String Injection)
    const btnBookmark = card.querySelector(".btn-bookmark");
    if (btnBookmark) {
      btnBookmark.addEventListener("click", () => toggleBookmark(job));
    }

    const btnCopy = card.querySelector(".btn-copy-link");
    if (btnCopy) {
      btnCopy.addEventListener("click", () => copyLink(safeLink));
    }

    grid.appendChild(card);

    // Render Table Row
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${(state.page - 1) * state.limit + index + 1}</td>
      <td><b>${escapeHtml(job.posisi)}</b></td>
      <td>${escapeHtml(job.perusahaan)}</td>
      <td><span class="badge badge-source">${escapeHtml(job.sumber)}</span></td>
      <td><i class="fa-solid fa-location-dot" style="color: var(--accent);"></i> ${escapeHtml(job.lokasi)}</td>
      <td>
        <a href="${safeLink}" target="_blank" rel="noopener noreferrer" class="btn-apply" style="padding: 4px 10px; font-size: 0.75rem;">
          Lamar <i class="fa-solid fa-arrow-up-right-from-square"></i>
        </a>
      </td>
    `;
    tableBody.appendChild(tr);
  });
}

function renderPagination(pg) {
  const container = document.getElementById("pagination");
  container.innerHTML = "";
  if (pg.total_pages <= 1) return;

  // Tombol Prev
  const prevBtn = document.createElement("button");
  prevBtn.className = "page-btn";
  prevBtn.innerHTML = '<i class="fa-solid fa-chevron-left"></i> Sebelumnya';
  prevBtn.disabled = !pg.has_prev;
  prevBtn.addEventListener("click", () => {
    if (state.page > 1) {
      state.page--;
      loadJobs();
      window.scrollTo({ top: 380, behavior: "smooth" });
    }
  });
  container.appendChild(prevBtn);

  // Nomor halaman
  const startPage = Math.max(1, pg.current_page - 2);
  const endPage = Math.min(pg.total_pages, pg.current_page + 2);

  for (let i = startPage; i <= endPage; i++) {
    const numBtn = document.createElement("button");
    numBtn.className = `page-btn ${i === pg.current_page ? "active" : ""}`;
    numBtn.innerText = i;
    numBtn.addEventListener("click", () => {
      state.page = i;
      loadJobs();
      window.scrollTo({ top: 380, behavior: "smooth" });
    });
    container.appendChild(numBtn);
  }

  // Tombol Next
  const nextBtn = document.createElement("button");
  nextBtn.className = "page-btn";
  nextBtn.innerHTML = 'Selanjutnya <i class="fa-solid fa-chevron-right"></i>';
  nextBtn.disabled = !pg.has_next;
  nextBtn.addEventListener("click", () => {
    if (state.page < pg.total_pages) {
      state.page++;
      loadJobs();
      window.scrollTo({ top: 380, behavior: "smooth" });
    }
  });
  container.appendChild(nextBtn);
}

function toggleBookmark(job) {
  try {
    if (!job || !job.link) return;
    const idx = state.bookmarks.findIndex((b) => b.link === job.link);
    if (idx > -1) {
      state.bookmarks.splice(idx, 1);
      showToast("Lowongan dihapus dari daftar favorit.");
    } else {
      state.bookmarks.push(job);
      showToast("Lowongan berhasil disimpan ke favorit!");
    }
    localStorage.setItem("loker_bookmarks", JSON.stringify(state.bookmarks));

    if (state.filterMode === "bookmarks") {
      renderBookmarksView();
    } else {
      loadJobs();
    }
  } catch (e) {
    console.error("Gagal simpan bookmark:", e);
  }
}

function renderBookmarksView() {
  renderJobs(state.bookmarks);
  document.getElementById("pagination").innerHTML = "";
  document.getElementById("resultsInfoText").innerHTML = `<i class="fa-solid fa-star" style="color: #f59e0b;"></i> Menampilkan <b>${state.bookmarks.length}</b> lowongan tersimpan di favorit`;
}

function copyLink(link) {
  if (navigator.clipboard && link) {
    navigator.clipboard.writeText(link).then(() => {
      showToast("Tautan lowongan berhasil disalin!");
    }).catch(() => {
      showToast("Gagal menyalin tautan.");
    });
  }
}

function escapeHtml(str) {
  if (!str) return "-";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeAttr(str) {
  if (!str) return "";
  return String(str)
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
