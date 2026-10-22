/**
 * cc-app.js — AI Video Command Center SPA
 * Contract 0.1.0-draft · Registry 1.0.0 · Anti/Antigravity build
 * Ngôn ngữ UI: tiếng Việt
 */

/* ─── SVG Icons ──────────────────────────────────────────── */
const I = {
  home:    `<svg viewBox="0 0 20 20" fill="currentColor"><path d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h4a1 1 0 001-1v-3h2v3a1 1 0 001 1h4a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z"/></svg>`,
  folder:  `<svg viewBox="0 0 20 20" fill="currentColor"><path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg>`,
  plus:    `<svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clip-rule="evenodd"/></svg>`,
  cpu:     `<svg viewBox="0 0 20 20" fill="currentColor"><path d="M13 7H7v6h6V7z"/><path fill-rule="evenodd" d="M7 2a1 1 0 012 0v1h2V2a1 1 0 112 0v1h1a2 2 0 012 2v1h1a1 1 0 110 2h-1v2h1a1 1 0 110 2h-1v1a2 2 0 01-2 2h-1v1a1 1 0 11-2 0v-1H9v1a1 1 0 11-2 0v-1H6a2 2 0 01-2-2v-1H3a1 1 0 110-2h1V9H3a1 1 0 010-2h1V6a2 2 0 012-2h1V2zM6 6h8v8H6V6z" clip-rule="evenodd"/></svg>`,
  video:   `<svg viewBox="0 0 20 20" fill="currentColor"><path d="M2 6a2 2 0 012-2h6a2 2 0 012 2v8a2 2 0 01-2 2H4a2 2 0 01-2-2V6zm12.553 1.106A1 1 0 0014 8v4a1 1 0 00.553.894l2 1A1 1 0 0018 13V7a1 1 0 00-1.447-.894l-2 1z"/></svg>`,
  alert:   `<svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>`,
  check:   `<svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>`,
  x:       `<svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/></svg>`,
  refresh: `<svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"/></svg>`,
  eye:     `<svg viewBox="0 0 20 20" fill="currentColor"><path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/><path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd"/></svg>`,
  stop:    `<svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 001 1h4a1 1 0 001-1V8a1 1 0 00-1-1H8z" clip-rule="evenodd"/></svg>`,
  log:     `<svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h4a1 1 0 110 2H4a1 1 0 01-1-1z" clip-rule="evenodd"/></svg>`,
  play:    `<svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd"/></svg>`,
  film:    `<svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4 3a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V5a2 2 0 00-2-2H4zm3 2h6v4H7V5zm8 8v2h1v-2h-1zm-2-2H7v4h6v-4zm2 0h1V9h-1v2zm1-4V5h-1v2h1zM5 5v2H4V5h1zm-1 4h1v2H4V9zm1 4H4v2h1v-2z" clip-rule="evenodd"/></svg>`,
  list:    `<svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clip-rule="evenodd"/></svg>`,
  cog:     `<svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z" clip-rule="evenodd"/></svg>`,
};

/* ─── 8 Fanpage Channel Profiles (Hợp nhất toàn hệ thống) ── */
const CHANNELS_8 = [
  {
    id: 'ch_wuby_main',
    name: 'Kênh 1: Wuby Thuyết Minh',
    niche: 'Thuyết minh AI giữ nền',
    preset_id: 'cauhinh3_wuby',
    voice_id: 'wuby_clone_v2',
    banner_text: 'WUBY AI STUDIO',
    marquee_text: 'Bản thuyết minh AI độc quyền giữ âm thanh gốc',
    blur_box: { x: 6, y: 74, w: 88, h: 16 },
    schedule: '11:30 · 19:30 · 21:00',
  },
  {
    id: 'ch_review_black',
    name: 'Kênh 2: Review Phim Black',
    niche: 'Review kịch tính viền đen',
    preset_id: 'cauhinh2',
    voice_id: 'vi_male_review_tram',
    banner_text: 'REVIEW PHIM HAY',
    marquee_text: 'Theo dõi kênh để xem tập tiếp theo!',
    blur_box: { x: 8, y: 72, w: 84, h: 18 },
    schedule: '12:00 · 18:00 · 22:00',
  },
  {
    id: 'ch_movie_clone',
    name: 'Kênh 3: Phim Ngắn 9:16',
    niche: 'Nền mờ Gaussian + Lật gương',
    preset_id: 'cauhinh3',
    voice_id: 'vi_female_north_ngochuyen',
    banner_text: 'PHIM NGẮN HOT',
    marquee_text: 'Đừng quên thả tim và bấm theo dõi kênh nhé!',
    blur_box: { x: 6, y: 70, w: 88, h: 18 },
    schedule: '09:00 · 15:00 · 20:30',
  },
  {
    id: 'ch_chidepdicau',
    name: 'Kênh 4: Chị Đẹp Đi Câu',
    niche: 'Outdoor / Câu cá giải trí',
    preset_id: 'chidepdicau',
    voice_id: 'vi_female_north_ngochuyen',
    banner_text: 'CHỊ ĐẸP ĐI CÂU',
    marquee_text: 'Hành trình săn cá khủng mỗi ngày!',
    blur_box: { x: 5, y: 73, w: 90, h: 17 },
    schedule: '10:30 · 17:30 · 20:00',
  },
  {
    id: 'ch_song1minh',
    name: 'Kênh 5: Sống Một Mình',
    niche: 'Vlog Chill Lo-Fi / Healing',
    preset_id: 'song1minhcogivui',
    voice_id: 'vi_female_south_thaovy',
    banner_text: 'SỐNG MỘT MÌNH CÓ GÌ VUI',
    marquee_text: 'Nhật ký chill mỗi tối một mình',
    blur_box: { x: 10, y: 75, w: 80, h: 14 },
    schedule: '20:00 · 22:30',
  },
  {
    id: 'ch_hoc_tieng_trung',
    name: 'Kênh 6: Học Tiếng Trung',
    niche: 'Edutainment / Song ngữ',
    preset_id: 'cauhinh3',
    voice_id: 'vi_female_north_ngochuyen',
    banner_text: 'HỌC TIẾNG TRUNG QUA PHIM',
    marquee_text: 'Lưu lại ngay mẫu câu giao tiếp cực chuẩn này!',
    blur_box: { x: 6, y: 76, w: 88, h: 14 },
    schedule: '08:00 · 12:30 · 19:00',
  },
  {
    id: 'ch_drama_reels',
    name: 'Kênh 7: Drama Tổng Tài',
    niche: 'Series ngôn tình ngắn tập',
    preset_id: 'cauhinh2',
    voice_id: 'vi_male_north_minhquang',
    banner_text: 'TẬP CUỐI: CÁI KẾT BẤT NGỜ',
    marquee_text: 'Bấm vào trang cá nhân để xem trọn bộ Full HD!',
    blur_box: { x: 6, y: 71, w: 88, h: 18 },
    schedule: '11:00 · 16:00 · 21:30',
  },
  {
    id: 'ch_custom_studio',
    name: 'Kênh 8: Studio Tự Do',
    niche: 'Tuỳ biến 100% thông số',
    preset_id: 'basic_render',
    voice_id: 'original',
    banner_text: '',
    marquee_text: '',
    blur_box: { x: 6, y: 72, w: 88, h: 16 },
    schedule: 'Đăng thủ công / Theo yêu cầu',
  },
];

/* ─── State ──────────────────────────────────────────────── */
const state = {
  view: 'overview',          // 'overview' | 'projects' | 'project-detail' | 'new-job' | 'job-detail' | 'channels' | 'modules' | 'agents'
  projectId: null,
  jobId: null,
  selectedChannelId: 'ch_review_black',
  localVideoBlobUrl: null,
  projects: [],
  jobs: [],
  agents: [],
  modules: [],
  presets: [],
  selectedPreset: null,
  jobFilterStatus: '',
  logFilter: '',
  submitPending: false,
  isMock: window.CC_API ? window.CC_API.isMock : true,
};

/* ─── DOM helpers ────────────────────────────────────────── */
const $ = id => document.getElementById(id);

function chip(status) {
  return `<span class="chip ${status}" aria-label="${window.ccUtil.statusLabel(status)}">${window.ccUtil.statusLabel(status)}</span>`;
}

