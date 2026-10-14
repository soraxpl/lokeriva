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
  initLiveClock();
  initCoverLetterGenerator();
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
        showToast("Aplikasi Lokeriva.vercel.app berhasil dipasang!");
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
    showToast("Aplikasi Lokeriva.vercel.app telah terpasang di perangkat Anda.");
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

  // Social Share Modal Event Listeners
  const btnCloseModal = document.getElementById("btnCloseShareModal");
  if (btnCloseModal) btnCloseModal.addEventListener("click", closeShareModal);

  const shareModal = document.getElementById("shareModal");
  if (shareModal) {
    shareModal.addEventListener("click", (e) => {
      if (e.target === shareModal) closeShareModal();
    });
  }

  const btnNativeShare = document.getElementById("shareNativeBtn");
  if (btnNativeShare) btnNativeShare.addEventListener("click", triggerNativeShare);

  const btnCopyShare = document.getElementById("btnCopyShareUrl");
  if (btnCopyShare) btnCopyShare.addEventListener("click", copyShareUrl);

  // Donation Modal Event Listeners
  const btnOpenDonate = document.getElementById("btnOpenDonateModal");
  if (btnOpenDonate) btnOpenDonate.addEventListener("click", openDonateModal);

  const btnFooterDonate = document.getElementById("btnFooterDonate");
  if (btnFooterDonate) btnFooterDonate.addEventListener("click", openDonateModal);

  const btnCloseDonate = document.getElementById("btnCloseDonateModal");
  if (btnCloseDonate) btnCloseDonate.addEventListener("click", closeDonateModal);

  const donateModal = document.getElementById("donateModal");
  if (donateModal) {
    donateModal.addEventListener("click", (e) => {
      if (e.target === donateModal) closeDonateModal();
    });
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeShareModal();
      closeDonateModal();
    }
  });
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
          <button class="btn-letter-card" title="Buat Surat Lamaran / Email Kerja">
            <i class="fa-solid fa-file-signature"></i>
          </button>
          <button class="btn-bookmark ${isBookmarked ? "active" : ""}" title="Simpan ke Favorit">
            <i class="${isBookmarked ? "fa-solid fa-star" : "fa-regular fa-star"}"></i>
          </button>
          <button class="btn-share-wa" title="Bagikan ke WhatsApp">
            <i class="fa-brands fa-whatsapp"></i>
          </button>
          <button class="btn-share-more" title="Bagikan ke Media Sosial Lainnya">
            <i class="fa-solid fa-share-nodes"></i>
          </button>
          <a href="${safeLink}" target="_blank" rel="noopener noreferrer" class="btn-apply">
            Lamar <i class="fa-solid fa-arrow-up-right-from-square"></i>
          </a>
        </div>
      </div>
    `;

    // Pasang Event Listener Aman (Bebas Inline String Injection)
    const btnLetter = card.querySelector(".btn-letter-card");
    if (btnLetter) {
      btnLetter.addEventListener("click", (e) => {
        e.stopPropagation();
        openCoverLetterGenerator(job.posisi, job.perusahaan);
      });
    }

    const btnBookmark = card.querySelector(".btn-bookmark");
    if (btnBookmark) {
      btnBookmark.addEventListener("click", () => toggleBookmark(job));
    }

    const btnShareWa = card.querySelector(".btn-share-wa");
    if (btnShareWa) {
      btnShareWa.addEventListener("click", (e) => {
        e.stopPropagation();
        shareToWhatsApp(job);
      });
    }

    const btnShareMore = card.querySelector(".btn-share-more");
    if (btnShareMore) {
      btnShareMore.addEventListener("click", (e) => {
        e.stopPropagation();
        openShareModal(job);
      });
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
      <td class="table-actions-cell">
        <div class="table-actions-group">
          <button class="btn-letter-table" title="Buat Surat Lamaran / Email">
            <i class="fa-solid fa-file-signature"></i>
          </button>
          <button class="btn-share-wa btn-share-wa-table" title="Bagikan ke WhatsApp">
            <i class="fa-brands fa-whatsapp"></i>
          </button>
          <button class="btn-share-more btn-share-more-table" title="Bagikan ke Media Sosial">
            <i class="fa-solid fa-share-nodes"></i>
          </button>
          <a href="${safeLink}" target="_blank" rel="noopener noreferrer" class="btn-apply btn-apply-table">
            <span>Lamar</span> <i class="fa-solid fa-arrow-up-right-from-square"></i>
          </a>
        </div>
      </td>
    `;

    const trLetter = tr.querySelector(".btn-letter-table");
    if (trLetter) {
      trLetter.addEventListener("click", () => openCoverLetterGenerator(job.posisi, job.perusahaan));
    }
    const trWa = tr.querySelector(".btn-share-wa-table");
    if (trWa) {
      trWa.addEventListener("click", () => shareToWhatsApp(job));
    }
    const trMore = tr.querySelector(".btn-share-more-table");
    if (trMore) {
      trMore.addEventListener("click", () => openShareModal(job));
    }

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

