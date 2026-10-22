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

/* ─── State ──────────────────────────────────────────────── */
const state = {
  view: 'overview',          // 'overview' | 'projects' | 'project-detail' | 'new-job' | 'job-detail' | 'modules' | 'agents'
  projectId: null,
  jobId: null,
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
    banner.classList.remove('hidden');
    if (state.isMock) {
      banner.classList.remove('real');
      bannerTxt.textContent = 'DỮ LIỆU MÔ PHỎNG — Thao tác qua Mock Client (Registry 1.0.0). Nhấn "Cấu hình API" để kết nối backend thật.';
    } else {
      banner.classList.add('real');
      bannerTxt.textContent = `KẾT NỐI API THỰC (${window.CC_CONFIG.apiBase}) — Đang giao tiếp với FastAPI backend (PostgreSQL Docker).`;
    }
  }
}

/* ─── Navigation ─────────────────────────────────────────── */
function navigate(view, params = {}) {
  state.view = view;
  if (params.projectId !== undefined) state.projectId = params.projectId;
  if (params.jobId !== undefined)     state.jobId     = params.jobId;
  render();
}

function syncNav() {
  document.querySelectorAll('[data-nav]').forEach(el => {
    el.classList.toggle('active', el.dataset.nav === state.view
      || (state.view === 'project-detail' && el.dataset.nav === 'projects')
      || (state.view === 'new-job' && el.dataset.nav === 'projects')
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
        <h1 class="page-title">Tổng quan</h1>
        <p class="page-subtitle">Cập nhật lúc ${new Date().toLocaleTimeString('vi-VN')} · ${state.isMock ? '<span class="not-impl">Dữ liệu mô phỏng</span>' : '<span style="color:var(--teal)">API thật</span>'}</p>
      </div>
      <div class="page-actions">
        <button class="btn btn-secondary btn-sm" id="btn-api-settings-quick">${I.cog} Cấu hình API</button>
        <button class="btn btn-secondary btn-sm" id="btn-refresh-overview">${I.refresh} Làm mới</button>
        <button class="btn btn-primary btn-sm" id="btn-new-job-quick">${I.plus} Tạo job mới</button>
      </div>
    </div>

    <div class="grid-4 mb-3">
      <div class="stat-card running">
        <div class="label">Đang chạy</div>
        <div class="value">${counts.running}</div>
        <div class="sublabel">job đang xử lý</div>
      </div>
      <div class="stat-card waiting">
        <div class="label">Đang chờ</div>
        <div class="value">${counts.queued}</div>
        <div class="sublabel">trong hàng đợi</div>
      </div>
      <div class="stat-card review">
        <div class="label">Cần duyệt</div>
        <div class="value">${counts.needs_review}</div>
        <div class="sublabel">cần người xem video</div>
      </div>
      <div class="stat-card ${needsAction > 0 ? 'error' : 'ok'}">
        <div class="label">Cần xử lý</div>
        <div class="value">${needsAction}</div>
        <div class="sublabel">lỗi + cần xem xét + cần duyệt</div>
      </div>
    </div>

    <div class="grid-2" style="gap:16px">
      <!-- Agent status -->
      <div class="card">
        <div class="card-header">
          <span class="card-title">${I.cpu} Agent Trực Tuyến</span>
          <button class="btn btn-ghost btn-sm" id="btn-go-agents">Xem tất cả (${state.agents.length})</button>
        </div>
        ${state.agents.length === 0
          ? renderEmpty('Chưa có Agent nào kết nối', 'Agent kết nối outbound sau khi backend và Agent mới được triển khai.')
          : state.agents.map(a => `
            <div class="agent-card ${a.status}" style="margin-bottom:10px">
              <div class="agent-header">
                <span class="agent-name">${a.machine_label || a.id}</span>
                ${chip(a.status)}
              </div>
              <div class="agent-meta">
                Heartbeat cuối: ${window.ccUtil.relativeTime(a.last_seen_at)} ·
                Task đang chạy: ${a.active_task_count}
              </div>
              <div class="agent-caps">
                ${(a.capabilities || []).map(c => `<span class="tag">${c}</span>`).join('')}
              </div>
            </div>
          `).join('')}
        <div class="info-state mt-2 text-sm">
          <b>Ghi chú vận hành:</b> Agent offline ≠ backend không truy cập. Nếu tất cả Agent offline, job vẫn được nhận vào hàng đợi nhưng chờ Agent claim.
        </div>
      </div>

      <!-- Cần xử lý -->
      <div class="card">
        <div class="card-header">
          <span class="card-title">${I.alert} Cần duyệt &amp; Xử lý</span>
        </div>
        ${needsAction === 0
          ? `<div class="empty-state" style="padding:24px"><p>Không có job nào cần duyệt hoặc có lỗi.</p></div>`
          : state.jobs.filter(j => ['failed','needs_attention','needs_review'].includes(j.status))
              .slice(0,6).map(j => `
              <div class="flex items-center gap-2 mb-2 p-2" style="cursor:pointer;border-radius:4px;background:var(--bg-2)" data-job="${j.id}" role="button" tabindex="0" aria-label="Xem chi tiết job ${window.ccUtil.shortId(j.id)}">
                ${chip(j.status)}
                <span class="truncate" style="flex:1;font-size:12px">${j.preset_id} · <span class="font-mono">${window.ccUtil.shortId(j.id)}</span></span>
                <span class="text-muted text-sm">${window.ccUtil.relativeTime(j.updated_at)}</span>
              </div>
            `).join('')
        }
      </div>
    </div>

    <div class="section mt-4">
      <div class="section-header">
        <span class="section-title">Job gần nhất</span>
        <div class="section-actions">
          <button class="btn btn-ghost btn-sm" id="btn-go-projects">Xem theo dự án</button>
        </div>
      </div>
      ${recentJobs.length === 0 ? renderEmpty('Chưa có job nào trong hệ thống') : `
        <div class="table-wrap">
          <table>
            <thead><tr>
              <th scope="col">ID</th>
              <th scope="col">Dự án</th>
              <th scope="col">Preset</th>
              <th scope="col">Trạng thái</th>
              <th scope="col">Tiến độ</th>
              <th scope="col">Cập nhật</th>
              <th scope="col"></th>
            </tr></thead>
            <tbody>
              ${recentJobs.map(j => {
                const pg = j.progress;
                const pgText = pg ? (pg.percent !== null ? `${pg.percent}%` : `${pg.completed_tasks}/${pg.total_tasks} task`) : '—';
                return `
                <tr data-job="${j.id}" role="button" tabindex="0" aria-label="Xem job ${window.ccUtil.shortId(j.id)}">
                  <td class="mono">${window.ccUtil.shortId(j.id)}</td>
                  <td class="muted">${window.ccUtil.shortId(j.project_id)}</td>
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

// C. TẠO JOB
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
    main.innerHTML = renderError(`Không tải được dữ liệu tạo job. ${e?.body?.error?.message || ''}`, renderNewJob);
    $('btn-err-retry')?.addEventListener('click', renderNewJob);
    return;
  }

  const activeProjects = state.projects.filter(p => !p.archived_at);
  const defaultProject = state.projectId || (activeProjects[0]?.id || '');
  const defaultPreset  = state.presets.find(p => p.available) || state.presets[0];

  main.innerHTML = `
    <div class="page-header">
      <div>
        <h1 class="page-title">Tạo job render mới</h1>
        <p class="page-subtitle">Chọn dự án, file đầu vào và preset từ registry 1.0.0. ${state.isMock ? '<span class="not-impl">Dữ liệu mô phỏng</span>' : '<span style="color:var(--teal)">API thật</span>'}</p>
      </div>
      <div class="page-actions">
        <button class="btn btn-ghost" id="btn-cancel-job">Huỷ</button>
      </div>
    </div>

    <div class="info-state mb-3" style="font-size:12px">
      ${I.alert} <b>Lưu ý tích hợp:</b> API <code>POST /api/v1/jobs</code> nhận <code>input_refs</code> là File UUID đã đăng ký qua backend.
      Hiện tại chưa có HTTP upload file trực tiếp từ trình duyệt — sử dụng file ID đã import từ CLI hoặc file mẫu đã kiểm chứng.
    </div>

    <form id="new-job-form" novalidate>
      <div class="grid-2" style="gap:20px">
        <!-- Left: project + input + schema overrides -->
        <div class="flex-col" style="gap:16px">
          <div class="card">
            <div class="card-header"><span class="card-title">Dự án &amp; File Đầu Vào</span></div>
            <div class="flex-col" style="gap:12px">
              <div class="form-group">
                <label class="form-label" for="new-job-project">Dự án <span class="required">*</span></label>
                <select class="form-select" id="new-job-project" required aria-required="true">
                  ${activeProjects.length === 0 ? '<option value="">— Chưa có dự án nào —</option>' : ''}
                  ${activeProjects.map(p => `<option value="${p.id}" ${p.id === defaultProject ? 'selected' : ''}>${p.name}</option>`).join('')}
                </select>
              </div>

              <div class="form-group">
                <label class="form-label" for="new-job-input">Input (File UUID đã verified) <span class="required">*</span></label>
                <input class="form-input" id="new-job-input" type="text"
                  placeholder="Ví dụ: f5d34973-487e-4794-be6b-ff927eb83218"
                  value="${state.isMock ? 'f5d34973-487e-4794-be6b-ff927eb83218' : ''}"
                  aria-describedby="input-hint" />
                <div id="verified-files-picker" style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap"></div>
                <p class="form-hint" id="input-hint">
                  Nhập hoặc chọn UUID của File đã qua kiểm tra hợp lệ. Không nhập đường dẫn tệp cục bộ (C:\\... hoặc D:\\...).
                </p>
                <div class="form-error hidden" id="input-error">${I.alert} Cần ít nhất 1 UUID hợp lệ (36 ký tự).</div>
              </div>
            </div>
          </div>

          <div class="card">
            <div class="card-header"><span class="card-title">Tham Số Ghi Đè (Theo Schema Preset)</span></div>
            <div id="dynamic-override-container">
              <!-- Render động theo schema của preset được chọn -->
            </div>
          </div>
        </div>

        <!-- Right: preset picker -->
        <div class="card">
          <div class="card-header"><span class="card-title">Chọn Preset Từ Registry</span></div>
          <p class="form-hint mb-2">Schema và tính sẵn sàng lấy trực tiếp từ registry 1.0.0, không hard-code cấu hình.</p>
          <div id="preset-list" class="flex-col" style="gap:8px">
            ${state.presets.map(p => `
              <label class="preset-option" style="cursor:pointer;border:1px solid var(--border);border-radius:6px;padding:10px 12px;display:flex;align-items:flex-start;gap:10px;transition:border-color .15s,background .15s;${!p.available ? 'opacity:.55;' : ''}">
                <input type="radio" name="preset" value="${p.id}" data-version="${p.version}"
                  ${p.id === defaultPreset?.id ? 'checked' : ''}
                  ${!p.available ? 'disabled' : ''}
                  style="margin-top:2px;accent-color:var(--teal)"
                  aria-describedby="preset-desc-${p.id}">
                <div style="flex:1">
                  <div style="font-size:13px;font-weight:600;display:flex;align-items:center;gap:6px">
                    ${p.label}
                    ${p.available ? `<span class="chip succeeded" style="font-size:10px">Sẵn sàng</span>` : `<span class="chip disabled" style="font-size:10px">Chưa tích hợp</span>`}
                  </div>
                  <div style="font-size:11px;color:var(--txt-3);margin-top:2px" id="preset-desc-${p.id}">
                    <span class="font-mono">${p.id}</span> · v${p.version}
                    ${p.available ? '' : `<br><span class="not-impl">${p.unavailable_reason || 'Đang tích hợp adapter'}</span>`}
                  </div>
                  <div style="display:flex;gap:4px;flex-wrap:wrap;margin-top:4px">
                    ${(p.modules || []).map(m => `<span class="tag">${m}</span>`).join('')}
                  </div>
                </div>
              </label>
            `).join('')}
          </div>

          <div id="preset-availability" class="mt-3" style="font-size:11px;color:var(--txt-3)"></div>
        </div>
      </div>

      <!-- Summary + submit -->
      <div class="card mt-4" id="job-summary">
        <div class="card-header"><span class="card-title">Tóm tắt cấu hình Job</span></div>
        <div id="summary-body" class="dl-grid"></div>
        <div id="form-submit-error" class="form-error hidden mt-3"></div>
        <div class="modal-footer" style="padding:12px 0 0">
          <button type="submit" class="btn btn-primary btn-lg" id="btn-submit-job" aria-describedby="form-submit-error">
            ${I.play} Gửi job render
          </button>
        </div>
      </div>
    </form>
  `;

  $('btn-cancel-job')?.addEventListener('click', () =>
    state.projectId ? navigate('project-detail') : navigate('projects'));

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

  // Update dynamic schema override fields
  function updateOverrideFields(preset) {
    const container = $('dynamic-override-container');
    if (!container) return;

    const schema = getSchemaProps(preset);
    if (Object.keys(schema).length === 0) {
      container.innerHTML = `<p class="form-hint">Preset này không yêu cầu hoặc không nhận tham số ghi đè (overrides rỗng).</p>`;
      return;
    }

    let html = '';

    if (schema.width && schema.height) {
      const curW = parseInt($('override-width')?.value || schema.width.default || 720, 10);
      const curH = parseInt($('override-height')?.value || schema.height.default || 1280, 10);
      html += `
        <div class="grid-2" style="gap:12px">
          <div class="form-group">
            <label class="form-label" for="override-width">Chiều rộng (Width px)</label>
            <select class="form-select" id="override-width">
              ${(schema.width.enum || [360, 720, 1080]).map(w => `<option value="${w}" ${w === curW ? 'selected' : ''}>${w} px</option>`).join('')}
            </select>
          </div>
          <div class="form-group">
            <label class="form-label" for="override-height">Chiều cao (Height px)</label>
            <select class="form-select" id="override-height">
              ${(schema.height.enum || [640, 1280, 1920]).map(h => `<option value="${h}" ${h === curH ? 'selected' : ''}>${h} px (Dọc)</option>`).join('')}
            </select>
          </div>
        </div>
        <p class="form-hint mt-2">
          Preset basic_render nhận độ phân giải qua schema. Tiêu đề không được nhận (tránh lỗi 422).
        </p>
      `;
    } else if (schema.title) {
      html += `
        <div class="form-group">
          <label class="form-label" for="override-title">Tiêu đề ghi đè</label>
          <input class="form-input" id="override-title" type="text" maxlength="200" placeholder="Tiêu đề video..." />
          <p class="form-hint">Tối đa 200 ký tự.</p>
        </div>
      `;
    } else {
      html += `<p class="form-hint">Tham số mở rộng schema: ${Object.keys(schema).join(', ')}</p>`;
    }

    container.innerHTML = html;
    $('override-width')?.addEventListener('change', updateSummaryTextOnly);
    $('override-height')?.addEventListener('change', updateSummaryTextOnly);
  }

  function updateSummaryTextOnly() {
    const projSel   = $('new-job-project');
    const presetSel = document.querySelector('input[name="preset"]:checked');
    const inputVal  = $('new-job-input')?.value.trim() || '';

    const projName  = projSel?.options[projSel.selectedIndex]?.text || '—';
    const presetId  = presetSel?.value || '—';
    const presetVer = presetSel?.dataset.version || '1.0.0';

    const preset = state.presets.find(p => p.id === presetId);
    const schema = getSchemaProps(preset);

    let overrideText = 'Không có';
    if (schema.width) {
      const w = $('override-width')?.value || 720;
      const h = $('override-height')?.value || 1280;
      overrideText = `width: ${w}, height: ${h}`;
    }

    $('summary-body').innerHTML = `
      <span class="dl-label">Dự án</span><span class="dl-value">${projName}</span>
      <span class="dl-label">Preset</span><span class="dl-value">${presetId} (v${presetVer})</span>
      <span class="dl-label">Input Ref</span><span class="dl-value mono">${inputVal || '<em>Chưa nhập UUID</em>'}</span>
      <span class="dl-label">Overrides</span><span class="dl-value mono">${overrideText}</span>
      <span class="dl-label">schema_version</span><span class="dl-value mono">0.1.0-draft</span>
    `;

    const disabled = !preset?.available || state.submitPending;
    $('btn-submit-job').disabled = disabled;
    if (preset && !preset.available) {
      $('btn-submit-job').innerHTML = `${I.alert} Preset chưa sẵn sàng trong registry`;
    } else {
      $('btn-submit-job').innerHTML = `${I.play} Gửi job render`;
    }
  }

  // Update summary when form changes
  function updateSummary() {
    const presetSel = document.querySelector('input[name="preset"]:checked');
    const preset = state.presets.find(p => p.id === (presetSel?.value || ''));
    updateOverrideFields(preset);
    updateSummaryTextOnly();
  }

  async function loadProjectVerifiedFiles() {
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
        updateSummaryTextOnly();
      }
      picker.innerHTML = files.map(f => `
        <button type="button" class="tag" style="cursor:pointer;border:1px solid var(--teal)" data-pick-file="${f.id}">
          ${I.film} Chọn file verified: ${window.ccUtil.shortId(f.id)} (${window.ccUtil.formatBytes(f.size_bytes)})
        </button>
      `).join('');
      picker.querySelectorAll('[data-pick-file]').forEach(btn => {
        btn.addEventListener('click', () => {
          $('new-job-input').value = btn.dataset.pickFile;
          updateSummaryTextOnly();
        });
      });
    } catch {
      picker.innerHTML = '';
    }
  }

  $('new-job-project')?.addEventListener('change', () => {
    updateSummaryTextOnly();
    loadProjectVerifiedFiles();
  });
  $('new-job-input')?.addEventListener('input', updateSummaryTextOnly);
  document.querySelectorAll('input[name="preset"]').forEach(r => r.addEventListener('change', updateSummary));
  updateSummary();
  loadProjectVerifiedFiles();

  // Submit
  $('new-job-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    if (state.submitPending) return;

    const projSel   = $('new-job-project');
    const presetSel = document.querySelector('input[name="preset"]:checked');
    const inputVal  = $('new-job-input')?.value.trim();

    // Validation UUID
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
    const schema = getSchemaProps(preset);
    const overrides = {};
    if (schema.width) {
      overrides.width = parseInt($('override-width')?.value || 720, 10);
      overrides.height = parseInt($('override-height')?.value || 1280, 10);
    } else if (schema.title) {
      const t = $('override-title')?.value.trim();
      if (t) overrides.title = t;
    }

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
    $('btn-submit-job').innerHTML = `<span>Đang gửi đến backend…</span>`;
    $('form-submit-error')?.classList.add('hidden');

    try {
      const job = await window.CC_API.createJob(payload);
      toast(`Đã tạo job ${window.ccUtil.shortId(job.id)}`, 'ok');
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
      $('btn-submit-job').innerHTML = `${I.play} Gửi job render`;
    }
  });
}