function toast(msg, type = 'ok') {
  const container = $('toast-container');
  if (!container) return;
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.setAttribute('role', 'status');
  t.textContent = msg;
  container.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

function renderError(msg, retryFn = null) {
  return `
    <div class="error-state" role="alert">
      ${I.alert}
      <div style="flex:1">${msg}</div>
      ${retryFn ? `<button class="btn btn-secondary btn-sm" id="btn-err-retry">${I.refresh} Thử lại</button>` : ''}
    </div>`;
}

function renderEmpty(msg = 'Chưa có dữ liệu', hint = '') {
  return `<div class="empty-state" role="status">${I.list}<p>${msg}</p>${hint ? `<small>${hint}</small>` : ''}</div>`;
}

function renderLoading() {
  return `<div class="empty-state text-muted" aria-busy="true"><p>Đang tải…</p></div>`;
}

/* ─── Sync UI Mode (Mock vs Real API) ────────────────────── */
function syncApiModeUI() {
  state.isMock = window.CC_API ? window.CC_API.isMock : true;

  const btnMode = $('btn-api-mode');
  const txtMode = $('api-mode-text');
  const banner = $('mock-banner');
  const bannerTxt = $('banner-text');

  if (btnMode && txtMode) {
    if (state.isMock) {
      btnMode.className = 'api-badge mode-mock';
      txtMode.textContent = 'Chế độ: Mô phỏng';
    } else {
      btnMode.className = 'api-badge mode-real';
      txtMode.textContent = 'Chế độ: API Thật';
    }
  }

  if (banner && bannerTxt) {
    if (state.isMock) {
      banner.classList.remove('hidden', 'real');
      bannerTxt.textContent = 'DỮ LIỆU MÔ PHỎNG — Thao tác qua Mock Client (Registry 1.0.0). Nhấn "Cấu hình API" để kết nối backend thật.';
    } else {
      banner.classList.add('real');
      banner.classList.remove('hidden');
      bannerTxt.textContent = `KẾT NỐI TRỰC TIẾP QUA HTTPS CỔNG 443 (${window.CC_CONFIG.apiBase}) — Hàng đợi PostgreSQL 16 + Outbound Agent + JSON Render Report hoạt động 100%.`;
    }
  }
}

let jobPollTimer = null;
function stopJobPolling() {
  if (jobPollTimer) {
    clearInterval(jobPollTimer);
    jobPollTimer = null;
  }
}

function renderProgressCell(j) {
  const pg = j.progress;
  const pct = pg && pg.percent !== null && pg.percent !== undefined
    ? pg.percent
    : (pg && pg.total_tasks ? Math.round((pg.completed_tasks / pg.total_tasks) * 100) : 0);
  const label = pg ? `${pg.completed_tasks}/${pg.total_tasks} bước (${pct}%)` : '—';
  const fillCls = j.status === 'running' ? 'running' : (j.status === 'failed' ? 'failed' : '');
  return `
    <div class="progress-cell">
      <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--txt-2)">
        <span>${label}</span>
      </div>
      <div class="progress-track">
        <div class="progress-fill ${fillCls}" style="width:${Math.max(pct, j.status === 'running' ? 15 : 0)}%"></div>
      </div>
    </div>
  `;
}

/* ─── Navigation ─────────────────────────────────────────── */
function navigate(view, params = {}) {
  stopJobPolling();
  state.view = view;
  if (params.projectId !== undefined) state.projectId = params.projectId;
  if (params.jobId !== undefined)     state.jobId     = params.jobId;
  if (params.channelId !== undefined) state.selectedChannelId = params.channelId;
  render();
}

function syncNav() {
  document.querySelectorAll('[data-nav]').forEach(el => {
    el.classList.toggle('active', el.dataset.nav === state.view
      || (state.view === 'project-detail' && el.dataset.nav === 'projects')
      || (state.view === 'job-detail' && el.dataset.nav === 'projects'));
  });
}

/* ─── Views ─────────────────────────────────────────────── */

// A. TỔNG QUAN
async function renderOverview() {
  const main = $('main-content');
  main.innerHTML = renderLoading();
  try {
    const [agentsRes, jobsRes] = await Promise.all([
      window.CC_API.getAgents(),
      window.CC_API.getAllJobs(),
    ]);
    state.agents = agentsRes.items || [];
    state.jobs   = jobsRes.items || [];
  } catch(e) {
    const msg = e?.body?.error?.message || (e?.status === 0 ? 'Không kết nối được tới backend. Kiểm tra URL API hoặc chuyển sang chế độ Mô phỏng.' : 'Lỗi tải dữ liệu.');
    main.innerHTML = renderError(`Không thể tải dữ liệu tổng quan. ${msg}`, () => renderOverview());
    $('btn-err-retry')?.addEventListener('click', renderOverview);
    return;
  }

  const counts = {
    running:          state.jobs.filter(j => j.status === 'running').length,
    queued:           state.jobs.filter(j => j.status === 'queued').length,
    needs_review:     state.jobs.filter(j => j.status === 'needs_review').length,
    needs_attention:  state.jobs.filter(j => j.status === 'needs_attention').length,
    failed:           state.jobs.filter(j => j.status === 'failed').length,
    cancelling:       state.jobs.filter(j => j.status === 'cancelling').length,
  };

  const needsAction = counts.failed + counts.needs_attention + counts.needs_review;
  const recentJobs = state.jobs.slice(0, 8);

  main.innerHTML = `
    <div class="page-header">
      <div>
        <h1 class="page-title">Trung Tâm Điều Hành Render Video AI</h1>
        <p class="page-subtitle">Đồng bộ thời gian thực lúc ${new Date().toLocaleTimeString('vi-VN')} · ${state.isMock ? '<span class="not-impl">Dữ liệu mô phỏng</span>' : '<span style="color:var(--teal);font-weight:600">⚡ Đang kết nối Production HTTPS :443</span>'}</p>
      </div>
      <div class="page-actions">
        <button class="btn btn-secondary btn-sm" id="btn-api-settings-quick">${I.cog} Cấu hình API</button>
        <button class="btn btn-secondary btn-sm" id="btn-refresh-overview">${I.refresh} Làm mới</button>
        <button class="btn btn-primary btn-sm" id="btn-new-job-quick">${I.plus} Tạo job render mới</button>
      </div>
    </div>

    <!-- Luồng kiến trúc 4 bước: Port 443 -> Queue -> Outbound Agent -> JSON Report -->
    <div class="arch-strip">
      <div class="arch-node">
        <div class="arch-node-icon">🔒</div>
        <div>
          <div class="arch-node-title">1. Cổng HTTPS 443 <span class="arch-pill">TLS 1.3</span></div>
          <div class="arch-node-desc">Giao tiếp duy nhất qua cổng 443. API &amp; DB khoá chặt trên loopback <code>127.0.0.1</code>.</div>
        </div>
      </div>
      <div class="arch-node">
        <div class="arch-node-icon">📥</div>
        <div>
          <div class="arch-node-title">2. Hàng Đợi PostgreSQL <span class="arch-pill">FIFO DAG</span></div>
          <div class="arch-node-desc">Xếp hàng tự động <code>FOR UPDATE SKIP LOCKED</code>, phân rã bước <code>probe → compose</code>.</div>
        </div>
      </div>
      <div class="arch-node">
        <div class="arch-node-icon">⚡</div>
        <div>
          <div class="arch-node-title">3. Outbound Agent <span class="arch-pill">${state.agents.filter(a => a.status === 'online').length}/${state.agents.length || 1} Online</span></div>
          <div class="arch-node-desc">Agent chủ động claim việc qua cổng 443, khoá tài nguyên CPU/GPU &amp; gia hạn Lease.</div>
        </div>
      </div>
      <div class="arch-node">
        <div class="arch-node-icon">📄</div>
        <div>
          <div class="arch-node-title">4. Gửi JSON Cấu Hình <span class="arch-pill">SHA-256</span></div>
          <div class="arch-node-desc">Trả về <code>render-report.json</code> &amp; <code>probe.json</code> kèm <code>render_config</code> và video đã kiểm chứng.</div>
        </div>
      </div>
    </div>

    <div class="grid-4 mb-3">
      <div class="stat-card running">
        <div class="label"><span>Đang chạy (Running)</span> ${I.play}</div>
        <div class="value">${counts.running}</div>
        <div class="sublabel">job đang được Agent xử lý</div>
      </div>
      <div class="stat-card waiting">
        <div class="label"><span>Hàng đợi (Queued)</span> ${I.list}</div>
        <div class="value">${counts.queued}</div>
        <div class="sublabel">job xếp hàng chờ claim</div>
      </div>
      <div class="stat-card review">
        <div class="label"><span>Hoàn tất / Cần duyệt</span> ${I.film}</div>
        <div class="value">${counts.needs_review}</div>
        <div class="sublabel">đã có Video + JSON Report</div>
      </div>
      <div class="stat-card ${counts.failed + counts.needs_attention > 0 ? 'error' : 'ok'}">
        <div class="label"><span>Cảnh báo / Cần chú ý</span> ${I.alert}</div>
        <div class="value">${counts.failed + counts.needs_attention}</div>
        <div class="sublabel">job lỗi hoặc hết hạn lease</div>
      </div>
    </div>

    <div class="grid-2" style="gap:16px">
      <!-- Agent status -->
      <div class="card">
        <div class="card-header">
          <span class="card-title">${I.cpu} Trạng Thái Worker Agent</span>
          <button class="btn btn-ghost btn-sm" id="btn-go-agents">Chi tiết (${state.agents.length})</button>
        </div>
        ${state.agents.length === 0
          ? renderEmpty('Chưa có Agent nào kết nối', 'Agent kết nối outbound qua HTTPS 443.')
          : state.agents.map(a => `
            <div class="agent-card ${a.status}" style="margin-bottom:10px">
              <div class="agent-header">
                <span class="agent-name">🖥 ${a.machine_label || ('Worker ' + window.ccUtil.shortId(a.id))}</span>
                ${chip(a.status)}
              </div>
              <div class="agent-meta">
                Heartbeat cuối: <b>${window.ccUtil.relativeTime(a.last_seen_at)}</b> ·
                Task đang chạy: <b>${a.active_task_count}</b>
              </div>
              <div class="agent-caps">
                ${(a.capabilities || []).map(c => `<span class="tag" style="border-color:rgba(45,212,191,0.3);color:var(--teal)">⚡ ${c}</span>`).join('')}
              </div>
            </div>
          `).join('')}
        <div class="info-state mt-2 text-sm">
          <b>Cơ chế hàng đợi an toàn:</b> Kể cả khi Agent tạm nghỉ, mọi Job gửi lên đều được xếp vào bảng <code>command_center.jobs</code> (trạng thái <code>queued</code>) và tự động chạy ngay khi Agent online.
        </div>
      </div>

      <!-- Cần xử lý & Duyệt -->
      <div class="card">
        <div class="card-header">
          <span class="card-title">${I.film} Video Mới Render &amp; Cần Duyệt (${needsAction})</span>
        </div>
        ${needsAction === 0
          ? `<div class="empty-state" style="padding:24px"><p>Tất cả các job đều ổn định.</p></div>`
          : state.jobs.filter(j => ['failed','needs_attention','needs_review'].includes(j.status))
              .slice(0,6).map(j => `
              <div class="flex items-center gap-2 mb-2" style="cursor:pointer;padding:10px 12px;border-radius:8px;background:rgba(13,18,27,0.75);border:1px solid var(--border)" data-job="${j.id}" role="button" tabindex="0" aria-label="Xem chi tiết job ${window.ccUtil.shortId(j.id)}">
                ${chip(j.status)}
                <div style="flex:1;min-width:0">
                  <div class="truncate" style="font-size:12px;font-weight:600">${j.preset_id} · <span class="font-mono" style="color:var(--teal)">#${window.ccUtil.shortId(j.id)}</span></div>
                  <div class="text-muted text-sm">Đã xuất Video MP4 + JSON cấu hình</div>
                </div>
                <span class="text-muted text-sm">${window.ccUtil.relativeTime(j.updated_at)}</span>
                <span class="btn btn-secondary btn-sm">Mở xem →</span>
              </div>
            `).join('')
        }
      </div>
    </div>

    <div class="section mt-4">
      <div class="section-header">
        <span class="section-title">Hàng Đợi &amp; Lịch Sử Job Render Gần Nhất</span>
        <div class="section-actions">
          <button class="btn btn-ghost btn-sm" id="btn-go-projects">Quản lý theo dự án →</button>
        </div>
      </div>
      ${recentJobs.length === 0 ? renderEmpty('Chưa có job nào trong hệ thống') : `
        <div class="table-wrap">
          <table>
            <thead><tr>
              <th scope="col">Job ID</th>
              <th scope="col">Dự án</th>
              <th scope="col">Cấu hình Preset</th>
              <th scope="col">Trạng thái Hàng đợi</th>
              <th scope="col">Tiến độ Pipeline</th>
              <th scope="col">Cập nhật</th>
              <th scope="col">Thao tác</th>
            </tr></thead>
            <tbody>
              ${recentJobs.map(j => `
                <tr data-job="${j.id}" role="button" tabindex="0" aria-label="Xem job ${window.ccUtil.shortId(j.id)}">
                  <td class="mono" style="color:var(--teal);font-weight:600">#${window.ccUtil.shortId(j.id)}</td>
                  <td class="mono muted">${window.ccUtil.shortId(j.project_id)}</td>
                  <td><span class="tag" style="font-size:11px">${j.preset_id}</span> <span class="text-muted text-sm">v${j.preset_version}</span></td>
                  <td>${chip(j.status)}</td>
                  <td>${renderProgressCell(j)}</td>
                  <td class="muted nowrap">${window.ccUtil.relativeTime(j.updated_at)}</td>
                  <td><button class="btn btn-secondary btn-sm" data-job="${j.id}" aria-label="Chi tiết">Xem JSON &amp; Video</button></td>
                </tr>`).join('')}
            </tbody>
          </table>
        </div>
      `}
    </div>
  `;

  $('btn-refresh-overview')?.addEventListener('click', () => navigate('overview'));
  $('btn-new-job-quick')?.addEventListener('click', () => navigate('new-job'));
  $('btn-api-settings-quick')?.addEventListener('click', openApiSettingsModal);
  $('btn-go-agents')?.addEventListener('click', () => navigate('agents'));
  $('btn-go-projects')?.addEventListener('click', () => navigate('projects'));

  main.querySelectorAll('[data-job]').forEach(el => {
    const handler = () => navigate('job-detail', { jobId: el.dataset.job });
    el.addEventListener('click', handler);
    el.addEventListener('keydown', e => { if(e.key === 'Enter' || e.key === ' ') handler(); });
  });
}

// B. DỰ ÁN
async function renderProjects() {
  const main = $('main-content');
  main.innerHTML = renderLoading();
  try {
    const res = await window.CC_API.getProjects();
    state.projects = res.items || [];
  } catch(e) {
    main.innerHTML = renderError(`Không tải được danh sách dự án. ${e?.body?.error?.message || ''}`, renderProjects);
    $('btn-err-retry')?.addEventListener('click', renderProjects);
    return;
  }

  main.innerHTML = `
    <div class="page-header">
      <div>
        <h1 class="page-title">Dự án</h1>
        <p class="page-subtitle">${state.projects.length} dự án · ${state.isMock ? '<span class="not-impl">Dữ liệu mô phỏng</span>' : '<span style="color:var(--teal)">API thật</span>'}</p>
      </div>
      <div class="page-actions">
        <button class="btn btn-primary" id="btn-create-project">${I.plus} Tạo dự án mới</button>
      </div>
    </div>
    ${state.projects.length === 0 ? renderEmpty('Chưa có dự án nào', 'Tạo dự án mới để bắt đầu quản lý job render.') : `
      <div class="table-wrap">
        <table>
          <thead><tr>
            <th scope="col">Tên dự án</th>
            <th scope="col">ID</th>
            <th scope="col">Phiên bản</th>
            <th scope="col">Cập nhật</th>
            <th scope="col">Lưu trữ</th>
            <th scope="col"></th>
          </tr></thead>
          <tbody>
            ${state.projects.map(p => `
              <tr data-project="${p.id}" role="button" tabindex="0" aria-label="Xem dự án ${p.name}">
                <td style="font-weight:600">${p.name}</td>
                <td class="mono">${window.ccUtil.shortId(p.id)}</td>
                <td class="muted">v${p.version}</td>
                <td class="muted nowrap">${window.ccUtil.relativeTime(p.updated_at)}</td>
                <td>${p.archived_at ? `<span class="tag">Lưu trữ</span>` : '—'}</td>
                <td>
                  <button class="btn btn-ghost btn-sm" data-project="${p.id}" aria-label="Xem dự án">Xem</button>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `}
  `;

  $('btn-create-project')?.addEventListener('click', openCreateProjectModal);
  main.querySelectorAll('[data-project]').forEach(el => {
    const handler = () => navigate('project-detail', { projectId: el.dataset.project });
    el.addEventListener('click', handler);
    el.addEventListener('keydown', e => { if(e.key === 'Enter' || e.key === ' ') handler(); });
  });
}

// B2. CHI TIẾT DỰ ÁN + JOB LIST
async function renderProjectDetail() {
  const main = $('main-content');
  main.innerHTML = renderLoading();

  let project, jobsRes;
  try {
    [project, jobsRes] = await Promise.all([
      window.CC_API.getProject(state.projectId),
      window.CC_API.getProjectJobs(state.projectId, { status: state.jobFilterStatus || undefined }),
    ]);
  } catch(e) {
    main.innerHTML = renderError(e?.body?.error?.message || 'Không tải được dữ liệu dự án.', () => renderProjectDetail());
    $('btn-err-retry')?.addEventListener('click', renderProjectDetail);
    return;
  }
  state.jobs = jobsRes.items || [];

  const STATUSES = ['', 'queued', 'running', 'needs_review', 'needs_attention', 'failed', 'cancelled'];

  main.innerHTML = `
    <div class="page-header">
      <div>
        <nav aria-label="Đường dẫn" style="font-size:11px;color:var(--txt-3);margin-bottom:4px">
          <button class="btn btn-ghost btn-sm" id="btn-back-projects" style="padding:0">Dự án</button>
          <span style="margin:0 4px">›</span>
          <span>${project.name}</span>
        </nav>
        <h1 class="page-title">${project.name}</h1>
        <p class="page-subtitle">v${project.version} · ID: <span class="font-mono">${window.ccUtil.shortId(project.id)}</span> · Cập nhật ${window.ccUtil.relativeTime(project.updated_at)}
          ${state.isMock ? '· <span class="not-impl">Dữ liệu mô phỏng</span>' : ''}</p>
      </div>
      <div class="page-actions">
        <button class="btn btn-secondary btn-sm" id="btn-rename-project">${I.list} Đổi tên</button>
        <button class="btn btn-primary btn-sm" id="btn-new-job-proj">${I.plus} Tạo job</button>
      </div>
    </div>

    <div class="section">
      <div class="section-header">
        <span class="section-title">Danh sách job của dự án</span>
      </div>
      <div class="filter-bar" id="job-filter-bar">
        ${STATUSES.map(s => `
          <button class="filter-chip${s === state.jobFilterStatus ? ' active' : ''}"
            data-filter="${s}" aria-pressed="${s === state.jobFilterStatus}">
            ${s === '' ? 'Tất cả' : window.ccUtil.statusLabel(s)}
          </button>
        `).join('')}
      </div>
      ${state.jobs.length === 0 ? renderEmpty('Chưa có job nào', state.jobFilterStatus ? `Không có job ở trạng thái "${window.ccUtil.statusLabel(state.jobFilterStatus)}".` : '') : `
        <div class="table-wrap">
          <table>
            <thead><tr>
              <th scope="col">ID</th>
              <th scope="col">Preset</th>
              <th scope="col">Trạng thái</th>
              <th scope="col">Tiến độ</th>
              <th scope="col">Cập nhật</th>
              <th scope="col"></th>
            </tr></thead>
            <tbody>
              ${state.jobs.map(j => {
                const pg = j.progress;
                const pgText = pg ? (pg.percent !== null ? `${pg.percent}%` : `${pg.completed_tasks}/${pg.total_tasks} task`) : '—';
                return `
                  <tr data-job="${j.id}" role="button" tabindex="0" aria-label="Xem job ${window.ccUtil.shortId(j.id)}">
                    <td class="mono">${window.ccUtil.shortId(j.id)}</td>
                    <td>${j.preset_id}</td>
                    <td>${chip(j.status)}</td>
                    <td class="muted">${pgText}</td>
                    <td class="muted nowrap">${window.ccUtil.relativeTime(j.updated_at)}</td>
                    <td><button class="btn btn-ghost btn-sm" data-job="${j.id}" aria-label="Chi tiết">Chi tiết</button></td>
                  </tr>`;
              }).join('')}
            </tbody>
          </table>
        </div>
      `}
    </div>
  `;

  $('btn-back-projects')?.addEventListener('click', () => navigate('projects'));
  $('btn-new-job-proj')?.addEventListener('click', () => navigate('new-job'));
  $('btn-rename-project')?.addEventListener('click', () => openRenameProjectModal(project));
  main.querySelectorAll('#job-filter-bar [data-filter]').forEach(btn => {
    btn.addEventListener('click', () => {
      state.jobFilterStatus = btn.dataset.filter;
      renderProjectDetail();
    });
  });
  main.querySelectorAll('[data-job]').forEach(el => {
    const handler = () => navigate('job-detail', { jobId: el.dataset.job });
    el.addEventListener('click', handler);
    el.addEventListener('keydown', e => { if(e.key === 'Enter' || e.key === ' ') handler(); });
  });
}

// C. STUDIO ĐA CẤU HÌNH & CHỌN VÙNG BLUR TRỰC TIẾP TRÊN KHUNG VIDEO THẬT
async function renderNewJob() {
  const main = $('main-content');
  main.innerHTML = renderLoading();
  try {
    const [projRes, presetRes] = await Promise.all([
      window.CC_API.getProjects(),
      window.CC_API.getPresets(),
    ]);
    state.projects = projRes.items || [];
    state.presets  = presetRes.items || [];
  } catch(e) {
    main.innerHTML = renderError(`Không tải được dữ liệu Studio. ${e?.body?.error?.message || ''}`, renderNewJob);
    $('btn-err-retry')?.addEventListener('click', renderNewJob);
    return;
  }

  const activeProjects = state.projects.filter(p => !p.archived_at);
  const defaultProject = state.projectId || (activeProjects[0]?.id || '');
  const activeChannel  = CHANNELS_8.find(c => c.id === state.selectedChannelId) || CHANNELS_8[1];
  const defaultPreset  = state.presets.find(p => p.id === activeChannel.preset_id && p.available)
                      || state.presets.find(p => p.id === 'basic_render' && p.available)
                      || state.presets.find(p => p.available)
                      || state.presets[0];

  main.innerHTML = `
    <div class="page-header">
      <div>
        <h1 class="page-title">🎬 Studio Hợp Nhất Đa Cấu Hình &amp; Custom Blur Trên Video Thật</h1>
        <p class="page-subtitle">Chọn kênh Fanpage, tải video MP4 lên hoặc chọn file sẵn có, kéo thả khung Blur trực tiếp trên hình ảnh thực tế và đẩy vào hàng đợi HTTPS :443.</p>
      </div>
      <div class="page-actions">
        <button class="btn btn-secondary btn-sm" id="btn-go-channels-view">📊 Ma trận 8 Kênh</button>
        <button class="btn btn-ghost btn-sm" id="btn-cancel-job">← Tổng quan</button>
      </div>
    </div>

    <!-- Thanh chọn nhanh 8 Kênh Fanpage -->
    <div class="card mb-3">
      <div class="card-header">
        <span class="card-title">📺 Bước 1: Chọn Kênh Fanpage Đích (Tự động nạp Preset, Giọng đọc AI, Chạy chữ &amp; Tọa độ Blur mẫu)</span>
        <span class="tag" id="selected-channel-tag" style="color:var(--teal);border-color:rgba(45,212,191,0.35)">${activeChannel.name}</span>
      </div>
      <div class="channel-strip" id="studio-channel-strip">
        ${CHANNELS_8.map(ch => `
          <button type="button" class="channel-pill-card ${ch.id === activeChannel.id ? 'active' : ''}" data-channel-id="${ch.id}">
            <div class="channel-pill-top">
              <span class="truncate">${ch.name}</span>
              <span class="tag" style="font-size:9px;padding:1px 5px;color:var(--teal)">${ch.preset_id}</span>
            </div>
            <div class="channel-pill-sub truncate">${ch.niche} · Blur (${ch.blur_box.x}%,${ch.blur_box.y}%)</div>
          </button>
        `).join('')}
      </div>
    </div>

    <form id="new-job-form" novalidate>
      <div class="grid-2" style="gap:20px">
        <!-- Cột Trái: Dự án + Upload/Chọn Video + Đa Cấu Hình (A, B, C, D) -->
        <div class="flex-col" style="gap:16px">
          <div class="card">
            <div class="card-header"><span class="card-title">${I.folder} Bước 2: Dự Án &amp; Tải Lên / Chọn Video Thực Tế</span></div>
            <div class="flex-col" style="gap:12px">
              <div class="form-group">
                <label class="form-label" for="new-job-project">Dự án lưu trữ <span class="required">*</span></label>
                <select class="form-select" id="new-job-project" required aria-required="true">
                  ${activeProjects.length === 0 ? '<option value="">— Chưa có dự án nào —</option>' : ''}
                  ${activeProjects.map(p => `<option value="${p.id}" ${p.id === defaultProject ? 'selected' : ''}>${p.name} (v${p.version})</option>`).join('')}
                </select>
              </div>

              <!-- Khu vực kéo thả hoặc chọn file .mp4 từ máy tính -->
              <div>
                <label class="form-label mb-2" style="display:block">Tải Video MP4 mới từ máy tính (Qua cổng HTTPS :443) hoặc chọn Video bên dưới</label>
                <div class="upload-dropzone" id="studio-upload-dropzone">
                  <div>
                    <div style="font-size:12px;font-weight:700;color:var(--teal)">📤 Nhấn để chọn file .MP4 hoặc kéo thả video vào đây</div>
                    <div style="font-size:11px;color:var(--txt-3);margin-top:2px" id="upload-status-text">Video tải lên sẽ hiển thị ngay vào khung Preview bên phải để bạn kéo chọn vùng Blur.</div>
                  </div>
                  <span class="btn btn-secondary btn-sm">Chọn MP4…</span>
                  <input type="file" id="studio-file-input" accept="video/mp4,video/*" class="hidden" />
                </div>
              </div>

              <div class="form-group">
                <label class="form-label" for="new-job-input">File Video Đầu Vào (UUID Đã Xác Minh SHA-256) <span class="required">*</span></label>
                <input class="form-input font-mono" id="new-job-input" type="text"
                  placeholder="Ví dụ: 35326dd1-1211-41bf-937a-dca209c6c897"
                  value="${state.isMock ? 'f5d34973-487e-4794-be6b-ff927eb83218' : ''}"
                  aria-describedby="input-hint" />
                <div id="verified-files-picker" class="file-pick-grid"></div>
                <div class="form-error hidden" id="input-error">${I.alert} Cần ít nhất 1 UUID hợp lệ (36 ký tự).</div>
              </div>
            </div>
          </div>

          <div class="card">
            <div class="card-header"><span class="card-title">${I.cog} Bước 3: Đa Cấu Hình Chi Tiết (Khung Hình · Giọng Đọc · Tọa Độ Blur · Chạy Chữ)</span></div>
            <div id="dynamic-override-container"></div>
          </div>
        </div>

        <!-- Cột Phải: KHUNG VIDEO THẬT + VÙNG CHỌN BLUR KÉO THẢ THỦ CÔNG + PRESET + JSON -->
        <div class="flex-col" style="gap:16px">
          <div class="card">
            <div class="card-header">
              <span class="card-title">${I.film} Khung Video Thực Tế &amp; Kéo Thả Vùng Blur Thủ Công (2D ROI)</span>
              <span class="tag" id="studio-preview-res-badge" style="color:var(--teal)">720×1280</span>
            </div>

            <div class="studio-stage-outer">
              <!-- Khung 9:16 chứa thẻ <video> thật + Hộp Blur kéo thả 8 hướng -->
              <div class="studio-phone-interactive" id="studio-live-phone">
                <div class="real-frame-fallback" id="studio-video-fallback">
                  <div>🎬 Đang tải khung hình video thực tế...</div>
                  <small style="color:rgba(255,255,255,0.65);margin-top:4px">Kéo thả khung viền xanh bên dưới để che chính xác phụ đề hoặc logo</small>
                </div>
                <video id="studio-real-video" class="real-frame-video" playsinline muted loop preload="metadata"></video>

                <!-- Banner Hook cố định phía trên -->
                <div class="studio-phone-banner hidden" id="studio-phone-banner" style="position:absolute;top:10px;left:10px;right:10px;margin:0;z-index:5">REVIEW PHIM HAY</div>

                <!-- Badge hiển thị Voice / BGM / Flip -->
                <div class="studio-phone-badges" id="studio-phone-badges" style="z-index:5"></div>

                <!-- HỘP CHỌN VÙNG BLUR THỦ CÔNG TRÊN ẢNH THỰC TẾ (KÉO & ĐỔI KÍCH THƯỚC 8 ĐIỂM) -->
                <div class="custom-blur-rect" id="custom-blur-rect" title="Kéo để di chuyển vùng làm mờ, kéo các góc/cạnh để thay đổi kích thước">
                  <span class="custom-blur-label" id="custom-blur-label">BLUR: X:6% Y:72% (88×16%)</span>
                  <div class="blur-handle nw" data-handle="nw"></div>
                  <div class="blur-handle ne" data-handle="ne"></div>
                  <div class="blur-handle sw" data-handle="sw"></div>
                  <div class="blur-handle se" data-handle="se"></div>
                  <div class="blur-handle n"  data-handle="n"></div>
                  <div class="blur-handle s"  data-handle="s"></div>
                  <div class="blur-handle w"  data-handle="w"></div>
                  <div class="blur-handle e"  data-handle="e"></div>
                </div>

                <!-- Phụ đề chạy chữ đè lên trên -->
                <div class="studio-phone-sub hidden" id="studio-phone-sub" style="position:absolute;left:8px;right:8px;bottom:14px;margin:0;z-index:7">
                  <span class="marquee-inner" id="studio-phone-sub-text">Phụ đề chạy chữ tự động...</span>
                </div>
              </div>

              <!-- Thanh tua khung hình video thực tế (Scrubber) để tìm đúng đoạn có chữ/logo -->
              <div class="frame-scrubber-bar">
                <button type="button" class="btn btn-secondary btn-sm" id="btn-toggle-preview-play" style="padding:3px 8px;font-size:11px">▶ Phát</button>
                <input type="range" id="studio-video-scrubber" min="0" max="100" step="0.1" value="0" style="flex:1;accent-color:var(--teal)" title="Tua đến khung hình có phụ đề/logo để căn chỉnh vùng Blur" />
                <span class="font-mono text-muted" id="studio-video-time" style="font-size:10px;min-width:68px;text-align:right">0.0s / 0.0s</span>
              </div>

              <!-- Nút chọn nhanh vị trí Blur mẫu -->
              <div class="blur-preset-bar">
                <button type="button" class="blur-preset-btn" data-box-preset="sub_bottom">🎯 Phụ đề đáy (6%, 72%, 88×16%)</button>
                <button type="button" class="blur-preset-btn" data-box-preset="sub_high">🔼 Phụ đề cao (8%, 62%, 84×16%)</button>
                <button type="button" class="blur-preset-btn" data-box-preset="logo_tr">🏷 Logo phải trên (66%, 4%, 28×12%)</button>
                <button type="button" class="blur-preset-btn" data-box-preset="logo_tl">🏷 Logo trái trên (6%, 4%, 28×12%)</button>
                <button type="button" class="blur-preset-btn" data-box-preset="center_watermark">💧 Giữa khung (15%, 42%, 70×16%)</button>
              </div>
            </div>
            <p class="form-hint mt-2" style="text-align:center">
              💡 <b>Mẹo:</b> Dùng thanh trượt tua video đến đúng cảnh có phụ đề tiếng Trung hoặc logo, sau đó <b>dùng chuột kéo trực tiếp khung viền xanh</b> trên video để che khít 100%.
            </p>
          </div>

          <div class="card">
            <div class="card-header"><span class="card-title">${I.cpu} Bước 4: Bộ Cấu Hình Preset Gốc (Registry 1.0.0)</span></div>
            <div id="preset-list" class="flex-col" style="gap:8px">
              ${state.presets.map(p => `
                <label class="preset-option ${p.id === defaultPreset?.id ? 'selected-card' : ''}" style="cursor:pointer;border:1px solid var(--border);border-radius:10px;padding:10px 12px;display:flex;align-items:flex-start;gap:10px;transition:all .18s;${!p.available ? 'opacity:.55;' : ''}">
                  <input type="radio" name="preset" value="${p.id}" data-version="${p.version}"
                    ${p.id === defaultPreset?.id ? 'checked' : ''}
                    ${!p.available ? 'disabled' : ''}
                    style="margin-top:3px;accent-color:var(--teal)">
                  <div style="flex:1">
                    <div style="font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:space-between;gap:6px">
                      <span>${p.label}</span>
                      ${p.available ? `<span class="chip succeeded" style="font-size:9px">Sẵn sàng</span>` : `<span class="chip disabled" style="font-size:9px">Chờ GPU</span>`}
                    </div>
                    <div style="font-size:10px;color:var(--txt-3);margin-top:2px">
                      ID: <code style="color:var(--teal)">${p.id}</code> · Pipeline: ${(p.modules || []).join(' → ')}
                    </div>
                  </div>
                </label>
              `).join('')}
            </div>
          </div>

          <div class="card">
            <div class="card-header">
              <span class="card-title">${I.log} Gói Tin JSON Gửi Hàng Đợi (Bao gồm tọa độ Custom Blur 2D)</span>
              <span class="tag" style="color:var(--teal);border-color:rgba(45,212,191,0.3)">POST /api/v1/jobs</span>
            </div>
            <pre id="live-job-payload-json" class="json-code-box"></pre>
          </div>
        </div>
      </div>

      <!-- Summary + submit -->
      <div class="card mt-4" id="job-summary">
        <div class="card-header"><span class="card-title">${I.check} Bước 5: Xác Nhận Đa Cấu Hình &amp; Đẩy Vào Hàng Đợi Render</span></div>
        <div id="summary-body" class="dl-grid"></div>
        <div id="form-submit-error" class="form-error hidden mt-3"></div>
        <div class="modal-footer" style="padding:14px 0 0">
          <button type="submit" class="btn btn-primary btn-lg" id="btn-submit-job" aria-describedby="form-submit-error">
            ${I.play} Xếp vào hàng đợi &amp; Render Vùng Blur Đã Chọn
          </button>
        </div>
      </div>
    </form>
  `;

  $('btn-cancel-job')?.addEventListener('click', () =>
    state.projectId ? navigate('project-detail') : navigate('overview'));
  $('btn-go-channels-view')?.addEventListener('click', () => navigate('channels'));

  const VOICE_LABELS = {
    original: '🔊 Giữ nguyên âm thanh gốc',
    vi_female_north_ngochuyen: '🎙 Nữ Miền Bắc — Ngọc Huyền (VieNeu/Edge)',
    vi_male_north_minhquang: '🎙 Nam Miền Bắc — Minh Quang (Thuyết minh)',
    vi_female_south_thaovy: '🎙 Nữ Miền Nam — Thảo Vy (Kể chuyện/Chill)',
    vi_male_review_tram: '🎙 Nam Trầm Review Phim (Cấu hình 2)',
    wuby_clone_v2: '✨ Wuby AI Voice Clone v2 (Giọng mẫu độc quyền)',
    omnivoice_auto: '🤖 OmniVoice Zero-Shot Auto Dubbing',
  };

  const BLUR_LABELS = {
    none: 'Không làm mờ phụ đề',
    gaussian_box: 'Gaussian Box Blur (Làm mờ mịn vùng chọn 2D)',
    feather_dark: 'Feather Dark Box (Phủ mờ tối vùng chọn 2D)',
    ai_inpaint: 'AI Smart Inpaint (Xoá chữ giữ nền vùng chọn 2D)',
  };

  const SUB_STYLE_LABELS = {
    none: 'Tắt phụ đề chạy chữ',
    karaoke_pop: '🎤 Karaoke Pop TikTok (Nhảy chữ đổi màu)',
    review_yellow_box: '🎬 Hộp Vàng Viền Đen (Chuẩn Review Phim)',
    neon_glow: '✨ Neon Glow (Chữ phát sáng nổi bật)',
    minimal_white: '📝 Minimal White (Trắng thanh lịch)',
  };

  function getSchemaProps(preset) {
    if (!preset || !preset.override_schema) return {};
    const raw = preset.override_schema.properties || preset.override_schema;
    if (!raw || typeof raw !== 'object') return {};
    const clean = {};
    for (const [k, v] of Object.entries(raw)) {
      if (!['type', 'properties', 'additionalProperties', 'required', 'title'].includes(k) || (k === 'title' && typeof v === 'object')) {
        clean[k] = v;
      }
    }
    return clean;
  }

  function collectCurrentOverrides(preset) {
    const schema = getSchemaProps(preset);
    if (!schema.width) return {};
    const hPct = parseInt($('override-blur-h')?.value || $('override-blur-height')?.value || 16, 10);
    return {
      width: parseInt($('override-width')?.value || 720, 10),
      height: parseInt($('override-height')?.value || 1280, 10),
      fit_mode: $('override-fit-mode')?.value || 'contain',
      voice_id: $('override-voice-id')?.value || 'original',
      voice_speed: parseFloat($('override-voice-speed')?.value || '1.0'),
      keep_original_audio: Boolean($('override-keep-audio')?.checked ?? true),
      bgm_style: $('override-bgm-style')?.value || 'none',
      blur_subtitle: Boolean($('override-blur-sub')?.checked ?? true),
      blur_mode: $('override-blur-mode')?.value || 'gaussian_box',
      blur_height_pct: hPct,
      blur_strength: parseInt($('override-blur-strength')?.value || 20, 10),
      blur_x_pct: parseInt($('override-blur-x')?.value ?? 6, 10),
      blur_y_pct: parseInt($('override-blur-y')?.value ?? 72, 10),
      blur_w_pct: parseInt($('override-blur-w')?.value ?? 88, 10),
      blur_h_pct: hPct,
      channel_id: state.selectedChannelId || 'ch_custom_studio',
      subtitle_style: $('override-sub-style')?.value || 'none',
      banner_text: ($('override-banner-text')?.value || '').trim(),
      marquee_text: ($('override-marquee-text')?.value || '').trim(),
      text_position: $('override-text-pos')?.value || 'bottom',
      mirror_flip: Boolean($('override-mirror')?.checked ?? false),
      color_grade: $('override-color-grade')?.value || 'natural',
    };
  }

  function updateLivePhonePreview(ov) {
    const videoEl = $('studio-real-video');
    const banner = $('studio-phone-banner');
    const blurRect = $('custom-blur-rect');
    const blurLbl = $('custom-blur-label');
    const subBox = $('studio-phone-sub');
    const subText = $('studio-phone-sub-text');
    const badges = $('studio-phone-badges');
    const resBadge = $('studio-preview-res-badge');
    if (!videoEl || !blurRect) return;

    if (resBadge) resBadge.textContent = `${ov.width || 720}×${ov.height || 1280} · ${ov.fit_mode || 'contain'}`;

    // Áp dụng fit_mode trực tiếp lên video thật
    videoEl.style.objectFit = ov.fit_mode === 'cover' ? 'cover' : 'contain';

    // Mirror + Color grade trên video thật
    let filterStr = '';
    if (ov.color_grade === 'cinematic_warm') filterStr = 'sepia(0.18) saturate(1.25) contrast(1.08)';
    else if (ov.color_grade === 'film_contrast') filterStr = 'contrast(1.28) saturate(0.9)';
    else if (ov.color_grade === 'vibrant_tiktok') filterStr = 'saturate(1.45) contrast(1.12)';
    else if (ov.color_grade === 'noir_bw') filterStr = 'grayscale(1) contrast(1.25)';
    videoEl.style.filter = filterStr;
    videoEl.style.transform = ov.mirror_flip ? 'scaleX(-1)' : 'none';

    // Banner Hook
    if (ov.banner_text) {
      banner.textContent = ov.banner_text;
      banner.classList.remove('hidden');
    } else {
      banner.classList.add('hidden');
    }

    // Vùng chọn Custom Blur 2D trên khung hình thực tế
    if (ov.blur_subtitle && ov.blur_mode !== 'none') {
      const bx = Math.min(Math.max(ov.blur_x_pct ?? 6, 0), 94);
      const by = Math.min(Math.max(ov.blur_y_pct ?? 72, 0), 94);
      const bw = Math.min(Math.max(ov.blur_w_pct ?? 88, 6), 100 - bx);
      const bh = Math.min(Math.max(ov.blur_h_pct ?? 16, 6), 100 - by);
      const sigma = Math.round((ov.blur_strength || 20) * 0.55);

      blurRect.style.left = `${bx}%`;
      blurRect.style.top = `${by}%`;
      blurRect.style.width = `${bw}%`;
      blurRect.style.height = `${bh}%`;
      blurRect.style.backdropFilter = `blur(${sigma}px)`;
      blurRect.style.webkitBackdropFilter = `blur(${sigma}px)`;
      blurRect.className = `custom-blur-rect ${ov.blur_mode || 'gaussian_box'}`;
      if (blurLbl) {
        blurLbl.textContent = `BLUR (${bx}%, ${by}% · ${bw}×${bh}%)`;
      }
      blurRect.classList.remove('hidden');
    } else {
      blurRect.classList.add('hidden');
    }

    // Running text / Subtitle style
    if ((ov.subtitle_style && ov.subtitle_style !== 'none') || ov.marquee_text) {
      subBox.classList.remove('hidden');
      subText.textContent = ov.marquee_text || '🔥 Phụ đề chạy chữ tự động theo giọng đọc AI...';
      if (ov.text_position === 'top') {
        subBox.style.top = '48px';
        subBox.style.bottom = 'auto';
      } else if (ov.text_position === 'middle') {
        subBox.style.top = '46%';
        subBox.style.bottom = 'auto';
      } else {
        subBox.style.top = 'auto';
        subBox.style.bottom = '14px';
      }
      if (ov.subtitle_style === 'review_yellow_box') {
        subBox.style.background = 'rgba(0,0,0,0.88)';
        subBox.style.color = '#facc15';
        subBox.style.border = '1px solid #facc15';
      } else if (ov.subtitle_style === 'neon_glow') {
        subBox.style.background = 'rgba(8,15,28,0.65)';
        subBox.style.color = '#38bdf8';
        subBox.style.border = '1px solid rgba(56,189,248,0.5)';
      } else if (ov.subtitle_style === 'karaoke_pop') {
        subBox.style.background = 'rgba(0,0,0,0.65)';
        subBox.style.color = '#2dd4bf';
        subBox.style.border = '1px solid rgba(45,212,191,0.5)';
      } else {
        subBox.style.background = 'rgba(0,0,0,0.55)';
        subBox.style.color = '#ffffff';
        subBox.style.border = '1px solid rgba(255,255,255,0.2)';
      }
    } else {
      subBox.classList.add('hidden');
    }

    // Feature badges
    const pillList = [];
    if (ov.voice_id && ov.voice_id !== 'original') pillList.push(`🎙 ${ov.voice_id.replace('vi_', '').slice(0, 14)} (${ov.voice_speed || 1}x)`);
    else pillList.push('🔊 Audio Gốc');
    if (ov.bgm_style && ov.bgm_style !== 'none') pillList.push(`🎵 ${ov.bgm_style}`);
    if (ov.mirror_flip) pillList.push('🪞 Flip');
    badges.innerHTML = pillList.map(p => `<span class="studio-mini-badge">${p}</span>`).join('');
  }

  function updateOverrideFields(preset, channelOverride = null) {
    const container = $('dynamic-override-container');
    if (!container) return;

    const schema = getSchemaProps(preset);
    if (Object.keys(schema).length === 0) {
      container.innerHTML = `<p class="form-hint">Preset <b>${preset?.id || ''}</b> chỉ chạy bước kiểm tra thông số gốc (<code>media.probe</code>) và xuất <code>probe.json</code>.</p>`;
      return;
    }

    const baseCfg = preset?.default_config || {
      width: 720, height: 1280, fit_mode: 'contain',
      voice_id: 'original', voice_speed: 1.0, keep_original_audio: true, bgm_style: 'none',
      blur_subtitle: true, blur_mode: 'gaussian_box', blur_height_pct: 16, blur_strength: 20,
      blur_x_pct: 6, blur_y_pct: 72, blur_w_pct: 88, blur_h_pct: 16,
      subtitle_style: 'review_yellow_box', banner_text: '', marquee_text: '', text_position: 'bottom',
      mirror_flip: false, color_grade: 'natural',
    };

    const ch = channelOverride || CHANNELS_8.find(c => c.id === state.selectedChannelId);
    const d = {
      ...baseCfg,
      voice_id: ch?.voice_id || baseCfg.voice_id || 'original',
      banner_text: ch?.banner_text !== undefined ? ch.banner_text : (baseCfg.banner_text || ''),
      marquee_text: ch?.marquee_text !== undefined ? ch.marquee_text : (baseCfg.marquee_text || ''),
      blur_x_pct: ch?.blur_box?.x ?? baseCfg.blur_x_pct ?? 6,
      blur_y_pct: ch?.blur_box?.y ?? baseCfg.blur_y_pct ?? 72,
      blur_w_pct: ch?.blur_box?.w ?? baseCfg.blur_w_pct ?? 88,
      blur_h_pct: ch?.blur_box?.h ?? baseCfg.blur_h_pct ?? 16,
      blur_subtitle: true,
      blur_mode: baseCfg.blur_mode === 'none' ? 'gaussian_box' : (baseCfg.blur_mode || 'gaussian_box'),
    };

    const profiles = [
      { w: 360, h: 640, title: 'SD Nhanh (9:16)', sub: '360 × 640 px' },
      { w: 720, h: 1280, title: 'HD Reels/TikTok', sub: '720 × 1280 px' },
      { w: 1080, h: 1920, title: 'Full HD Studio', sub: '1080 × 1920 px' },
    ];

    container.innerHTML = `
      <!-- C. VÙNG CHỌN BLUR 2D THỦ CÔNG TRÊN ẢNH THỰC TẾ (ĐẶT LÊN ĐẦU ĐỂ TIỆN THAO TÁC) -->
      <div class="cfg-section-box" style="border-color:rgba(45,212,191,0.45)">
        <div class="cfg-section-title">
          <span>🎯 A. Vùng Chọn Làm Mờ Thủ Công Trên Video Thật (Custom 2D Blur Box)</span>
          <span class="tag" style="color:var(--teal)">Kéo thả trực tiếp</span>
        </div>
        <label class="toggle-row mb-2">
          <span>Bật làm mờ vùng chọn 2D trên khung hình (Che phụ đề gốc / Logo / Watermark)</span>
          <input type="checkbox" id="override-blur-sub" ${d.blur_subtitle ? 'checked' : ''} />
        </label>
        <div class="grid-2" style="gap:10px;margin-bottom:10px">
          <div class="form-group">
            <label class="form-label" for="override-blur-mode">Thuật toán xử lý vùng chọn</label>
            <select class="form-select" id="override-blur-mode">
              ${Object.entries(BLUR_LABELS).map(([k, lbl]) => `<option value="${k}" ${k === (d.blur_mode || 'gaussian_box') ? 'selected' : ''}>${lbl}</option>`).join('')}
            </select>
          </div>
          <div class="form-group">
            <label class="form-label" for="override-blur-strength">Độ mờ Gaussian (Sigma): <b id="lbl-blur-s">${d.blur_strength || 20}</b></label>
            <input type="range" id="override-blur-strength" min="5" max="40" step="1" value="${d.blur_strength || 20}" style="accent-color:var(--teal);width:100%" />
          </div>
        </div>
        <div class="grid-2" style="gap:10px">
          <div class="form-group">
            <label class="form-label" for="override-blur-x">Toạ độ ngang X (Trái → Phải): <b id="lbl-blur-x">${d.blur_x_pct}%</b></label>
            <input type="range" id="override-blur-x" min="0" max="90" step="1" value="${d.blur_x_pct}" style="accent-color:var(--teal);width:100%" />
          </div>
          <div class="form-group">
            <label class="form-label" for="override-blur-y">Toạ độ dọc Y (Trên → Dưới): <b id="lbl-blur-y">${d.blur_y_pct}%</b></label>
            <input type="range" id="override-blur-y" min="0" max="90" step="1" value="${d.blur_y_pct}" style="accent-color:var(--teal);width:100%" />
          </div>
          <div class="form-group">
            <label class="form-label" for="override-blur-w">Chiều rộng vùng Blur (Width): <b id="lbl-blur-w">${d.blur_w_pct}%</b></label>
            <input type="range" id="override-blur-w" min="5" max="100" step="1" value="${d.blur_w_pct}" style="accent-color:var(--teal);width:100%" />
          </div>
          <div class="form-group">
            <label class="form-label" for="override-blur-h">Chiều cao vùng Blur (Height): <b id="lbl-blur-h">${d.blur_h_pct}%</b></label>
            <input type="range" id="override-blur-h" min="5" max="60" step="1" value="${d.blur_h_pct}" style="accent-color:var(--teal);width:100%" />
          </div>
        </div>
      </div>

      <!-- B. GIỌNG ĐỌC AI & ÂM THANH -->
      <div class="cfg-section-box">
        <div class="cfg-section-title"><span>🎙 B. Giọng Đọc AI (TTS Voice) &amp; Nhạc Nền</span></div>
        <div class="form-group mb-2">
          <label class="form-label" for="override-voice-id">Chọn Giọng Đọc Thuyết Minh / Lồng Tiếng</label>
          <select class="form-select" id="override-voice-id">
            ${Object.entries(VOICE_LABELS).map(([k, lbl]) => `<option value="${k}" ${k === (d.voice_id || 'original') ? 'selected' : ''}>${lbl}</option>`).join('')}
          </select>
        </div>
        <div class="grid-2" style="gap:10px;margin-bottom:10px">
          <div class="form-group">
            <label class="form-label" for="override-voice-speed">Tốc độ giọng đọc: <b id="lbl-voice-speed">${d.voice_speed || 1.0}x</b></label>
            <input type="range" id="override-voice-speed" min="0.8" max="1.4" step="0.05" value="${d.voice_speed || 1.0}" style="accent-color:var(--teal);width:100%" />
          </div>
          <div class="form-group">
            <label class="form-label" for="override-bgm-style">Nhạc nền trộn tự động (BGM)</label>
            <select class="form-select" id="override-bgm-style">
              <option value="none" ${d.bgm_style === 'none' ? 'selected' : ''}>Không chèn nhạc nền</option>
              <option value="cinematic_tension" ${d.bgm_style === 'cinematic_tension' ? 'selected' : ''}>Kịch tính Review Phim (Tension)</option>
              <option value="chill_lofi" ${d.bgm_style === 'chill_lofi' ? 'selected' : ''}>Chill Lo-Fi nhẹ nhàng</option>
              <option value="upbeat_viral" ${d.bgm_style === 'upbeat_viral' ? 'selected' : ''}>Sôi động Xu hướng (Upbeat Viral)</option>
              <option value="emotional_piano" ${d.bgm_style === 'emotional_piano' ? 'selected' : ''}>Piano cảm xúc sâu lắng</option>
            </select>
          </div>
        </div>
        <label class="toggle-row">
          <span>🔊 Giữ âm thanh môi trường gốc (Tự động giảm âm khi có giọng đọc)</span>
          <input type="checkbox" id="override-keep-audio" ${d.keep_original_audio !== false ? 'checked' : ''} />
        </label>
      </div>

      <!-- C. CHẠY CHỮ KARAOKE & BANNER HOOK -->
      <div class="cfg-section-box">
        <div class="cfg-section-title"><span>💬 C. Chạy Chữ Phụ Đề Động &amp; Tiêu Đề Banner Hook</span></div>
        <div class="grid-2" style="gap:10px;margin-bottom:10px">
          <div class="form-group">
            <label class="form-label" for="override-sub-style">Kiểu chạy chữ / Phụ đề</label>
            <select class="form-select" id="override-sub-style">
              ${Object.entries(SUB_STYLE_LABELS).map(([k, lbl]) => `<option value="${k}" ${k === (d.subtitle_style || 'none') ? 'selected' : ''}>${lbl}</option>`).join('')}
            </select>
          </div>
          <div class="form-group">
            <label class="form-label" for="override-text-pos">Vị trí hiển thị phụ đề</label>
            <select class="form-select" id="override-text-pos">
              <option value="bottom" ${d.text_position === 'bottom' ? 'selected' : ''}>Phía dưới (Đè lên vùng Blur Sub)</option>
              <option value="middle" ${d.text_position === 'middle' ? 'selected' : ''}>Chính giữa khung hình</option>
              <option value="top" ${d.text_position === 'top' ? 'selected' : ''}>Phía trên</option>
            </select>
          </div>
        </div>
        <div class="form-group mb-2">
          <label class="form-label" for="override-banner-text">Tiêu đề Hook cố định trên đầu video (Banner Text)</label>
          <input class="form-input" id="override-banner-text" type="text" maxlength="120" value="${d.banner_text || ''}" placeholder="Ví dụ: TẬP CUỐI: CÁI KẾT KHÔNG NGỜ..." />
        </div>
        <div class="form-group">
          <label class="form-label" for="override-marquee-text">Nội dung chữ chạy ngang / Phụ đề nổi bật (Marquee / Sub Text)</label>
          <input class="form-input" id="override-marquee-text" type="text" maxlength="200" value="${d.marquee_text || ''}" placeholder="Nhập dòng chữ chạy hoặc lời bình hiển thị trên video..." />
        </div>
      </div>

      <!-- D. KHUNG HÌNH & BỐ CỤC -->
      <div class="cfg-section-box" style="margin-bottom:0">
        <div class="cfg-section-title"><span>📐 D. Độ Phân Giải, Bố Cục 9:16 &amp; Màu Sắc</span></div>
        <div class="res-grid">
          ${profiles.map(pr => `
            <button type="button" class="res-card ${(d.width || 720) === pr.w && (d.height || 1280) === pr.h ? 'active' : ''}" data-res-w="${pr.w}" data-res-h="${pr.h}">
              <div class="res-card-title">${pr.title}</div>
              <div class="res-card-sub">${pr.sub}</div>
            </button>
          `).join('')}
        </div>
        <div class="grid-2" style="gap:10px;margin-bottom:10px">
          <div class="form-group">
            <label class="form-label" for="override-width">Chiều rộng (Width)</label>
            <select class="form-select" id="override-width">
              ${[360, 720, 1080].map(w => `<option value="${w}" ${w === (d.width || 720) ? 'selected' : ''}>${w} px</option>`).join('')}
            </select>
          </div>
          <div class="form-group">
            <label class="form-label" for="override-height">Chiều cao (Height)</label>
            <select class="form-select" id="override-height">
              ${[640, 1280, 1920].map(h => `<option value="${h}" ${h === (d.height || 1280) ? 'selected' : ''}>${h} px (Dọc 9:16)</option>`).join('')}
            </select>
          </div>
        </div>
        <div class="grid-2" style="gap:10px;margin-bottom:10px">
          <div class="form-group">
            <label class="form-label" for="override-fit-mode">Chế độ khung hình (Fit Mode)</label>
            <select class="form-select" id="override-fit-mode">
              <option value="contain" ${d.fit_mode === 'contain' ? 'selected' : ''}>Viền đen chuẩn (Contain)</option>
              <option value="blur_bg" ${d.fit_mode === 'blur_bg' ? 'selected' : ''}>Nền mờ Gaussian 9:16 (Blur BG)</option>
              <option value="cover" ${d.fit_mode === 'cover' ? 'selected' : ''}>Cắt tràn viền 9:16 (Cover Crop)</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label" for="override-color-grade">Bộ lọc màu (Color Grade)</label>
            <select class="form-select" id="override-color-grade">
              <option value="natural" ${d.color_grade === 'natural' ? 'selected' : ''}>Màu gốc tự nhiên (Natural)</option>
              <option value="cinematic_warm" ${d.color_grade === 'cinematic_warm' ? 'selected' : ''}>Cinematic Ấm (Warm Film)</option>
              <option value="film_contrast" ${d.color_grade === 'film_contrast' ? 'selected' : ''}>Tương phản điện ảnh (Review Black)</option>
              <option value="vibrant_tiktok" ${d.color_grade === 'vibrant_tiktok' ? 'selected' : ''}>Rực rỡ TikTok/Reels (Vibrant)</option>
              <option value="noir_bw" ${d.color_grade === 'noir_bw' ? 'selected' : ''}>Đen trắng nghệ thuật (Noir B&amp;W)</option>
            </select>
          </div>
        </div>
        <label class="toggle-row">
          <span>🪞 Lật gương ngang video (Mirror Flip chống bản quyền)</span>
          <input type="checkbox" id="override-mirror" ${d.mirror_flip ? 'checked' : ''} />
        </label>
      </div>
    `;

    const syncAllControls = () => {
      const w = parseInt($('override-width')?.value || 720, 10);
      const h = parseInt($('override-height')?.value || 1280, 10);
      container.querySelectorAll('[data-res-w]').forEach(btn => {
        btn.classList.toggle('active', parseInt(btn.dataset.resW, 10) === w && parseInt(btn.dataset.resH, 10) === h);
      });
      if ($('lbl-voice-speed')) $('lbl-voice-speed').textContent = `${$('override-voice-speed').value}x`;
      if ($('lbl-blur-x')) $('lbl-blur-x').textContent = `${$('override-blur-x').value}%`;
      if ($('lbl-blur-y')) $('lbl-blur-y').textContent = `${$('override-blur-y').value}%`;
      if ($('lbl-blur-w')) $('lbl-blur-w').textContent = `${$('override-blur-w').value}%`;
      if ($('lbl-blur-h')) $('lbl-blur-h').textContent = `${$('override-blur-h').value}%`;
      if ($('lbl-blur-s')) $('lbl-blur-s').textContent = `${$('override-blur-strength').value}`;
      updateSummaryTextOnly();
    };

    container.querySelectorAll('input, select').forEach(el => {
      el.addEventListener('input', syncAllControls);
      el.addEventListener('change', syncAllControls);
    });
    $('override-blur-sub')?.addEventListener('change', e => {
      if (e.target.checked && $('override-blur-mode')?.value === 'none') {
        $('override-blur-mode').value = 'gaussian_box';
      } else if (!e.target.checked && $('override-blur-mode')) {
        $('override-blur-mode').value = 'none';
      }
      syncAllControls();
    });
    $('override-blur-mode')?.addEventListener('change', e => {
      if ($('override-blur-sub')) {
        $('override-blur-sub').checked = e.target.value !== 'none';
      }
      syncAllControls();
    });
    container.querySelectorAll('[data-res-w]').forEach(btn => {
      btn.addEventListener('click', () => {
        if ($('override-width')) $('override-width').value = btn.dataset.resW;
        if ($('override-height')) $('override-height').value = btn.dataset.resH;
        syncAllControls();
      });
    });
  }

  function setBlurBoxCoords(x, y, w, h) {
    const bx = Math.round(Math.min(Math.max(x, 0), 92));
    const by = Math.round(Math.min(Math.max(y, 0), 92));
    const bw = Math.round(Math.min(Math.max(w, 6), 100 - bx));
    const bh = Math.round(Math.min(Math.max(h, 6), 100 - by));
    if ($('override-blur-sub')) $('override-blur-sub').checked = true;
    if ($('override-blur-mode') && $('override-blur-mode').value === 'none') {
      $('override-blur-mode').value = 'gaussian_box';
    }
    if ($('override-blur-x')) $('override-blur-x').value = bx;
    if ($('override-blur-y')) $('override-blur-y').value = by;
    if ($('override-blur-w')) $('override-blur-w').value = bw;
    if ($('override-blur-h')) $('override-blur-h').value = bh;
    if ($('lbl-blur-x')) $('lbl-blur-x').textContent = `${bx}%`;
    if ($('lbl-blur-y')) $('lbl-blur-y').textContent = `${by}%`;
    if ($('lbl-blur-w')) $('lbl-blur-w').textContent = `${bw}%`;
    if ($('lbl-blur-h')) $('lbl-blur-h').textContent = `${bh}%`;
    updateSummaryTextOnly();
  }

  // Khởi tạo thao tác kéo thả & co giãn 8 góc/cạnh trên khung hình video thật
  function setupInteractiveBlurBox() {
    const phone = $('studio-live-phone');
    const rectEl = $('custom-blur-rect');
    if (!phone || !rectEl) return;

    let dragState = null;

    rectEl.addEventListener('pointerdown', e => {
      e.preventDefault();
      e.stopPropagation();
      const handle = e.target.dataset?.handle || 'move';
      const stageRect = phone.getBoundingClientRect();
      dragState = {
        handle,
        startX: e.clientX,
        startY: e.clientY,
        stageW: stageRect.width || 270,
        stageH: stageRect.height || 480,
        initX: parseFloat($('override-blur-x')?.value ?? 6),
        initY: parseFloat($('override-blur-y')?.value ?? 72),
        initW: parseFloat($('override-blur-w')?.value ?? 88),
        initH: parseFloat($('override-blur-h')?.value ?? 16),
      };
      rectEl.setPointerCapture(e.pointerId);
    });

    rectEl.addEventListener('pointermove', e => {
      if (!dragState) return;
      e.preventDefault();
      const dxPct = ((e.clientX - dragState.startX) / dragState.stageW) * 100;
      const dyPct = ((e.clientY - dragState.startY) / dragState.stageH) * 100;

      let { initX: x, initY: y, initW: w, initH: h, handle } = dragState;
      if (handle === 'move') {
        x = Math.min(Math.max(x + dxPct, 0), 100 - w);
        y = Math.min(Math.max(y + dyPct, 0), 100 - h);
      } else {
        if (handle.includes('e')) w = Math.min(Math.max(w + dxPct, 6), 100 - x);
        if (handle.includes('s')) h = Math.min(Math.max(h + dyPct, 6), 100 - y);
        if (handle.includes('w')) {
          const nx = Math.min(Math.max(x + dxPct, 0), x + w - 6);
          w = w + (x - nx);
          x = nx;
        }
        if (handle.includes('n')) {
          const ny = Math.min(Math.max(y + dyPct, 0), y + h - 6);
          h = h + (y - ny);
          y = ny;
        }
      }
      setBlurBoxCoords(x, y, w, h);
    });

    const endDrag = e => {
      if (!dragState) return;
      try { rectEl.releasePointerCapture(e.pointerId); } catch {}
      dragState = null;
    };
    rectEl.addEventListener('pointerup', endDrag);
    rectEl.addEventListener('pointercancel', endDrag);

    // Các nút chọn nhanh vùng Blur mẫu
    document.querySelectorAll('[data-box-preset]').forEach(btn => {
      btn.addEventListener('click', () => {
        const key = btn.dataset.boxPreset;
        if (key === 'sub_bottom') setBlurBoxCoords(6, 72, 88, 16);
        else if (key === 'sub_high') setBlurBoxCoords(8, 62, 84, 16);
        else if (key === 'logo_tr') setBlurBoxCoords(66, 4, 28, 12);
        else if (key === 'logo_tl') setBlurBoxCoords(6, 4, 28, 12);
        else if (key === 'center_watermark') setBlurBoxCoords(15, 42, 70, 16);
      });
    });
  }

  // Điều khiển phát & tua khung hình video thực tế
  function setupRealVideoScrubber() {
    const videoEl = $('studio-real-video');
    const scrubber = $('studio-video-scrubber');
    const timeLbl = $('studio-video-time');
    const playBtn = $('btn-toggle-preview-play');
    const fallback = $('studio-video-fallback');
    if (!videoEl || !scrubber) return;

    const updateTimeUI = () => {
      const dur = videoEl.duration || 0;
      const cur = videoEl.currentTime || 0;
      if (dur > 0) {
        scrubber.max = dur.toFixed(2);
        scrubber.value = cur.toFixed(2);
        if (timeLbl) timeLbl.textContent = `${cur.toFixed(1)}s / ${dur.toFixed(1)}s`;
      }
    };

    videoEl.addEventListener('loadeddata', () => {
      if (fallback) fallback.classList.add('hidden');
      updateTimeUI();
    });
    videoEl.addEventListener('timeupdate', updateTimeUI);

    scrubber.addEventListener('input', () => {
      videoEl.pause();
      if (playBtn) playBtn.textContent = '▶ Phát';
      videoEl.currentTime = parseFloat(scrubber.value || '0');
      updateTimeUI();
    });

    playBtn?.addEventListener('click', () => {
      if (videoEl.paused) {
        videoEl.play().catch(() => {});
        playBtn.textContent = '⏸ Dừng';
      } else {
        videoEl.pause();
        playBtn.textContent = '▶ Phát';
      }
    });
  }

  async function loadRealVideoIntoStage(fileId, localBlobUrl = null) {
    const videoEl = $('studio-real-video');
    const fallback = $('studio-video-fallback');
    if (!videoEl) return;

    if (localBlobUrl) {
      videoEl.src = localBlobUrl;
      videoEl.load();
      if (fallback) fallback.classList.add('hidden');
      return;
    }

    if (!fileId || state.isMock || !window.CC_API.fetchFileBlobUrl) return;
    try {
      const blobUrl = await window.CC_API.fetchFileBlobUrl(fileId);
      if (blobUrl) {
        videoEl.src = blobUrl;
        videoEl.load();
        if (fallback) fallback.classList.add('hidden');
      }
    } catch {
      // Giữ nguyên khung nền nếu chưa tải được blob
    }
  }

  function updateSummaryTextOnly() {
    const projSel   = $('new-job-project');
    const presetSel = document.querySelector('input[name="preset"]:checked');
    const inputVal  = $('new-job-input')?.value.trim() || '';

    const projName  = projSel?.options[projSel.selectedIndex]?.text || '—';
    const presetId  = presetSel?.value || '—';
    const presetVer = presetSel?.dataset.version || '1.0.0';

    const preset = state.presets.find(p => p.id === presetId);
    const overridesObj = collectCurrentOverrides(preset);

    updateLivePhonePreview(overridesObj);

    const hasRender = Object.keys(overridesObj).length > 0;
    const blurDesc = overridesObj.blur_subtitle
      ? `${overridesObj.blur_mode} [X:${overridesObj.blur_x_pct}%, Y:${overridesObj.blur_y_pct}%, W:${overridesObj.blur_w_pct}%, H:${overridesObj.blur_h_pct}%]`
      : 'Tắt';
    const summaryText = hasRender
      ? `${overridesObj.width}×${overridesObj.height} (${overridesObj.fit_mode}) · Voice: ${overridesObj.voice_id} · Blur 2D: ${blurDesc}`
      : 'Chỉ kiểm tra thông số gốc (probe.json)';

    const chObj = CHANNELS_8.find(c => c.id === state.selectedChannelId);

    $('summary-body').innerHTML = `
      <span class="dl-label">Kênh Fanpage Đích</span><span class="dl-value"><b style="color:var(--teal)">${chObj ? chObj.name : 'Tự do'}</b></span>
      <span class="dl-label">Dự án lưu trữ</span><span class="dl-value">${projName}</span>
      <span class="dl-label">Preset Pipeline</span><span class="dl-value"><span class="tag" style="color:var(--teal)">${presetId}</span> (v${presetVer})</span>
      <span class="dl-label">Input Video UUID</span><span class="dl-value mono">${inputVal || '<em>Chưa chọn UUID</em>'}</span>
      <span class="dl-label">Vùng Blur &amp; Cấu hình</span><span class="dl-value mono" style="color:var(--teal)">${summaryText}</span>
    `;

    const previewEl = $('live-job-payload-json');
    if (previewEl) {
      previewEl.textContent = JSON.stringify({
        schema_version: '0.1.0-draft',
        project_id: projSel?.value || '',
        preset_id: presetId,
        preset_version: presetVer,
        input_refs: inputVal ? [inputVal] : [],
        overrides: overridesObj,
      }, null, 2);
    }

    document.querySelectorAll('[data-pick-file]').forEach(card => {
      card.classList.toggle('selected', card.dataset.pickFile === inputVal);
    });

    const disabled = !preset?.available || state.submitPending;
    $('btn-submit-job').disabled = disabled;
    if (preset && !preset.available) {
      $('btn-submit-job').innerHTML = `${I.alert} Preset chưa sẵn sàng trong registry`;
    } else {
      $('btn-submit-job').innerHTML = `${I.play} Xếp vào hàng đợi & Render Vùng Blur Đã Chọn`;
    }
  }

  function updateSummary(channelOverride = null) {
    const presetSel = document.querySelector('input[name="preset"]:checked');
    document.querySelectorAll('.preset-option').forEach(lbl => {
      const radio = lbl.querySelector('input[name="preset"]');
      lbl.classList.toggle('selected-card', Boolean(radio && radio.checked));
    });
    const preset = state.presets.find(p => p.id === (presetSel?.value || ''));
    updateOverrideFields(preset, channelOverride);
    updateSummaryTextOnly();
  }

  // Sự kiện chọn 1 trong 8 Kênh Fanpage trên thanh đầu trang
  document.querySelectorAll('[data-channel-id]').forEach(btn => {
    btn.addEventListener('click', () => {
      const chId = btn.dataset.channelId;
      state.selectedChannelId = chId;
      document.querySelectorAll('[data-channel-id]').forEach(b => b.classList.toggle('active', b.dataset.channelId === chId));
      const ch = CHANNELS_8.find(c => c.id === chId);
      if ($('selected-channel-tag') && ch) $('selected-channel-tag').textContent = ch.name;
      if (ch) {
        const targetRadio = document.querySelector(`input[name="preset"][value="${ch.preset_id}"]`);
        if (targetRadio && !targetRadio.disabled) {
          targetRadio.checked = true;
        }
        updateSummary(ch);
        toast(`Đã nạp cấu hình & vùng Blur mẫu của ${ch.name}`, 'ok');
      }
    });
  });

  // Sự kiện Upload file .MP4 trực tiếp từ trình duyệt
  const dropzone = $('studio-upload-dropzone');
  const fileInput = $('studio-file-input');
  const uploadStatus = $('upload-status-text');

  async function handleFileUpload(file) {
    if (!file) return;
    const projId = $('new-job-project')?.value;
    if (!projId) {
      toast('Vui lòng chọn Dự án trước khi tải video lên.', 'warn');
      return;
    }
    // Hiển thị ngay video vừa chọn vào khung Preview để người dùng kéo khung Blur ngay lập tức!
    const localUrl = URL.createObjectURL(file);
    state.localVideoBlobUrl = localUrl;
    loadRealVideoIntoStage(null, localUrl);

    if (uploadStatus) uploadStatus.textContent = `Đang tải "${file.name}" (${window.ccUtil.formatBytes(file.size)}) lên máy chủ qua HTTPS :443...`;
    try {
      const uploaded = await window.CC_API.uploadProjectFile(projId, file);
      if ($('new-job-input')) $('new-job-input').value = uploaded.id;
      if (uploadStatus) uploadStatus.innerHTML = `<span style="color:var(--status-ok)">✔ Đã tải lên &amp; xác minh SHA-256: <code>${window.ccUtil.shortId(uploaded.id)}</code> (${window.ccUtil.formatBytes(uploaded.size_bytes)})</span>`;
      toast(`Đã tải video lên thành công! Hãy kéo khung Blur trên video.`, 'ok');
      await loadProjectVerifiedFiles(false);
      updateSummaryTextOnly();
    } catch (err) {
      const msg = err?.body?.error?.message || err?.message || 'Lỗi tải file video lên.';
      if (uploadStatus) uploadStatus.innerHTML = `<span style="color:var(--status-failed)">✖ ${msg}</span>`;
      toast(msg, 'err');
    }
  }

  dropzone?.addEventListener('click', () => fileInput?.click());
  fileInput?.addEventListener('change', e => {
    const f = e.target.files?.[0];
    if (f) handleFileUpload(f);
  });
  dropzone?.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('dragover'); });
  dropzone?.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
  dropzone?.addEventListener('drop', e => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    const f = e.dataTransfer?.files?.[0];
    if (f) handleFileUpload(f);
  });

  async function loadProjectVerifiedFiles(autoLoadStage = true) {
    const projId = $('new-job-project')?.value;
    const picker = $('verified-files-picker');
    if (!projId || !picker || !window.CC_API.getProjectFiles) return;
    try {
      const res = await window.CC_API.getProjectFiles(projId);
      const files = res.items || [];
      if (files.length === 0) {
        picker.innerHTML = '';
        return;
      }
      if (!$('new-job-input').value.trim()) {
        $('new-job-input').value = files[0].id;
      }
      const curVal = $('new-job-input').value.trim();
      picker.innerHTML = files.map((f, idx) => `
        <button type="button" class="file-pick-card ${f.id === curVal ? 'selected' : ''}" data-pick-file="${f.id}">
          <div class="file-pick-icon">${I.film}</div>
          <div style="flex:1;min-width:0">
            <div style="font-size:12px;font-weight:700;display:flex;align-items:center;gap:6px">
              <span>Video #${idx + 1} (${window.ccUtil.shortId(f.id)})</span>
              <span class="chip succeeded" style="font-size:9px;padding:1px 6px">Verified</span>
            </div>
            <div class="font-mono text-muted" style="font-size:10px;margin-top:2px">
              ${window.ccUtil.formatBytes(f.size_bytes)} · SHA256: ${(f.sha256 || '').slice(0, 10)}…
            </div>
          </div>
        </button>
      `).join('');
      picker.querySelectorAll('[data-pick-file]').forEach(btn => {
        btn.addEventListener('click', () => {
          $('new-job-input').value = btn.dataset.pickFile;
          updateSummaryTextOnly();
          loadRealVideoIntoStage(btn.dataset.pickFile);
        });
      });
      updateSummaryTextOnly();
      if (autoLoadStage && curVal) {
        loadRealVideoIntoStage(curVal);
      }
    } catch {
      picker.innerHTML = '';
    }
  }

  $('new-job-project')?.addEventListener('change', () => {
    updateSummaryTextOnly();
    loadProjectVerifiedFiles();
  });
  $('new-job-input')?.addEventListener('input', updateSummaryTextOnly);
  document.querySelectorAll('input[name="preset"]').forEach(r => r.addEventListener('change', () => updateSummary(null)));

  setupInteractiveBlurBox();
  setupRealVideoScrubber();
  updateSummary(activeChannel);
  loadProjectVerifiedFiles(true);

  // Submit
  $('new-job-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    if (state.submitPending) return;

    const projSel   = $('new-job-project');
    const presetSel = document.querySelector('input[name="preset"]:checked');
    const inputVal  = $('new-job-input')?.value.trim();

    let valid = true;
    if (!inputVal || !/^[0-9a-f-]{36}$/i.test(inputVal)) {
      $('new-job-input')?.classList.add('invalid');
      $('input-error')?.classList.remove('hidden');
      valid = false;
    } else {
      $('new-job-input')?.classList.remove('invalid');
      $('input-error')?.classList.add('hidden');
    }
    if (!valid) return;

    const preset = state.presets.find(p => p.id === presetSel.value);
    const overrides = collectCurrentOverrides(preset);

    const payload = {
      schema_version: '0.1.0-draft',
      project_id:     projSel.value,
      preset_id:      presetSel.value,
      preset_version: presetSel.dataset.version || '1.0.0',
      input_refs:     [inputVal],
      overrides:      overrides,
    };

    state.submitPending = true;
    $('btn-submit-job').disabled = true;
    $('btn-submit-job').innerHTML = `<span>Đang xếp vào hàng đợi PostgreSQL…</span>`;
    $('form-submit-error')?.classList.add('hidden');

    try {
      const job = await window.CC_API.createJob(payload);
      toast(`Đã xếp job #${window.ccUtil.shortId(job.id)} vào hàng đợi!`, 'ok');
      state.projectId = projSel.value;
      navigate('job-detail', { jobId: job.id });
    } catch(err) {
      const msg = err?.body?.error?.message || `Lỗi ${err?.status || 'kết nối'}`;
      $('form-submit-error').innerHTML = `${I.alert} ${msg}`;
      $('form-submit-error').classList.remove('hidden');
      toast(msg, 'err');
    } finally {
      state.submitPending = false;
      $('btn-submit-job').disabled = false;
      $('btn-submit-job').innerHTML = `${I.play} Xếp vào hàng đợi & Render Vùng Blur Đã Chọn`;
    }
  });
}