// ==============================================================================
// 7. FITUR SOCIAL SHARE (WHATSAPP, FACEBOOK, MESSENGER, TELEGRAM, LINKEDIN, SMS, INSTAGRAM)
// ==============================================================================
let currentShareJob = null;

function buildJobShareMessage(job) {
  const title = job.posisi || "Lowongan Kerja";
  const company = job.perusahaan || "Perusahaan";
  const link = job.link && job.link !== "#" ? job.link : "https://lokeriva.vercel.app/";
  return `Halo! Cek lowongan ${title} di ${company} ini: ${link}\n\nLihat info karir lainnya di Lokeriva: https://lokeriva.vercel.app/`;
}

function shareToWhatsApp(job) {
  if (!job) return;
  const msg = buildJobShareMessage(job);
  const waUrl = `https://api.whatsapp.com/send?text=${encodeURIComponent(msg)}`;
  window.open(waUrl, "_blank", "noopener,noreferrer");
}

function openShareModal(job) {
  if (!job) return;
  currentShareJob = job;
  const title = job.posisi || "Lowongan Kerja";
  const company = job.perusahaan || "Lokeriva.vercel.app";
  const msg = buildJobShareMessage(job);
  const link = job.link && job.link !== "#" ? job.link : "https://lokeriva.vercel.app/";

  const modal = document.getElementById("shareModal");
  const titleEl = document.getElementById("shareJobTitle");
  const companyEl = document.getElementById("shareJobCompany");
  const msgEl = document.getElementById("shareMessagePreview");
  const urlInput = document.getElementById("shareUrlInput");

  if (titleEl) titleEl.innerText = title;
  if (companyEl) companyEl.innerText = company;
  if (msgEl) msgEl.innerText = msg;
  if (urlInput) urlInput.value = link;

  // 1. WhatsApp
  const shareWa = document.getElementById("shareWaBtn");
  if (shareWa) shareWa.href = `https://api.whatsapp.com/send?text=${encodeURIComponent(msg)}`;

  // 2. Facebook
  const shareFb = document.getElementById("shareFbBtn");
  if (shareFb) shareFb.href = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(link)}&quote=${encodeURIComponent(msg)}`;

  // 3. Messenger
  const shareMsgr = document.getElementById("shareMessengerBtn");
  if (shareMsgr) {
    shareMsgr.href = `https://www.facebook.com/dialog/send?link=${encodeURIComponent(link)}&app_id=291494419107518&redirect_uri=${encodeURIComponent("https://lokeriva.vercel.app/")}`;
    shareMsgr.onclick = (e) => {
      if (/Android|iPhone|iPad/i.test(navigator.userAgent)) {
        window.location.href = `fb-messenger://share/?link=${encodeURIComponent(link)}`;
        e.preventDefault();
      }
    };
  }

  // 4. Telegram
  const shareTg = document.getElementById("shareTgBtn");
  if (shareTg) shareTg.href = `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(msg)}`;

  // 5. LinkedIn
  const shareLi = document.getElementById("shareLiBtn");
  if (shareLi) shareLi.href = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(link)}`;

  // 6. SMS
  const shareSms = document.getElementById("shareSmsBtn");
  if (shareSms) shareSms.href = `sms:?body=${encodeURIComponent(msg)}`;

  if (modal) {
    modal.style.display = "flex";
    modal.setAttribute("aria-hidden", "false");
  }
}

function closeShareModal() {
  const modal = document.getElementById("shareModal");
  if (modal) {
    modal.style.display = "none";
    modal.setAttribute("aria-hidden", "true");
  }
  currentShareJob = null;
}

function triggerNativeShare() {
  if (!currentShareJob) return;
  const title = currentShareJob.posisi || "Lowongan Kerja";
  const msg = buildJobShareMessage(currentShareJob);
  const link = currentShareJob.link || "https://lokeriva.vercel.app/";

  if (navigator.share) {
    navigator.share({
      title: `${title} - Lokeriva`,
      text: msg,
      url: link
    }).catch((err) => {
      if (err.name !== "AbortError") {
        copyLink(link);
      }
    });
  } else {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(msg).then(() => {
        showToast("Teks lowongan disalin! Silakan tempel (paste) ke Instagram DM / Story atau aplikasi lain.");
      }).catch(() => {
        copyLink(link);
      });
    } else {
      copyLink(link);
    }
  }
}

function copyShareUrl() {
  const urlInput = document.getElementById("shareUrlInput");
  if (urlInput && urlInput.value) {
    copyLink(urlInput.value);
  }
}

// ==============================================================================
// 8. JAM DIGITAL REAL-TIME (WIB / JAKARTA)
// ==============================================================================
function initLiveClock() {
  const clockEl = document.getElementById("footerClock");
  if (!clockEl) return;

  const updateClock = () => {
    try {
      const now = new Date();
      const timeStr = new Intl.DateTimeFormat("id-ID", {
        timeZone: "Asia/Jakarta",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false
      }).format(now);
      clockEl.innerText = `${timeStr} WIB`;
    } catch (e) {
      const now = new Date();
      const pad = (n) => String(n).padStart(2, "0");
      clockEl.innerText = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())} WIB`;
    }
  };

  updateClock();
  setInterval(updateClock, 1000);
}