// D. CHI TIẾT JOB
async function renderJobDetail() {
  const main = $('main-content');
  main.innerHTML = renderLoading();

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
    <div class="page-header">
      <div>
        <nav aria-label="Đường dẫn" style="font-size:11px;color:var(--txt-3);margin-bottom:4px">
          <button class="btn btn-ghost btn-sm" id="btn-back-proj-job" style="padding:0">${proj?.name || 'Dự án'}</button>
          <span style="margin:0 4px">›</span>
          <span class="font-mono">${window.ccUtil.shortId(job.id)}</span>
        </nav>
        <h1 class="page-title" style="display:flex;align-items:center;gap:10px">
          Job <span class="font-mono" style="font-size:14px">${window.ccUtil.shortId(job.id)}</span>
          ${chip(job.status)}
          ${state.isMock ? '<span class="not-impl">Dữ liệu mô phỏng</span>' : '<span style="color:var(--teal)">API thật</span>'}
        </h1>
        <p class="page-subtitle">Preset: ${job.preset_id} v${job.preset_version} · Tiến độ: ${pgText} · Cập nhật ${window.ccUtil.relativeTime(job.updated_at)}</p>
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
        <div class="card-header"><span class="card-title">Thông tin job</span></div>
        <div class="dl-grid">
          <span class="dl-label">Job ID</span><span class="dl-value mono">${job.id}</span>
          <span class="dl-label">Dự án ID</span><span class="dl-value mono">${job.project_id}</span>
          <span class="dl-label">Preset</span><span class="dl-value">${job.preset_id}</span>
          <span class="dl-label">Phiên bản preset</span><span class="dl-value mono">${job.preset_version}</span>
          <span class="dl-label">Phiên bản job</span><span class="dl-value">v${job.version}</span>
          <span class="dl-label">Tạo lúc</span><span class="dl-value">${window.ccUtil.formatDate(job.created_at)}</span>
          <span class="dl-label">Cập nhật</span><span class="dl-value">${window.ccUtil.formatDate(job.updated_at)}</span>
          <span class="dl-label">Tiến độ</span><span class="dl-value">${pgText}${pg?.percent === null && job.status === 'running' ? ' <span class="text-muted text-sm">(chưa đo được)</span>' : ''}</span>
        </div>
      </div>

      <!-- Pipeline / Tasks -->
      <div class="card">
        <div class="card-header"><span class="card-title">Pipeline Tasks (${tasks.length})</span></div>
        <div class="pipeline">
          ${tasks.length === 0 ? `<div class="text-muted text-sm">Chưa có task nào được tạo.</div>` : ''}
          ${tasks.map((t, i) => `
            ${i > 0 ? '<div class="pipeline-connector"></div>' : ''}
            <div class="pipeline-step${t.id === job.current_task_id ? ' active' : ''}">
              <div class="pipeline-step-icon ${t.status}">
                ${t.status === 'succeeded' ? I.check : t.status === 'failed' ? I.x : (t.attempt || '')}
              </div>
              <div style="flex:1">
                <div class="pipeline-step-name">${t.task_key}</div>
                <div class="pipeline-step-module">${t.module} (v${t.module_version}) · attempt ${t.attempt}</div>
              </div>
              ${chip(t.status)}
              ${t.error ? `<span class="text-sm" style="color:var(--status-failed)" title="${t.error.message}">${t.error.code}</span>` : ''}
            </div>
          `).join('')}
        </div>
        <p class="form-hint mt-2">Pipeline phụ thuộc vào preset từ registry — không mọi preset đều có đủ tất cả các bước.</p>
      </div>
    </div>

    <!-- Kết quả & duyệt video -->
    ${renderOutputSection(job, outItems)}

    <!-- Log -->
    <div class="section">
      <div class="section-header">
        <span class="section-title">${I.log} Log sự kiện (${evItems.length})</span>
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
    state.projectId ? navigate('project-detail') : navigate('projects'));
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

  // Load authenticated blob stream for video player if in Real API mode
  const videoEl = $('cc-stream-video');
  const videoFile = outItems.find(f => f.kind === 'video');
  if (videoEl && videoFile && !state.isMock && window.CC_API.fetchFileBlobUrl) {
    window.CC_API.fetchFileBlobUrl(videoFile.id)
      .then(blobUrl => {
        if (blobUrl && videoEl) videoEl.src = blobUrl;
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
        <span class="section-title">${I.film} Kết quả &amp; Duyệt Video</span>
        ${job.status === 'needs_review' ? `
          <div style="margin-left:auto;display:flex;align-items:center;gap:6px">
            <span class="chip needs_review" style="font-size:12px">Cần người xem duyệt</span>
            <span class="not-impl" style="font-size:10px" title="Contract 0.1.0-draft chưa có endpoint phê duyệt xuất bản">API duyệt chưa có</span>
          </div>` : ''}
      </div>

      ${job.status === 'needs_review' ? `
        <div class="info-state mb-3" style="font-size:12px">
          ${I.alert} <b>needs_review:</b> Đã hoàn thành các bước render kỹ thuật và xác minh output. Trạng thái này <b>chưa đồng nghĩa</b> được phép đăng lên Facebook/TikTok/Telegram.
        </div>` : ''}

      <div class="grid-2" style="gap:16px">
        <div>
          <div class="video-player-wrap mb-2">
            ${videoFile?.playback_url
              ? `<video controls preload="metadata" style="width:100%;border-radius:6px;background:#000" aria-label="Video kết quả">
                   <source src="${videoFile.playback_url}" type="video/mp4">
                 </video>`
              : (streamUrl && !state.isMock)
                ? `<video id="cc-stream-video" controls preload="metadata" style="width:100%;border-radius:6px;background:#000" aria-label="Stream video qua API">
                   </video>
                   <div style="font-size:11px;color:var(--teal);margin-top:4px">
                     ${I.check} Stream xác thực trực tiếp từ API backend (/files/${window.ccUtil.shortId(videoFile.id)}/content)
                   </div>`
                : `<div class="video-unavailable">
                     ${I.film}
                     <p>Chưa có luồng phát video trực tuyến</p>
                     <small>${videoFile ? 'File đã lưu tại managed storage; playback_url=null theo contract 0.1.0-draft.' : 'Không có file video trong danh sách output.'}</small>
                   </div>`
            }
          </div>
          ${videoFile ? `
            <div class="dl-grid" style="font-size:11px">
              <span class="dl-label">File ID</span><span class="dl-value mono">${videoFile.id}</span>
              <span class="dl-label">Loại MIME</span><span class="dl-value">${videoFile.media_type}</span>
              <span class="dl-label">Dung lượng</span><span class="dl-value">${window.ccUtil.formatBytes(videoFile.size_bytes)}</span>
              <span class="dl-label">Xác minh</span><span class="dl-value">${chip(videoFile.verification === 'verified' ? 'succeeded' : 'queued')}</span>
              ${videoFile.sha256 ? `<span class="dl-label">SHA256</span><span class="dl-value mono text-sm truncate">${videoFile.sha256}</span>` : ''}
            </div>` : ''}
        </div>

        <div class="flex-col" style="gap:12px">
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
            </div>` : ''}

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
              <div class="card-header"><span class="card-title">Báo cáo Kỹ thuật</span></div>
              ${repFiles.map(f => `
                <div class="flex items-center gap-2 mb-1" style="font-size:12px">
                  <span class="tag">${f.kind}</span>
                  <span class="text-muted">${window.ccUtil.formatBytes(f.size_bytes)}</span>
                  <span class="tag">${f.verification}</span>
                </div>`).join('')}
            </div>` : ''}

          ${job.status === 'needs_review' ? `
            <div class="card" style="border-color:var(--border-light)">
              <div class="card-header"><span class="card-title">Render Lại Hình Ảnh (Visual-Only)</span></div>
              <p class="form-hint">Render lại hình từ packet là job riêng biệt — không cho phép đổi giọng nói hoặc audio qua thao tác này.</p>
              <button class="btn btn-secondary btn-sm mt-2" disabled title="Chưa triển khai — Chờ endpoint trong contract">
                Tạo job render lại hình <span class="not-impl" style="margin-left:4px">Chờ tích hợp</span>
              </button>
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

/* ─── API badge (health check legacy 8005) ───────────────── */
async function checkLegacyHealth() {
  const badge = $('api-health-badge');
  if (!badge) return;
  try {
    const r = await fetch('/api/health', { signal: AbortSignal.timeout(3000) });
    if (!r.ok) throw new Error();
    badge.className = 'api-badge ok';
    badge.innerHTML = `<span class="dot"></span>Legacy 8005 OK`;
  } catch {
    badge.className = 'api-badge';
    badge.innerHTML = `<span class="dot"></span>Legacy 8005`;
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