// C2. ĐIỀU PHỐI 8 KÊNH FANPAGE TRONG CÙNG SPA
async function renderChannels() {
  const main = $('main-content');
  main.innerHTML = `
    <div class="page-header">
      <div>
        <h1 class="page-title">📊 Điều Phối 8 Kênh Fanpage &amp; Cấu Hình Render Chuyên Biệt</h1>
        <p class="page-subtitle">Tất cả 8 kênh được hợp nhất trực tiếp vào Command Center. Nhấn chọn kênh bất kỳ để mở ngay Studio với vùng Blur &amp; Giọng đọc AI của kênh đó.</p>
      </div>
      <div class="page-actions">
        <button class="btn btn-primary btn-sm" id="btn-open-studio-from-ch">${I.plus} Mở Studio Đa Cấu Hình</button>
      </div>
    </div>

    <div class="channel-matrix-grid">
      ${CHANNELS_8.map(ch => `
        <div class="channel-matrix-card">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:8px">
            <span style="font-size:14px;font-weight:700;color:var(--txt-1)">📺 ${ch.name}</span>
            <span class="chip succeeded">${ch.preset_id}</span>
          </div>
          <div class="text-muted text-sm">${ch.niche} · Khung giờ đăng: <b>${ch.schedule}</b></div>
          <div class="dl-grid" style="font-size:11px;padding-top:8px;border-top:1px solid var(--border)">
            <span class="dl-label">Giọng đọc AI</span><span class="dl-value mono" style="color:var(--teal)">${ch.voice_id}</span>
            <span class="dl-label">Banner Hook</span><span class="dl-value" style="color:#fde047;font-weight:700">${ch.banner_text || '—'}</span>
            <span class="dl-label">Chữ chạy (Marquee)</span><span class="dl-value">${ch.marquee_text || '—'}</span>
            <span class="dl-label">Tọa độ Blur mặc định</span><span class="dl-value mono">X:${ch.blur_box.x}% · Y:${ch.blur_box.y}% · W:${ch.blur_box.w}% · H:${ch.blur_box.h}%</span>
          </div>
          <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:4px">
            <button type="button" class="btn btn-primary btn-sm" data-open-channel-studio="${ch.id}">
              🎬 Mở Studio &amp; Chọn Vùng Blur cho kênh này →
            </button>
          </div>
        </div>
      `).join('')}
    </div>
  `;

  $('btn-open-studio-from-ch')?.addEventListener('click', () => navigate('new-job'));
  main.querySelectorAll('[data-open-channel-studio]').forEach(btn => {
    btn.addEventListener('click', () => {
      navigate('new-job', { channelId: btn.dataset.openChannelStudio });
    });
  });
}