// ==============================================================================
// 9. MODAL DUKUNGAN / DONASI DEVELOPER
// ==============================================================================
function openDonateModal() {
  const modal = document.getElementById("donateModal");
  if (modal) {
    modal.style.display = "flex";
    modal.setAttribute("aria-hidden", "false");
  }
}

function closeDonateModal() {
  const modal = document.getElementById("donateModal");
  if (modal) {
    modal.style.display = "none";
    modal.setAttribute("aria-hidden", "true");
  }
}

// ==============================================================================
// 10. GENERATOR SURAT LAMARAN & COLD EMAIL BUILDER (CUSTOMIZABLE)
// ==============================================================================
let currentLetterTab = "cold_email";
let isCustomizedManually = false;

const DEFAULT_CUSTOM_TEMPLATE = `Kepada Yth. {penerima}
{perusahaan}
di {kota}

Dengan hormat,

Perkenalkan, nama saya {nama}, berdomisili di {kota} dan merupakan lulusan dari {pendidikan}. Melalui surat ini, saya bermaksud untuk mengajukan lamaran pekerjaan untuk posisi {posisi} di {perusahaan} sebagaimana informasi yang saya temukan di portal Lokeriva.

Saya memiliki keahlian utama dalam {skills}. {pencapaian}

Saya sangat antusias untuk bergabung dan membawa kontribusi nyata dalam mencapai visi dan target {perusahaan}. Saya siap untuk mendiskusikan lebih lanjut kualifikasi saya dalam sesi wawancara.

Atas perhatian dan kesempatan yang Bapak/Ibu berikan, saya ucapkan terima kasih yang sebesar-besarnya.

Hormat saya,

{nama}
WhatsApp : {telepon}
Email    : {email}`;

function initCoverLetterGenerator() {
  // Muat data pelamar yang tersimpan di localStorage
  const savedName = localStorage.getItem("lokeriva_cl_name") || "";
  const savedEmail = localStorage.getItem("lokeriva_cl_email") || "";
  const savedPhone = localStorage.getItem("lokeriva_cl_phone") || "";
  const savedCity = localStorage.getItem("lokeriva_cl_city") || "";
  const savedEdu = localStorage.getItem("lokeriva_cl_edu") || "";
  const savedSkills = localStorage.getItem("lokeriva_cl_skills") || "";
  const savedExp = localStorage.getItem("lokeriva_cl_exp") || "fresh";
  const savedRecipient = localStorage.getItem("lokeriva_cl_recipient") || "";
  const savedTone = localStorage.getItem("lokeriva_cl_tone") || "formal";
  const savedAchievements = localStorage.getItem("lokeriva_cl_achievements") || "";

  const nameInput = document.getElementById("clApplicantName");
  const emailInput = document.getElementById("clApplicantEmail");
  const phoneInput = document.getElementById("clApplicantPhone");
  const cityInput = document.getElementById("clApplicantCity");
  const eduInput = document.getElementById("clApplicantEdu");
  const skillsInput = document.getElementById("clSkills");
  const expSelect = document.getElementById("clExperienceLevel");
  const recipientInput = document.getElementById("clRecipientName");
  const toneSelect = document.getElementById("clTone");
  const achInput = document.getElementById("clAchievements");

  if (nameInput && savedName) nameInput.value = savedName;
  if (emailInput && savedEmail) emailInput.value = savedEmail;
  if (phoneInput && savedPhone) phoneInput.value = savedPhone;
  if (cityInput && savedCity) cityInput.value = savedCity;
  if (eduInput && savedEdu) eduInput.value = savedEdu;
  if (skillsInput && savedSkills) skillsInput.value = savedSkills;
  if (expSelect && savedExp) expSelect.value = savedExp;
  if (recipientInput && savedRecipient) recipientInput.value = savedRecipient;
  if (toneSelect && savedTone) toneSelect.value = savedTone;
  if (achInput && savedAchievements) achInput.value = savedAchievements;

  // Real-time update listeners saat mengetik di input form
  const allInputs = [
    "clApplicantName",
    "clApplicantEmail",
    "clApplicantPhone",
    "clApplicantCity",
    "clApplicantEdu",
    "clJobPosition",
    "clJobCompany",
    "clRecipientName",
    "clSkills",
    "clAchievements",
    "clExperienceLevel",
    "clTone"
  ];

  allInputs.forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener("input", () => {
        saveApplicantData();
        if (!isCustomizedManually || currentLetterTab === "custom_template") {
          updateCoverLetterPreview();
        }
      });
      el.addEventListener("change", () => {
        saveApplicantData();
        if (!isCustomizedManually || currentLetterTab === "custom_template") {
          updateCoverLetterPreview();
        }
      });
    }
  });

  // Listener untuk Textarea Preview (Pengguna bebas mengetik / mengedit langsung)
  const outputText = document.getElementById("clOutputText");
  if (outputText) {
    outputText.addEventListener("input", () => {
      isCustomizedManually = true;
      updateMailtoLink();
    });
  }

  // Listener untuk Subjek Email jika diedit manual
  const subjectInput = document.getElementById("clSubjectInput");
  if (subjectInput) {
    subjectInput.addEventListener("input", () => {
      updateMailtoLink();
    });
  }

  // Tombol Reset Teks / Generate Ulang ke default template
  const btnRegen = document.getElementById("btnRegenerateLetter");
  if (btnRegen) {
    btnRegen.addEventListener("click", () => {
      isCustomizedManually = false;
      updateCoverLetterPreview();
      showToast("Teks surat di-generate ulang dari form.");
    });
  }

  // Tab switching (Cold Email vs Surat Formal ID vs Cover Letter EN vs Kustom Bebas)
  document.querySelectorAll(".letter-tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".letter-tab-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentLetterTab = btn.dataset.tab;
      isCustomizedManually = false;

      // Tampilkan helper variabel jika di tab Kustom Bebas
      const helper = document.getElementById("clCustomTemplateHelper");
      if (helper) {
        helper.style.display = currentLetterTab === "custom_template" ? "block" : "none";
      }

      updateCoverLetterPreview();
    });
  });

  // Chip variabel untuk memasukkan placeholder ke textarea saat di tab Kustom Bebas
  document.querySelectorAll(".tag-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const tag = chip.dataset.tag;
      if (!tag) return;
      insertTagIntoTextarea(tag);
    });
  });

  // Tombol Simpan Template Kustom Saya
  const btnSaveCustom = document.getElementById("btnSaveCustomTemplate");
  if (btnSaveCustom) {
    btnSaveCustom.addEventListener("click", () => {
      const text = document.getElementById("clOutputText")?.value || "";
      if (!text.trim()) {
        showToast("Teks template masih kosong.");
        return;
      }
      localStorage.setItem("lokeriva_cl_custom_template", text);
      showToast("Template kustom Anda berhasil disimpan!");
    });
  }

  // Tombol Muat Contoh Template Kustom
  const btnLoadCustom = document.getElementById("btnLoadDefaultCustomTemplate");
  if (btnLoadCustom) {
    btnLoadCustom.addEventListener("click", () => {
      const output = document.getElementById("clOutputText");
      if (output) {
        output.value = DEFAULT_CUSTOM_TEMPLATE;
        isCustomizedManually = true;
        updateMailtoLink();
        showToast("Contoh template kustom berhasil dimuat.");
      }
    });
  }

  // Reset form button
  const btnReset = document.getElementById("btnResetLetterForm");
  if (btnReset) {
    btnReset.addEventListener("click", () => {
      if (confirm("Reset data form? Profil tersimpan Anda akan dikosongkan.")) {
        localStorage.removeItem("lokeriva_cl_name");
        localStorage.removeItem("lokeriva_cl_email");
        localStorage.removeItem("lokeriva_cl_phone");
        localStorage.removeItem("lokeriva_cl_city");
        localStorage.removeItem("lokeriva_cl_edu");
        localStorage.removeItem("lokeriva_cl_skills");
        localStorage.removeItem("lokeriva_cl_exp");
        localStorage.removeItem("lokeriva_cl_recipient");
        localStorage.removeItem("lokeriva_cl_tone");
        localStorage.removeItem("lokeriva_cl_achievements");

        if (nameInput) nameInput.value = "";
        if (emailInput) emailInput.value = "";
        if (phoneInput) phoneInput.value = "";
        if (cityInput) cityInput.value = "";
        if (eduInput) eduInput.value = "";
        if (skillsInput) skillsInput.value = "";
        if (recipientInput) recipientInput.value = "";
        if (achInput) achInput.value = "";
        const jobPos = document.getElementById("clJobPosition");
        const jobComp = document.getElementById("clJobCompany");
        if (jobPos) jobPos.value = "";
        if (jobComp) jobComp.value = "";
        if (expSelect) expSelect.value = "fresh";
        if (toneSelect) toneSelect.value = "formal";

        isCustomizedManually = false;
        updateCoverLetterPreview();
        showToast("Form berhasil di-reset.");
      }
    });
  }

  // Copy button
  const btnCopy = document.getElementById("btnCopyCoverLetter");
  if (btnCopy) {
    btnCopy.addEventListener("click", copyCoverLetter);
  }

  // Download .txt button
  const btnDl = document.getElementById("btnDownloadTxtCoverLetter");
  if (btnDl) {
    btnDl.addEventListener("click", downloadCoverLetterTxt);
  }

  // Close modal button
  const btnClose = document.getElementById("btnCloseCoverLetterModal");
  if (btnClose) {
    btnClose.addEventListener("click", closeCoverLetterModal);
  }

  // Overlay click to close
  const modal = document.getElementById("coverLetterModal");
  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) {
        closeCoverLetterModal();
      }
    });
  }

  // Navbar, Hero, and Footer trigger buttons
  const btnNav = document.getElementById("btnNavCoverLetter");
  if (btnNav) {
    btnNav.addEventListener("click", () => openCoverLetterGenerator("", ""));
  }
  const btnHero = document.getElementById("btnHeroCoverLetter");
  if (btnHero) {
    btnHero.addEventListener("click", () => openCoverLetterGenerator("", ""));
  }
  const btnFooter = document.getElementById("btnFooterCoverLetter");
  if (btnFooter) {
    btnFooter.addEventListener("click", () => openCoverLetterGenerator("", ""));
  }
}