// D. CHI TIẾT JOB
async function renderJobDetail() {
  stopJobPolling();
  const main = $('main-content');
  if (!main.querySelector('[data-job-detail-loaded]')) {
    main.innerHTML = renderLoading();
  }

  let job, events, outputs;
  try {
    [job, events, outputs] = await Promise.all([
      window.CC_API.getJob(state.jobId),
      window.CC_API.getJobEvents(state.jobId),
      window.CC_API.getJobOutputs(state.jobId),
    ]);
  } catch(e) {
    main.innerHTML = renderError(e?.body?.error?.message || 'Không tải được chi tiết job.', () => renderJobDetail());
    $('btn-err-retry')?.addEventListener('click', renderJobDetail);
    return;
  }

  const tasks   = job.tasks || [];
  const evItems = events.items || [];
  const outItems = outputs.items || [];

  const pg = job.progress;
  const pgText = pg ? (pg.percent !== null ? `${pg.percent}%` : `${pg.completed_tasks}/${pg.total_tasks} task`) : 'Đang xử lý';

  const canCancel = ['queued','running','needs_attention'].includes(job.status);
  const canRetry  = ['failed','cancelled','needs_attention'].includes(job.status);

  const proj = state.projects.find(p => p.id === job.project_id);

  main.innerHTML = `
    <div data-job-detail-loaded="1"></div>
    <div class="page-header">
      <div>
        <nav aria-label="Đường dẫn" style="font-size:11px;color:var(--txt-3);margin-bottom:4px">
          <button class="btn btn-ghost btn-sm" id="btn-back-proj-job" style="padding:0">${proj?.name || 'Danh sách Dự án'}</button>
          <span style="margin:0 4px">›</span>
          <span class="font-mono">#${window.ccUtil.shortId(job.id)}</span>
        </nav>
        <h1 class="page-title" style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
          Job Render <span class="font-mono" style="font-size:15px;color:var(--teal)">#${window.ccUtil.shortId(job.id)}</span>
          ${chip(job.status)}
          ${['queued', 'running'].includes(job.status) ? `<span class="tag" style="color:var(--status-running);border-color:rgba(56,189,248,0.35)">⟳ Tự động đồng bộ tiến trình (2.5s)</span>` : ''}
          ${state.isMock ? '<span class="not-impl">Dữ liệu mô phỏng</span>' : '<span class="tag" style="color:var(--teal);border-color:rgba(45,212,191,0.3)">🔒 HTTPS :443</span>'}
        </h1>
        <p class="page-subtitle">Preset: <b>${job.preset_id}</b> (v${job.preset_version}) · Tiến độ: <b>${pgText}</b> · Cập nhật ${window.ccUtil.relativeTime(job.updated_at)}</p>
      </div>
      <div class="page-actions">
        <button class="btn btn-secondary btn-sm" id="btn-refresh-job">${I.refresh} Làm mới</button>
        ${canRetry  ? `<button class="btn btn-secondary btn-sm" id="btn-retry-job">${I.refresh} Thử lại</button>` : ''}
        ${canCancel ? `<button class="btn btn-danger btn-sm" id="btn-cancel-job-action">${I.stop} Huỷ job</button>` : ''}
      </div>
    </div>

    ${job.status === 'cancelling' ? `
      <div class="info-state mb-3" style="border-color:var(--status-cancelling);color:var(--status-cancelling)">
        ${I.alert} Đang dừng job — chờ backend xác nhận receipt dừng process từ Agent. Fencing sẽ khoá lease để ngăn chặn race condition.
      </div>` : ''}

    ${job.status === 'needs_attention' ? `
      <div class="info-state mb-3" style="border-color:var(--status-needs-attn);color:var(--status-needs-attn)">
        ${I.alert} <b>needs_attention:</b> Job đang ở trạng thái cách ly tài nguyên (quarantine). Cần kiểm tra Agent hoặc đối soát trước khi giải phóng.
      </div>` : ''}

    ${job.error ? `
      <div class="error-state mb-3">
        ${I.alert}
        <div>
          <b>${job.error.code}</b>: ${job.error.message}
        </div>
      </div>` : ''}

    <div class="grid-2" style="gap:16px;margin-bottom:16px">
      <!-- Thông tin cơ bản -->
      <div class="card">
        <div class="card-header"><span class="card-title">${I.list} Thông Tin Hàng Đợi &amp; Định Danh Job</span></div>
        <div class="dl-grid">
          <span class="dl-label">Job UUID</span><span class="dl-value mono">${job.id}</span>
          <span class="dl-label">Dự án UUID</span><span class="dl-value mono">${job.project_id}</span>
          <span class="dl-label">Preset Pipeline</span><span class="dl-value"><span class="tag" style="color:var(--teal)">${job.preset_id}</span> (v${job.preset_version})</span>
          <span class="dl-label">Phiên bản trạng thái</span><span class="dl-value mono">v${job.version}</span>
          <span class="dl-label">Xếp hàng lúc</span><span class="dl-value">${window.ccUtil.formatDate(job.created_at)}</span>
          <span class="dl-label">Cập nhật cuối</span><span class="dl-value">${window.ccUtil.formatDate(job.updated_at)}</span>
          <span class="dl-label">Tiến độ tổng thể</span><span class="dl-value">${renderProgressCell(job)}</span>
        </div>
      </div>

      <!-- Pipeline / Tasks -->
      <div class="card">
        <div class="card-header"><span class="card-title">${I.cpu} Các Bước Thực Thi Pipeline DAG (${tasks.length} bước)</span></div>
        <div class="pipeline">
          ${tasks.length === 0 ? `<div class="text-muted text-sm">Chưa có task nào được tạo.</div>` : ''}
          ${tasks.map((t, i) => `
            ${i > 0 ? '<div class="pipeline-connector"></div>' : ''}
            <div class="pipeline-step${t.id === job.current_task_id ? ' active' : ''}">
              <div class="pipeline-step-icon ${t.status}">
                ${t.status === 'succeeded' ? I.check : t.status === 'failed' ? I.x : (i + 1)}
              </div>
              <div style="flex:1">
                <div class="pipeline-step-name">Bước ${i + 1}: ${t.task_key === 'probe' ? 'Kiểm tra thông số gốc (probe)' : (t.task_key === 'compose' ? 'Render Video & Xuất Báo Cáo JSON (compose)' : t.task_key)}</div>
                <div class="pipeline-step-module">Module: <code>${t.module}@${t.module_version}</code> · Lần chạy (attempt): ${t.attempt}</div>
              </div>
              ${chip(t.status)}
              ${t.error ? `<span class="text-sm" style="color:var(--status-failed)" title="${t.error.message}">${t.error.code}</span>` : ''}
            </div>
          `).join('')}
        </div>
        <p class="form-hint mt-2">Mỗi bước trong hàng đợi được Agent nhận qua <code>POST /api/v1/agent/claims</code> và hoàn tất kèm mã kiểm chứng SHA-256.</p>
      </div>
    </div>

    <!-- Kết quả & duyệt video -->
    ${renderOutputSection(job, outItems)}

    <!-- Log -->
    <div class="section">
      <div class="section-header">
        <span class="section-title">${I.log} Nhật Ký Sự Kiện Hàng Đợi &amp; Agent (${evItems.length})</span>
      </div>
      <div class="log-toolbar">
        <button class="log-filter-btn ${state.logFilter === '' ? 'active' : ''}" data-lf="">Tất cả</button>
        <button class="log-filter-btn ${state.logFilter === 'info' ? 'active' : ''}" data-lf="info">Info</button>
        <button class="log-filter-btn ${state.logFilter === 'warning' ? 'active' : ''}" data-lf="warning">Cảnh báo</button>
        <button class="log-filter-btn ${state.logFilter === 'error' ? 'active' : ''}" data-lf="error">Lỗi</button>
      </div>
      <div class="log-container" role="log" aria-label="Log sự kiện" aria-live="polite">
        ${evItems.length === 0
          ? '<div class="text-muted text-sm">Chưa có sự kiện nào được ghi nhận.</div>'
          : evItems
              .filter(ev => !state.logFilter || ev.level === state.logFilter)
              .map(ev => `
                <div class="log-row ${ev.level}">
                  <span class="ts">${new Date(ev.timestamp).toLocaleTimeString('vi-VN')}</span>
                  <span class="lv">${ev.level}</span>
                  <span class="msg">[${ev.code}] ${ev.message}</span>
                </div>
              `).join('')
        }
      </div>
    </div>
  `;

  $('btn-back-proj-job')?.addEventListener('click', () =>
    state.projectId ? navigate('project-detail') : navigate('overview'));
  $('btn-refresh-job')?.addEventListener('click', () => renderJobDetail());

  $('btn-cancel-job-action')?.addEventListener('click', async () => {
    if (!confirm(`Huỷ job ${window.ccUtil.shortId(job.id)}?`)) return;
    try {
      await window.CC_API.cancelJob(job.id, job.version);
      toast('Đã gửi yêu cầu huỷ — chờ Agent dừng process', 'warn');
      renderJobDetail();
    } catch(e) {
      toast(e?.body?.error?.message || 'Không thể huỷ job.', 'err');
    }
  });

  $('btn-retry-job')?.addEventListener('click', async () => {
    if (!confirm(`Thử lại job ${window.ccUtil.shortId(job.id)}?`)) return;
    try {
      const updated = await window.CC_API.retryJob(job.id, job.version);
      toast(`Job đã được đặt lại hàng đợi`, 'ok');
      state.jobId = updated.id;
      renderJobDetail();
    } catch(e) {
      toast(e?.body?.error?.message || 'Không thể thử lại job.', 'err');
    }
  });

  document.querySelectorAll('[data-lf]').forEach(btn => {
    btn.addEventListener('click', () => {
      state.logFilter = btn.dataset.lf;
      renderJobDetail();
    });
  });

  // Auto-poll while job is queued or running
  if (['queued', 'running', 'cancelling'].includes(job.status)) {
    jobPollTimer = setInterval(() => {
      if (state.view === 'job-detail' && state.jobId === job.id) {
        renderJobDetail();
      } else {
        stopJobPolling();
      }
    }, 2500);
  }

  // Load authenticated blob stream for video player if in Real API mode
  const videoEl = $('cc-stream-video');
  const videoDlBtn = $('cc-download-video-btn');
  const videoFile = outItems.find(f => f.kind === 'video');
  if (videoFile && !state.isMock && window.CC_API.fetchFileBlobUrl) {
    window.CC_API.fetchFileBlobUrl(videoFile.id)
      .then(blobUrl => {
        if (!blobUrl) return;
        if (videoEl) videoEl.src = blobUrl;
        if (videoDlBtn) {
          videoDlBtn.href = blobUrl;
          videoDlBtn.download = `render-${window.ccUtil.shortId(job.id)}.mp4`;
          videoDlBtn.classList.remove('hidden');
        }
      })
      .catch(() => {});
  }

  // Load JSON reports (render-report.json / probe.json) from API and populate QC + JSON download
  const repFiles = outItems.filter(f => f.kind === 'report');
  if (repFiles.length > 0 && !state.isMock && window.CC_API.fetchFileJson) {
    Promise.all(repFiles.map(async f => ({ file: f, data: await window.CC_API.fetchFileJson(f.id).catch(() => null) })))
      .then(results => {
        const valid = results.filter(r => r.data);
        if (valid.length === 0) return;
        const renderRep = valid.find(r => r.data.output_sha256 || r.data.encoder)?.data || valid[0].data;
        const qcBox = $('live-qc-card');
        if (qcBox && renderRep?.media) {
          const m = renderRep.media;
          const rc = renderRep.render_config || {};
          const ap = renderRep.applied_profile || {};
          const vc = renderRep.voice_config || {};
          const bc = renderRep.blur_config || {};
          const tc = renderRep.text_overlay_config || {};
          const ve = renderRep.visual_effects || {};
          qcBox.innerHTML = `
            <div class="card-header">
              <span class="card-title">${I.check} Thông Số Render &amp; Đa Cấu Hình JSON Đã Áp Dụng</span>
              <span class="chip succeeded" style="font-size:10px">SHA-256 Verified</span>
            </div>
            <div class="metric-grid">
              <div class="metric-tile">
                <div class="m-label">Kích thước &amp; Bố cục</div>
                <div class="m-val" style="color:var(--teal)">${m.width}×${m.height} (${ve.fit_mode || rc.fit_mode || 'contain'})</div>
              </div>
              <div class="metric-tile">
                <div class="m-label">Giọng Đọc AI / BGM</div>
                <div class="m-val">${vc.voice_id || rc.voice_id || 'original'} (${vc.voice_speed || rc.voice_speed || 1}x)</div>
              </div>
              <div class="metric-tile">
                <div class="m-label">Vùng Chọn Blur 2D</div>
                <div class="m-val">${(bc.blur_subtitle ?? rc.blur_subtitle) ? `${bc.blur_mode || rc.blur_mode || 'gaussian'} [X:${bc.custom_blur_box?.x_pct ?? rc.blur_x_pct ?? 0}%, Y:${bc.custom_blur_box?.y_pct ?? rc.blur_y_pct ?? 72}%, ${bc.custom_blur_box?.w_pct ?? rc.blur_w_pct ?? 100}×${bc.custom_blur_box?.h_pct ?? rc.blur_h_pct ?? 16}%]` : 'Không bật'}</div>
              </div>
              <div class="metric-tile">
                <div class="m-label">Chạy Chữ / Phụ Đề</div>
                <div class="m-val">${tc.subtitle_style || rc.subtitle_style || 'none'}</div>
              </div>
              <div class="metric-tile">
                <div class="m-label">Màu Sắc &amp; Lật Gương</div>
                <div class="m-val">${ve.color_grade || rc.color_grade || 'natural'}${(ve.mirror_flip ?? rc.mirror_flip) ? ' · 🪞Flip' : ''}</div>
              </div>
              <div class="metric-tile">
                <div class="m-label">Thời lượng / FPS</div>
                <div class="m-val">${m.duration}s · ${m.fps} fps (${m.frames ?? '—'}f)</div>
              </div>
            </div>
            <div class="dl-grid mt-3" style="font-size:11px;padding-top:10px;border-top:1px solid var(--border)">
              ${(tc.banner_text || rc.banner_text) ? `<span class="dl-label">Banner Hook</span><span class="dl-value" style="color:#fde047;font-weight:700">${tc.banner_text || rc.banner_text}</span>` : ''}
              ${(tc.marquee_text || rc.marquee_text) ? `<span class="dl-label">Chữ chạy (Marquee)</span><span class="dl-value" style="color:var(--teal)">${tc.marquee_text || rc.marquee_text}</span>` : ''}
              <span class="dl-label">Cấu hình JSON</span><span class="dl-value mono" style="color:var(--teal)">${JSON.stringify(Object.keys(rc).length ? rc : { width: m.width, height: m.height })}</span>
              ${renderRep.source_sha256 ? `<span class="dl-label">Source SHA-256</span><span class="dl-value mono truncate">${renderRep.source_sha256}</span>` : ''}
              ${renderRep.output_sha256 ? `<span class="dl-label">Output SHA-256</span><span class="dl-value mono truncate">${renderRep.output_sha256}</span>` : ''}
            </div>
          `;
          qcBox.classList.remove('hidden');
        }
        valid.forEach(({ file, data }) => {
          const isRender = Boolean(data.output_sha256 || data.encoder);
          const fname = isRender ? `render-report-${window.ccUtil.shortId(file.id)}.json` : `probe-${window.ccUtil.shortId(file.id)}.json`;
          const badgeEl = document.getElementById(`json-name-${file.id}`);
          if (badgeEl) badgeEl.textContent = fname;
          const pre = document.getElementById(`json-preview-${file.id}`);
          const pretty = JSON.stringify(data, null, 2);
          if (pre) pre.textContent = pretty;
          const dlBtn = document.getElementById(`json-dl-${file.id}`);
          if (dlBtn) {
            const blob = new Blob([pretty], { type: 'application/json' });
            dlBtn.href = URL.createObjectURL(blob);
            dlBtn.download = fname;
            dlBtn.classList.remove('hidden');
          }
          const copyBtn = document.getElementById(`json-copy-${file.id}`);
          if (copyBtn) {
            copyBtn.classList.remove('hidden');
            copyBtn.onclick = () => {
              navigator.clipboard?.writeText(pretty);
              toast(`Đã sao chép ${fname} vào clipboard!`, 'ok');
            };
          }
        });
      })
      .catch(() => {});
  }
}