function insertTagIntoTextarea(tag) {
  const ta = document.getElementById("clOutputText");
  if (!ta) return;
  const start = ta.selectionStart || 0;
  const end = ta.selectionEnd || 0;
  const val = ta.value;
  ta.value = val.substring(0, start) + tag + val.substring(end);
  ta.focus();
  ta.selectionStart = ta.selectionEnd = start + tag.length;
  isCustomizedManually = true;
  updateMailtoLink();
}

function saveApplicantData() {
  const getVal = (id) => (document.getElementById(id)?.value || "").trim();
  localStorage.setItem("lokeriva_cl_name", getVal("clApplicantName"));
  localStorage.setItem("lokeriva_cl_email", getVal("clApplicantEmail"));
  localStorage.setItem("lokeriva_cl_phone", getVal("clApplicantPhone"));
  localStorage.setItem("lokeriva_cl_city", getVal("clApplicantCity"));
  localStorage.setItem("lokeriva_cl_edu", getVal("clApplicantEdu"));
  localStorage.setItem("lokeriva_cl_skills", getVal("clSkills"));
  localStorage.setItem("lokeriva_cl_exp", getVal("clExperienceLevel"));
  localStorage.setItem("lokeriva_cl_recipient", getVal("clRecipientName"));
  localStorage.setItem("lokeriva_cl_tone", getVal("clTone") || "formal");
  localStorage.setItem("lokeriva_cl_achievements", getVal("clAchievements"));
}

function openCoverLetterGenerator(posisi = "", perusahaan = "") {
  const modal = document.getElementById("coverLetterModal");
  if (!modal) return;

  const jobPosInput = document.getElementById("clJobPosition");
  const jobCompInput = document.getElementById("clJobCompany");

  if (jobPosInput && posisi) jobPosInput.value = posisi;
  if (jobCompInput && perusahaan) jobCompInput.value = perusahaan;

  isCustomizedManually = false;
  updateCoverLetterPreview();

  modal.style.display = "flex";
  modal.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
}

function closeCoverLetterModal() {
  const modal = document.getElementById("coverLetterModal");
  if (!modal) return;
  modal.style.display = "none";
  modal.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
}

function getLetterData() {
  const getVal = (id, fallback) => {
    const v = (document.getElementById(id)?.value || "").trim();
    return v || fallback;
  };

  const comp = getVal("clJobCompany", "Perusahaan");
  const customRecipient = getVal("clRecipientName", "");

  return {
    name: getVal("clApplicantName", "[Nama Lengkap Anda]"),
    email: getVal("clApplicantEmail", "[Email Anda]"),
    phone: getVal("clApplicantPhone", "[No. WhatsApp/HP]"),
    city: getVal("clApplicantCity", "Indonesia"),
    edu: getVal("clApplicantEdu", "Pendidikan Terakhir"),
    posisi: getVal("clJobPosition", "Posisi Lowongan"),
    perusahaan: comp,
    recipient: customRecipient || `Tim Rekrutmen / HRD ${comp}`,
    recipientEng: customRecipient || `Hiring Team / HR Department of ${comp}`,
    skills: getVal("clSkills", "komunikasi profesional, kerja sama tim, dan keahlian terkait"),
    achievements: getVal("clAchievements", ""),
    exp: document.getElementById("clExperienceLevel")?.value || "fresh",
    tone: document.getElementById("clTone")?.value || "formal"
  };
}