function renderOutputSection(job, outItems) {
  if (!['needs_review','cancelled','failed'].includes(job.status) && outItems.length === 0) return '';

  const videoFile = outItems.find(f => f.kind === 'video');
  const subtFiles = outItems.filter(f => f.kind === 'subtitle');
  const repFiles  = outItems.filter(f => f.kind === 'report');
  const qc        = job.qc;

  const streamUrl = (videoFile && window.CC_API.getFileContentUrl)
    ? window.CC_API.getFileContentUrl(videoFile.id)
    : null;

  return `
    <div class="section">
      <div class="section-header">
        <span class="section-title">${I.film} Kết Quả Render Video &amp; Báo Cáo Cấu Hình JSON</span>
        ${job.status === 'needs_review' ? `
          <div style="margin-left:auto;display:flex;align-items:center;gap:6px">
            <span class="chip needs_review" style="font-size:12px">Đã hoàn tất Render · Chờ duyệt</span>
          </div>` : ''}
      </div>

      <div class="grid-2" style="gap:16px">
        <div class="card">
          <div class="card-header">
            <span class="card-title">${I.play} Trình Phát Video Kết Quả (HTTPS :443 Stream)</span>
            <a id="cc-download-video-btn" class="btn btn-primary btn-sm hidden" style="text-decoration:none">Tải Video MP4 ↓</a>
          </div>
          <div class="video-player-wrap mb-3" style="border:1px solid var(--border)">
            ${videoFile?.playback_url
              ? `<video controls preload="metadata" style="width:100%;border-radius:6px;background:#000" aria-label="Video kết quả">
                   <source src="${videoFile.playback_url}" type="video/mp4">
                 </video>`
              : (streamUrl && !state.isMock)
                ? `<video id="cc-stream-video" controls preload="metadata" style="width:100%;height:100%;border-radius:6px;background:#000" aria-label="Stream video qua API">
                   </video>`
                : `<div class="video-unavailable">
                     ${I.film}
                     <p>Chưa có file video cho job này</p>
                     <small>${videoFile ? 'File đã lưu tại managed storage.' : 'Preset này chỉ xuất báo cáo JSON (probe.json).'}</small>
                   </div>`
            }
          </div>
          ${videoFile ? `
            <div class="dl-grid" style="font-size:11px">
              <span class="dl-label">File UUID</span><span class="dl-value mono">${videoFile.id}</span>
              <span class="dl-label">Định dạng</span><span class="dl-value">${videoFile.media_type} (${window.ccUtil.formatBytes(videoFile.size_bytes)})</span>
              <span class="dl-label">Toàn vẹn file</span><span class="dl-value">${chip(videoFile.verification === 'verified' ? 'succeeded' : 'queued')}</span>
              ${videoFile.sha256 ? `<span class="dl-label">SHA-256</span><span class="dl-value mono text-sm truncate">${videoFile.sha256}</span>` : ''}
            </div>` : ''}
        </div>

        <div class="flex-col" style="gap:14px">
          ${qc ? `
            <div class="card">
              <div class="card-header"><span class="card-title">QC / Kiểm tra Chất lượng</span></div>
              ${qc.warnings?.length ? `
                ${qc.warnings.map(w => `<div class="flex gap-2 mb-1" style="font-size:12px;color:var(--status-needs-attn)">${I.alert} ${w}</div>`).join('')}` : `<div class="text-muted text-sm">${I.check} Không có cảnh báo kỹ thuật.</div>`}
              ${qc.score !== null && qc.score !== undefined ? `<div class="mt-2 text-sm"><b>Điểm đánh giá:</b> ${qc.score}/100</div>` : ''}
              ${qc.media ? `
                <div class="dl-grid mt-2" style="font-size:11px">
                  <span class="dl-label">Kích thước</span><span class="dl-value">${qc.media.width}x${qc.media.height} px</span>
                  <span class="dl-label">Thời lượng</span><span class="dl-value">${qc.media.duration}s (${qc.media.frames || 0} frames)</span>
                  <span class="dl-label">FPS</span><span class="dl-value">${qc.media.fps}</span>
                  <span class="dl-label">Codec / Audio</span><span class="dl-value mono">${qc.media.codec || '—'} (audio: ${qc.media.has_audio ? 'có' : 'không'})</span>
                </div>
              ` : ''}
            </div>` : `<div class="card hidden" id="live-qc-card"></div>`}

          ${subtFiles.length > 0 ? `
            <div class="card">
              <div class="card-header"><span class="card-title">Phụ đề (${subtFiles.length})</span></div>
              ${subtFiles.map(f => `
                <div class="flex items-center gap-2 mb-1" style="font-size:12px">
                  <span class="tag">${f.media_type}</span>
                  <span class="text-muted">${window.ccUtil.formatBytes(f.size_bytes)}</span>
                  <span class="tag">${f.verification}</span>
                </div>`).join('')}
            </div>` : ''}

          ${repFiles.length > 0 ? `
            <div class="card">
              <div class="card-header">
                <span class="card-title">${I.log} File JSON Cấu Hình &amp; Báo Cáo Từ Agent (${repFiles.length})</span>
              </div>
              ${repFiles.map(f => `
                <div style="border-bottom:1px solid var(--border);padding:10px 0">
                  <div class="flex items-center gap-2 mb-2" style="font-size:12px;flex-wrap:wrap">
                    <span class="tag" style="color:var(--teal);border-color:rgba(45,212,191,0.3)">JSON Report</span>
                    <span id="json-name-${f.id}" class="font-mono" style="font-weight:700;color:var(--txt-1)">${window.ccUtil.shortId(f.id)}.json</span>
                    <span class="text-muted">(${window.ccUtil.formatBytes(f.size_bytes)})</span>
                    <div style="margin-left:auto;display:flex;gap:6px">
                      <button type="button" id="json-copy-${f.id}" class="btn btn-secondary btn-sm hidden" style="font-size:11px;padding:3px 8px">Sao chép JSON</button>
                      <a id="json-dl-${f.id}" class="btn btn-primary btn-sm hidden" style="font-size:11px;padding:3px 10px;text-decoration:none">Tải JSON ↓</a>
                    </div>
                  </div>
                  <pre id="json-preview-${f.id}" class="json-code-box">${f._mock ? JSON.stringify(f, null, 2) : 'Đang tải nội dung JSON từ /api/v1/files/' + window.ccUtil.shortId(f.id) + '/content...'}</pre>
                </div>`).join('')}
            </div>` : ''}
        </div>
      </div>
    </div>
  `;
}