function generateLetterContent() {
  const d = getLetterData();
  const today = new Date();
  const dateOptions = { day: "numeric", month: "long", year: "numeric", timeZone: "Asia/Jakarta" };
  const dateIndo = new Intl.DateTimeFormat("id-ID", dateOptions).format(today);
  const dateEng = new Intl.DateTimeFormat("en-US", { month: "long", day: "numeric", year: "numeric" }).format(today);

  let subject = "";
  let body = "";

  // Kalimat opsional pencapaian / highlight
  const achSentIndo = d.achievements ? ` Selain itu, saya memiliki pencapaian signifikan yaitu ${d.achievements}, yang mencerminkan dedikasi saya dalam memberikan hasil kerja optimal.` : "";
  const achSentEng = d.achievements ? ` Notably, ${d.achievements}, demonstrating my commitment to delivering measurable results and excellence.` : "";

  if (currentLetterTab === "cold_email") {
    subject = `Lamaran Pekerjaan: ${d.posisi} - ${d.name}`;

    let openingGreeting = `Yth. ${d.recipient},`;

    let expParagraph = "";
    if (d.tone === "confident") {
      expParagraph = `Dengan latar belakang kuat di bidang ${d.edu} serta penguasaan aktif dalam ${d.skills}, saya terbiasa menciptakan dampak nyata dan menyelesaikan tantangan dengan solusi yang inovatif.${achSentIndo} Saya sangat tertarik dengan pertumbuhan pesat ${d.perusahaan} dan yakin energi serta inisiatif saya dapat mempercepat pencapaian target tim Bapak/Ibu.`;
    } else if (d.tone === "concise") {
      expParagraph = `Saya memiliki kompetensi inti dalam ${d.skills}${d.achievements ? ` dengan rekam jejak ${d.achievements}` : ""}. Saya terbiasa bekerja tangkas, fokus pada efisiensi kerja, dan siap langsung berkontribusi pada posisi ${d.posisi}.`;
    } else {
      // formal (default)
      if (d.exp === "fresh") {
        expParagraph = `Sebagai lulusan dari ${d.edu} yang berdedikasi dan memiliki latar belakang relevan, saya memiliki pemahaman yang baik serta keahlian dalam ${d.skills}.${achSentIndo} Saya terbiasa belajar dengan cepat, adaptif dalam menghadapi tantangan baru, serta memiliki komitmen tinggi untuk memberikan kontribusi terbaik bagi kemajuan ${d.perusahaan}.`;
      } else if (d.exp === "junior") {
        expParagraph = `Dengan pengalaman kerja profesional selama 1–2 tahun di bidang terkait, saya telah mengasah kemampuan dalam ${d.skills}.${achSentIndo} Saya terbiasa menjalankan tanggung jawab dengan berorientasi pada pencapaian target, ketelitian, serta kolaborasi tim yang solid.`;
      } else {
        expParagraph = `Dengan rekam jejak profesional lebih dari 3 tahun, saya memiliki keahlian mendalam dalam ${d.skills}.${achSentIndo} Saya berpengalaman memimpin alur kerja, meningkatkan efisiensi operasional, serta menyelesaikan proyek strategis dengan hasil yang terukur.`;
      }
    }

    body = `${openingGreeting}

Perkenalkan, nama saya ${d.name}, berdomisili di ${d.city}. Melalui email ini, saya bermaksud untuk mengajukan lamaran pekerjaan untuk posisi ${d.posisi} di ${d.perusahaan} sebagaimana informasi lowongan yang saya temukan melalui platform Lokeriva.

${expParagraph}

Bersama email ini, saya melampirkan Curriculum Vitae (CV) dan dokumen pendukung saya untuk dijadikan bahan pertimbangan. Saya sangat menyambut baik kesempatan untuk berdiskusi lebih lanjut dalam sesi wawancara mengenai bagaimana kompetensi saya dapat selaras dengan kebutuhan tim di ${d.perusahaan}.

Atas perhatian dan kesempatan yang Bapak/Ibu berikan, saya ucapkan terima kasih yang sebesar-besarnya.

Hormat saya,

${d.name}
No. WhatsApp : ${d.phone}
Email        : ${d.email}
Domisili     : ${d.city}`;

  } else if (currentLetterTab === "formal_id") {
    subject = `Surat Lamaran Pekerjaan — ${d.posisi} — ${d.name}`;

    let expDetail = "";
    if (d.tone === "confident") {
      expDetail = `Saya memiliki dorongan kuat untuk menghadirkan nilai tambah bagi perusahaan melalui penguasaan ${d.skills}.${achSentIndo} Dengan gaya kerja yang proaktif dan orientasi pada solusi, saya siap mengambil peran strategis demi kemajuan ${d.perusahaan}.`;
    } else if (d.tone === "concise") {
      expDetail = `Kualifikasi utama saya mencakup penguasaan ${d.skills}.${achSentIndo} Saya mengedepankan ketepatan waktu, ketelitian kerja, dan efektivitas dalam mengeksekusi setiap tanggung jawab.`;
    } else {
      // formal (default)
      if (d.exp === "fresh") {
        expDetail = `Sebagai lulusan baru, saya memiliki semangat kerja yang tinggi, integritas, dan penguasaan dalam ${d.skills}.${achSentIndo} Selama masa studi, saya aktif mengembangkan keahlian praktis dan memiliki daya adaptasi yang sangat baik dalam lingkungan kerja yang dinamis.`;
      } else if (d.exp === "junior") {
        expDetail = `Berbekal pengalaman kerja di bidang terkait selama 1–2 tahun, saya memiliki pemahaman yang kuat mengenai alur kerja dan keahlian di bidang ${d.skills}.${achSentIndo} Saya terbiasa bekerja mandiri maupun dalam tim dengan mengedepankan efektivitas dan ketepatan waktu.`;
      } else {
        expDetail = `Berbekal pengalaman lebih dari 3 tahun di industri, saya terbiasa mengemban tanggung jawab strategis, mengoptimalkan proses kerja, dan menguasai ${d.skills}.${achSentIndo} Saya siap membawa nilai tambah dan kontribusi nyata bagi pertumbuhan ${d.perusahaan}.`;
      }
    }

    body = `${d.city}, ${dateIndo}

Hal      : Lamaran Pekerjaan — ${d.posisi}
Lampiran : 1 (Satu) Berkas

Kepada Yth.
${d.recipient}
${d.perusahaan}
di Tempat

Dengan hormat,

Sehubungan dengan informasi lowongan pekerjaan untuk posisi ${d.posisi} di ${d.perusahaan} yang saya peroleh melalui portal karir Lokeriva, melalui surat ini saya bermaksud untuk mengajukan diri guna bergabung dengan perusahaan yang Bapak/Ibu pimpin.

Berikut adalah ringkasan data diri saya:
Nama                : ${d.name}
Pendidikan Terakhir : ${d.edu}
Domisili            : ${d.city}
Nomor WhatsApp/HP   : ${d.phone}
Alamat Email        : ${d.email}

${expDetail} Saya meyakini bahwa latar belakang dan kompetensi yang saya miliki dapat memberikan kontribusi positif dalam mendukung target dan visi ${d.perusahaan}.

Sebagai bahan pertimbangan Bapak/Ibu, turut saya lampirkan:
1. Curriculum Vitae (CV) Terkini
2. Salinan Ijazah dan Transkrip Nilai
3. Portofolio Kerja / Sertifikat Keahlian

Besar harapan saya untuk diberikan kesempatan menghadiri sesi wawancara, agar saya dapat menjelaskan lebih lanjut mengenai kualifikasi, pengalaman, dan rencana kontribusi yang dapat saya berikan.

Demikian surat lamaran ini saya sampaikan. Atas perhatian dan kesempatan yang Bapak/Ibu berikan, saya ucapkan terima kasih.


Hormat saya,



${d.name}`;

  } else if (currentLetterTab === "english_cl") {
    subject = `Job Application: ${d.posisi} - ${d.name}`;

    let expEng = "";
    if (d.tone === "confident") {
      expEng = `With proven expertise in ${d.skills} and an agile problem-solving approach, I specialize in transforming operational challenges into impactful outcomes.${achSentEng} I am excited by ${d.perusahaan}'s trajectory and am confident that my drive and skill set will deliver immediate value to your organization.`;
    } else if (d.tone === "concise") {
      expEng = `My background spans core competencies in ${d.skills}.${achSentEng} I thrive in high-paced environments, communicate clearly, and take full ownership of delivering high-quality deliverables on schedule.`;
    } else {
      // formal (default)
      if (d.exp === "fresh") {
        expEng = `As an enthusiastic graduate with a background in ${d.edu}, I have developed a strong foundation and practical capability in ${d.skills}.${achSentEng} I am an eager learner, highly adaptable to fast-paced environments, and dedicated to delivering high-quality work for ${d.perusahaan}.`;
      } else if (d.exp === "junior") {
        expEng = `With 1-2 years of professional experience in related roles, I have honed my competencies in ${d.skills}.${achSentEng} I am accustomed to meeting deadlines, solving problems proactively, and collaborating across multidisciplinary teams to achieve shared objectives.`;
      } else {
        expEng = `Bringing over 3 years of progressive professional experience, I offer specialized domain expertise in ${d.skills}.${achSentEng} I have a proven track record of optimizing workflows, executing high-impact initiatives, and driving quantifiable value.`;
      }
    }

    body = `${dateEng}

${d.recipientEng}
${d.perusahaan}

Subject: Application for ${d.posisi} Position

Dear ${d.recipientEng},

I am writing to express my strong enthusiasm for the ${d.posisi} position at ${d.perusahaan}, as advertised on Lokeriva. Given my background in ${d.edu} and my hands-on experience, I am confident in my ability to make an immediate and meaningful contribution to your organization.

${expEng}

I have attached my resume and portfolio for your review. I would welcome the opportunity to discuss how my skill set and background align with the goals and needs of ${d.perusahaan}.

Thank you very much for your time and consideration. I look forward to the possibility of speaking with you soon.

Sincerely,

${d.name}
Phone/WhatsApp : ${d.phone}
Email          : ${d.email}
Location       : ${d.city}, Indonesia`;

  } else {
    // custom_template
    subject = `Lamaran Pekerjaan: ${d.posisi} — ${d.name}`;

    const savedTemplate = localStorage.getItem("lokeriva_cl_custom_template") || DEFAULT_CUSTOM_TEMPLATE;

    body = savedTemplate
      .replace(/\{nama\}/g, d.name)
      .replace(/\{posisi\}/g, d.posisi)
      .replace(/\{perusahaan\}/g, d.perusahaan)
      .replace(/\{penerima\}/g, d.recipient)
      .replace(/\{kota\}/g, d.city)
      .replace(/\{pendidikan\}/g, d.edu)
      .replace(/\{skills\}/g, d.skills)
      .replace(/\{pencapaian\}/g, d.achievements || "")
      .replace(/\{email\}/g, d.email)
      .replace(/\{telepon\}/g, d.phone);
  }

  return { subject, body };
}