// E. MODULE & AGENT
async function renderModules() {
  const main = $('main-content');
  main.innerHTML = renderLoading();
  try {
    const res = await window.CC_API.getModules();
    state.modules = res.items || [];
  } catch(e) {
    main.innerHTML = renderError(e?.body?.error?.message || 'Không tải được danh sách module.', renderModules);
    $('btn-err-retry')?.addEventListener('click', renderModules);
    return;
  }

  main.innerHTML = `
    <div class="page-header">
      <div>
        <h1 class="page-title">Module Registry</h1>
        <p class="page-subtitle">${state.modules.length} module đã đăng ký · Phiên bản: 1.0.0 · ${state.isMock ? '<span class="not-impl">Dữ liệu mô phỏng</span>' : '<span style="color:var(--teal)">API thật</span>'}</p>
      </div>
    </div>
    <div class="info-state mb-3" style="font-size:12px">
      ${I.alert} Module registry hiển thị năng lực thực thi và tài nguyên (CPU/GPU).
      Không hiển thị secret, token bí mật hoặc đường dẫn file mô hình nội bộ trên máy chủ.
    </div>
    <div class="card">
      <div style="border-radius:var(--radius);overflow:hidden">
        <div class="module-row" style="background:var(--bg-1);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--txt-3)">
          <span>ID</span><span>Tên Module</span><span>Tài Nguyên</span><span>Phiên Bản</span><span>Trạng Thái</span>
        </div>
        ${state.modules.map(m => `
          <div class="module-row">
            <span class="module-id font-mono">${m.id}</span>
            <span class="module-name">${m.label || m.id}</span>
            <span><span class="tag">${m.resource || 'cpu:0'}</span></span>
            <span class="module-ver">v${m.version}</span>
            <span class="module-avail ${m.available ? 'ready' : 'notready'}">
              ${m.available
                ? `${I.check} Sẵn sàng`
                : `<span title="${m.unavailable_reason || ''}">${I.alert} Chưa sẵn sàng</span>`}
            </span>
          </div>
          ${!m.available && m.unavailable_reason ? `
            <div style="padding:2px 14px 8px 14px;font-size:11px;color:var(--txt-3);background:rgba(245,158,11,0.03)">
              Lý do chưa sẵn sàng: <em>${m.unavailable_reason}</em>
            </div>` : ''}
        `).join('')}
      </div>
    </div>
  `;
}