function updateCoverLetterPreview() {
  const { subject, body } = generateLetterContent();

  const subjectRow = document.getElementById("clSubjectLineRow");
  const subjectInput = document.getElementById("clSubjectInput");
  const outputText = document.getElementById("clOutputText");
  const badgeEl = document.getElementById("clFormatBadge");

  if (subjectRow && subjectInput) {
    if (currentLetterTab === "formal_id") {
      subjectRow.style.display = "none";
    } else {
      subjectRow.style.display = "flex";
      if (!isCustomizedManually || !subjectInput.value.trim()) {
        subjectInput.value = subject;
      }
    }
  }

  if (outputText && (!isCustomizedManually || currentLetterTab === "custom_template")) {
    outputText.value = body;
  }

  if (badgeEl) {
    if (currentLetterTab === "cold_email") badgeEl.innerText = "Cold Email";
    else if (currentLetterTab === "formal_id") badgeEl.innerText = "Surat Formal (ID)";
    else if (currentLetterTab === "english_cl") badgeEl.innerText = "Cover Letter (EN)";
    else badgeEl.innerText = "Kustom Bebas";
  }

  updateMailtoLink();
}

function updateMailtoLink() {
  const mailtoBtn = document.getElementById("btnMailtoCoverLetter");
  if (!mailtoBtn) return;

  const subject = document.getElementById("clSubjectInput")?.value || "";
  const body = document.getElementById("clOutputText")?.value || "";

  const encSubject = encodeURIComponent(subject);
  const encBody = encodeURIComponent(body);
  mailtoBtn.href = `mailto:?subject=${encSubject}&body=${encBody}`;
}

function copyCoverLetter() {
  const output = document.getElementById("clOutputText");
  if (!output || !output.value) return;

  const fullText = output.value;
  if (navigator.clipboard) {
    navigator.clipboard.writeText(fullText).then(() => {
      showToast("Surat lamaran berhasil disalin ke clipboard!");
    }).catch(() => {
      fallbackCopyText(fullText);
    });
  } else {
    fallbackCopyText(fullText);
  }
}

function fallbackCopyText(text) {
  const ta = document.createElement("textarea");
  ta.value = text;
  document.body.appendChild(ta);
  ta.select();
  try {
    document.execCommand("copy");
    showToast("Surat lamaran berhasil disalin!");
  } catch (e) {
    showToast("Gagal menyalin teks.");
  }
  document.body.removeChild(ta);
}

function downloadCoverLetterTxt() {
  const output = document.getElementById("clOutputText");
  const body = output ? output.value : "";
  const d = getLetterData();
  const safeName = d.name.replace(/[^a-zA-Z0-9]/g, "_") || "Pelamar";
  const safePos = d.posisi.replace(/[^a-zA-Z0-9]/g, "_") || "Loker";
  const filename = `Surat_Lamaran_${safeName}_${safePos}.txt`;

  const blob = new Blob([body], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showToast(`File ${filename} berhasil diunduh!`);
}