async function renderAgents() {
  const main = $('main-content');
  main.innerHTML = renderLoading();
  try {
    const res = await window.CC_API.getAgents();
    state.agents = res.items || [];
  } catch(e) {
    main.innerHTML = renderError(e?.body?.error?.message || 'Không tải được danh sách Agent.', renderAgents);
    $('btn-err-retry')?.addEventListener('click', renderAgents);
    return;
  }

  main.innerHTML = `
    <div class="page-header">
      <div>
        <h1 class="page-title">Agent Thực Thi</h1>
        <p class="page-subtitle">${state.agents.length} agent · ${state.isMock ? '<span class="not-impl">Dữ liệu mô phỏng</span>' : '<span style="color:var(--teal)">API thật</span>'}</p>
      </div>
      <button class="btn btn-secondary btn-sm" id="btn-refresh-agents">${I.refresh} Làm mới</button>
    </div>
    <div class="info-state mb-3" style="font-size:12px">
      ${I.alert} Agent kết nối outbound đến backend qua HTTP/HTTPS — không mở cổng lắng nghe công khai trên máy Agent.
      Mất kết nối quá 45 giây được đánh dấu là offline.
    </div>
    ${state.agents.length === 0 ? renderEmpty('Chưa có Agent nào kết nối', 'Chạy lệnh Agent trong scripts/run_command_center.ps1 để nhận task.') : `
      <div class="grid-2">
        ${state.agents.map(a => `
          <div class="agent-card ${a.status}">
            <div class="agent-header">
              <span class="agent-name">${a.machine_label || a.id}</span>
              ${chip(a.status)}
            </div>
            <div class="dl-grid" style="font-size:12px">
              <span class="dl-label">ID</span><span class="dl-value mono">${a.id}</span>
              <span class="dl-label">Heartbeat cuối</span><span class="dl-value">${window.ccUtil.relativeTime(a.last_seen_at)}</span>
              <span class="dl-label">Task đang chạy</span><span class="dl-value">${a.active_task_count}</span>
            </div>
            <div class="agent-caps mt-2">
              ${(a.capabilities || []).map(c => `<span class="tag">${c}</span>`).join('')}
            </div>
            ${a.status === 'offline' ? `
              <div class="info-state" style="font-size:11px;margin-top:8px">
                Agent offline ≠ backend dừng hoạt động. Job gửi lên vẫn được lưu an toàn trong database PostgreSQL và chờ Agent nhận việc khi khởi động lại.
              </div>` : ''}
          </div>
        `).join('')}
      </div>
    `}
  `;

  $('btn-refresh-agents')?.addEventListener('click', renderAgents);
}

/* ─── Modals ─────────────────────────────────────────────── */

// Cấu hình kết nối API (Mock vs Real API)
function openApiSettingsModal() {
  const overlay = $('modal-overlay');
  const cfg = window.CC_CONFIG;

  overlay.innerHTML = `
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-settings-title" style="max-width:520px">
      <div class="modal-header">
        <span class="modal-title" id="modal-settings-title">${I.cog} Cấu hình Kết nối API</span>
        <button class="modal-close" id="modal-settings-close" aria-label="Đóng">×</button>
      </div>
      <div class="modal-body flex-col" style="gap:14px">
        <div class="form-group">
          <label class="form-label">Chế độ hoạt động</label>
          <div style="display:flex;gap:16px;margin-top:6px">
            <label style="display:flex;align-items:center;gap:6px;cursor:pointer">
              <input type="radio" name="cfg-mode" value="mock" ${cfg.mode === 'mock' ? 'checked' : ''} style="accent-color:var(--teal)">
              <span>Mô phỏng (Mock Fixtures)</span>
            </label>
            <label style="display:flex;align-items:center;gap:6px;cursor:pointer">
              <input type="radio" name="cfg-mode" value="real" ${cfg.mode === 'real' ? 'checked' : ''} style="accent-color:var(--teal)">
              <span>API thật (/api/v1)</span>
            </label>
          </div>
          <p class="form-hint">Chế độ mô phỏng không yêu cầu backend đang chạy; chế độ API thật kết nối trực tiếp đến FastAPI.</p>
        </div>

        <div class="form-group">
          <label class="form-label" for="cfg-base">Base URL API Backend</label>
          <input class="form-input font-mono text-sm" id="cfg-base" type="text" value="${cfg.apiBase || 'http://127.0.0.1:8016/api/v1'}" />
          <p class="form-hint">Mặc định: <code>http://127.0.0.1:8016/api/v1</code> hoặc <code>/api/v1</code> (nếu có dev proxy).</p>
        </div>

        <div class="form-group">
          <label class="form-label" for="cfg-token">Owner Bearer Token (Local)</label>
          <input class="form-input font-mono text-sm" id="cfg-token" type="password" value="${cfg.authToken || ''}" placeholder="Nhập owner token từ credentials.local.json..." />
          <p class="form-hint">Token xác thực owner (ít nhất 32 ký tự). Không lưu trữ hoặc đóng gói vào bundle công khai.</p>
        </div>

        <div id="cfg-test-result" class="hidden"></div>
      </div>
      <div class="modal-footer" style="justify-content:space-between">
        <button class="btn btn-secondary btn-sm" id="btn-test-connection">${I.refresh} Kiểm tra kết nối</button>
        <div style="display:flex;gap:8px">
          <button class="btn btn-ghost" id="modal-settings-cancel">Huỷ</button>
          <button class="btn btn-primary" id="modal-settings-save">${I.check} Lưu và Áp dụng</button>
        </div>
      </div>
    </div>
  `;
  overlay.classList.add('open');

  const close = () => { overlay.classList.remove('open'); overlay.innerHTML = ''; };
  $('modal-settings-close')?.addEventListener('click', close);
  $('modal-settings-cancel')?.addEventListener('click', close);
  overlay.addEventListener('click', e => { if (e.target === overlay) close(); });

  // Kiểm tra kết nối
  $('btn-test-connection')?.addEventListener('click', async () => {
    const resBox = $('cfg-test-result');
    const base = $('cfg-base').value.trim();
    const token = $('cfg-token').value.trim();
    const btn = $('btn-test-connection');

    btn.disabled = true;
    btn.textContent = 'Đang thử…';
    resBox.className = 'info-state text-sm';
    resBox.innerHTML = 'Đang gửi yêu cầu /health và /ready...';
    resBox.classList.remove('hidden');

    try {
      // Test health
      const hRes = await fetch(base.replace(/\/+$/, '') + '/health');
      const hJson = await hRes.json();
      resBox.className = 'card mt-2 p-2';
      resBox.style.borderColor = 'var(--status-ok)';
      resBox.innerHTML = `
        <div style="color:var(--status-ok);font-weight:600">${I.check} Kết nối thành công!</div>
        <div class="text-sm mt-1">Health: <code>status: ${hJson.status}, version: ${hJson.api_version}</code></div>
      `;
    } catch (err) {
      resBox.className = 'error-state text-sm';
      resBox.innerHTML = `${I.alert} Lỗi kết nối: ${err.message || 'Không thể liên lạc với server.'}. Kiểm tra port 8016 và CORS.`;
    } finally {
      btn.disabled = false;
      btn.innerHTML = `${I.refresh} Kiểm tra kết nối`;
    }
  });

  // Lưu cấu hình
  $('modal-settings-save')?.addEventListener('click', () => {
    const selectedMode = document.querySelector('input[name="cfg-mode"]:checked')?.value || 'mock';
    const base = $('cfg-base').value.trim();
    const token = $('cfg-token').value.trim();

    window.ccSwitchMode(selectedMode, base, token);
    syncApiModeUI();
    close();
    toast(`Đã chuyển sang chế độ: ${selectedMode === 'mock' ? 'Mô phỏng' : 'API thật'}`, 'ok');
    navigate(state.view);
  });
}

function openCreateProjectModal() {
  const overlay = $('modal-overlay');
  overlay.innerHTML = `
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div class="modal-header">
        <span class="modal-title" id="modal-title">Tạo dự án mới</span>
        <button class="modal-close" id="modal-close" aria-label="Đóng">×</button>
      </div>
      <div class="modal-body">
        <div class="form-group">
          <label class="form-label" for="proj-name-input">Tên dự án <span class="required">*</span></label>
          <input class="form-input" id="proj-name-input" type="text" maxlength="120" placeholder="Tên dự án (1–120 ký tự)" required autofocus />
          <div class="form-error hidden" id="proj-name-error">${I.alert} Cần nhập tên dự án.</div>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-ghost" id="modal-cancel">Huỷ</button>
        <button class="btn btn-primary" id="modal-confirm">${I.plus} Tạo dự án</button>
      </div>
    </div>
  `;
  overlay.classList.add('open');
  $('proj-name-input').focus();

  const close = () => { overlay.classList.remove('open'); overlay.innerHTML = ''; };
  $('modal-close').addEventListener('click', close);
  $('modal-cancel').addEventListener('click', close);
  overlay.addEventListener('click', e => { if(e.target === overlay) close(); });

  $('modal-confirm').addEventListener('click', async () => {
    const name = $('proj-name-input').value.trim();
    if (!name) { $('proj-name-error').classList.remove('hidden'); return; }
    $('proj-name-error').classList.add('hidden');
    $('modal-confirm').disabled = true;
    $('modal-confirm').textContent = 'Đang tạo…';
    try {
      const p = await window.CC_API.createProject(name);
      toast(`Đã tạo dự án "${p.name}"`, 'ok');
      close();
      navigate('project-detail', { projectId: p.id });
    } catch(e) {
      toast(e?.body?.error?.message || 'Không thể tạo dự án.', 'err');
      $('modal-confirm').disabled = false;
      $('modal-confirm').innerHTML = `${I.plus} Tạo dự án`;
    }
  });
}

function openRenameProjectModal(project) {
  const overlay = $('modal-overlay');
  overlay.innerHTML = `
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title-r">
      <div class="modal-header">
        <span class="modal-title" id="modal-title-r">Đổi tên dự án</span>
        <button class="modal-close" id="modal-close-r" aria-label="Đóng">×</button>
      </div>
      <div class="modal-body">
        <div class="form-group">
          <label class="form-label" for="proj-rename-input">Tên mới <span class="required">*</span></label>
          <input class="form-input" id="proj-rename-input" type="text" maxlength="120" value="${project.name}" required autofocus />
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-ghost" id="modal-cancel-r">Huỷ</button>
        <button class="btn btn-primary" id="modal-confirm-r">Lưu</button>
      </div>
    </div>
  `;
  overlay.classList.add('open');
  $('proj-rename-input').focus();

  const close = () => { overlay.classList.remove('open'); overlay.innerHTML = ''; };
  $('modal-close-r').addEventListener('click', close);
  $('modal-cancel-r').addEventListener('click', close);

  $('modal-confirm-r').addEventListener('click', async () => {
    const name = $('proj-rename-input').value.trim();
    if (!name) return;
    $('modal-confirm-r').disabled = true;
    try {
      await window.CC_API.updateProject(project.id, name, project.version);
      toast('Đã đổi tên dự án', 'ok');
      close();
      navigate('project-detail', { projectId: project.id });
    } catch(e) {
      toast(e?.body?.error?.message || 'Không thể đổi tên.', 'err');
      $('modal-confirm-r').disabled = false;
    }
  });
}

/* ─── API badge (health check /api/v1/health) ────────────── */
async function checkLegacyHealth() {
  const badge = $('api-health-badge');
  if (!badge) return;
  try {
    const r = await fetch('/api/v1/health', { signal: AbortSignal.timeout(3000) });
    if (!r.ok) throw new Error();
    badge.className = 'api-badge ok';
    badge.innerHTML = `<span class="dot"></span>API v1 Ready`;
  } catch {
    badge.className = 'api-badge';
    badge.innerHTML = `<span class="dot"></span>Local Mode`;
  }
}

/* ─── Main render loop ───────────────────────────────────── */
function render() {
  syncNav();
  syncApiModeUI();
  switch (state.view) {
    case 'overview':       renderOverview();      break;
    case 'projects':       renderProjects();      break;
    case 'project-detail': renderProjectDetail(); break;
    case 'new-job':        renderNewJob();        break;
    case 'channels':       renderChannels();      break;
    case 'job-detail':     renderJobDetail();     break;
    case 'modules':        renderModules();       break;
    case 'agents':         renderAgents();        break;
    default:               renderOverview();
  }
}

/* ─── Initialization ─────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-nav]').forEach(el => {
    el.addEventListener('click', (e) => {
      e.preventDefault();
      const v = el.dataset.nav;
      state.jobFilterStatus = '';
      navigate(v);
    });
  });

  // Nút mở modal Cấu hình API
  $('btn-api-mode')?.addEventListener('click', openApiSettingsModal);
  $('btn-banner-settings')?.addEventListener('click', openApiSettingsModal);

  // Sync mode ban đầu
  syncApiModeUI();

  // Kiểm tra health API cũ
  checkLegacyHealth();
  setInterval(checkLegacyHealth, 45_000);

  // Initial render
  render();
});
