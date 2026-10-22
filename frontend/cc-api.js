/**
 * cc-api.js — API client cho AI Video Command Center
 * Contract: 0.1.0-draft
 * Phiên bản registry: 1.0.0
 * Ngôn ngữ UI: tiếng Việt
 *
 * Tách rõ:
 *  - MockApiClient  → đọc fixture tĩnh phiên bản 1.0.0, KHÔNG gọi API thật
 *  - RealApiClient  → gọi FastAPI /api/v1 với Bearer token và Idempotency-Key
 *
 * Mọi dữ liệu mock được đánh dấu rõ ràng trong UI (_mock: true).
 * Không tự chuyển sang mock khi API thật lỗi.
 */

/* ────────────────────────────────────────────────────────────
   CONFIG — lưu trữ trong localStorage hoặc window.__CC_CONFIG
   ──────────────────────────────────────────────────────────── */
const savedConfig = (() => {
  try {
    const raw = localStorage.getItem('cc_config');
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
})();

const CC_CONFIG = {
  /** "mock" | "real" */
  mode: (savedConfig && savedConfig.mode) || (window.__CC_CONFIG && window.__CC_CONFIG.mode) || 'mock',
  /** Base URL của API mới — mặc định same-origin /api/v1 qua cổng 443 HTTPS */
  apiBase: (savedConfig && savedConfig.apiBase) || (window.__CC_CONFIG && window.__CC_CONFIG.apiBase) || '/api/v1',
  /** Opaque Bearer token cho local owner */
  authToken: (savedConfig && savedConfig.authToken) || (window.__CC_CONFIG && window.__CC_CONFIG.authToken) || '',
};

function saveConfig(newConfig) {
  Object.assign(CC_CONFIG, newConfig);
  try {
    localStorage.setItem('cc_config', JSON.stringify(CC_CONFIG));
  } catch (e) {
    console.warn('Không thể lưu cc_config vào localStorage:', e);
  }
}

/* ────────────────────────────────────────────────────────────
   HELPERS
   ──────────────────────────────────────────────────────────── */
function uuid4() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0;
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}

function rfc3339(d = new Date()) { return d.toISOString(); }

/** Làm ngắn UUID để hiển thị */
function shortId(id = '') { return (id || '').slice(0, 8); }

/** Tên trạng thái tiếng Việt */
const STATUS_LABEL = {
  queued:           'Đang chờ',
  running:          'Đang chạy',
  cancelling:       'Đang dừng',
  needs_review:     'Cần duyệt',
  needs_attention:  'Cần xem xét',
  failed:           'Lỗi',
  cancelled:        'Đã huỷ',
  succeeded:        'Hoàn tất',
  online:           'Trực tuyến',
  offline:          'Ngoại tuyến',
  disabled:         'Vô hiệu',
};
function statusLabel(s) { return STATUS_LABEL[s] || s; }

/** Format thời gian ngắn (tiếng Việt) */
function relativeTime(iso) {
  if (!iso) return '—';
  const ms = Date.now() - new Date(iso).getTime();
  if (ms < 0) return 'vừa xong';
  if (ms < 60_000) return `${Math.floor(ms/1000)}s trước`;
  if (ms < 3_600_000) return `${Math.floor(ms/60_000)} phút trước`;
  if (ms < 86_400_000) return `${Math.floor(ms/3_600_000)} giờ trước`;
  return new Date(iso).toLocaleDateString('vi-VN');
}

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('vi-VN', { hour12: false });
}

function formatBytes(b) {
  if (!b && b !== 0) return '—';
  if (b < 1024) return b + ' B';
  if (b < 1048576) return (b/1024).toFixed(1) + ' KB';
  return (b/1048576).toFixed(1) + ' MB';
}

/* ────────────────────────────────────────────────────────────
   FIXTURE DATA (mock)
   Phiên bản registry: 1.0.0 (đồng bộ với command_center/registry.py)
   ──────────────────────────────────────────────────────────── */
const NOW = () => new Date().toISOString();
const T = (minAgo) => new Date(Date.now() - minAgo * 60_000).toISOString();

const FIXTURES = {
  health: { status: 'ok', api_version: '0.1.0-draft', _mock: true },
  ready: { status: 'ready', database: 'ready', _mock: true },

  agents: {
    _mock: true,
    items: [
      {
        id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
        status: 'online',
        last_seen_at: T(0.2),
        capabilities: ['media.probe', 'render.basic'],
        active_task_count: 0,
        machine_label: 'CPU Pilot Agent (Localhost Windows)',
      },
      {
        id: 'agt-windows-gpu0',
        status: 'offline',
        last_seen_at: T(45),
        capabilities: ['render.compose', 'render.rerender'],
        active_task_count: 0,
        machine_label: 'RTX 5060 Ti — chờ adapter GPU',
      },
    ],
    next_cursor: null,
  },

  modules: {
    _mock: true,
    items: [
      { id: 'media.probe',    version: '1.0.0', resource: 'cpu:0', actions: ['run'], available: true,  unavailable_reason: null, label: 'Phân tích thông số media (CPU)' },
      { id: 'render.basic',   version: '1.0.0', resource: 'cpu:0', actions: ['run'], available: true,  unavailable_reason: null, label: 'Render cơ bản CPU libx264 — giữ audio' },
      { id: 'render.compose', version: '1.0.0', resource: 'gpu:0', actions: ['run'], available: false, unavailable_reason: 'Chưa tích hợp adapter trong đợt CPU pilot', label: 'Render tổng hợp GPU' },
      { id: 'render.rerender',version: '1.0.0', resource: 'gpu:0', actions: ['rerender'], available: false, unavailable_reason: 'Chưa tích hợp adapter trong đợt CPU pilot', label: 'Render lại hình từ packet' },
    ],
  },

  presets: {
    _mock: true,
    items: [
      {
        id: 'basic_render',
        version: '1.0.0',
        label: 'Render cơ bản CPU — giữ âm thanh gốc',
        available: true,
        modules: ['media.probe', 'render.basic'],
        override_schema: {
          width: { type: 'integer', enum: [360, 720, 1080], default: 720 },
          height: { type: 'integer', enum: [640, 1280, 1920], default: 1280 },
        },
      },
      {
        id: 'inspect_media',
        version: '1.0.0',
        label: 'Kiểm tra thông số video',
        available: true,
        modules: ['media.probe'],
        override_schema: {},
      },
      {
        id: 'wuby',
        version: '1.0.0',
        label: 'Wuby — đang tích hợp adapter',
        available: false,
        modules: ['render.compose'],
        unavailable_reason: 'Chưa tích hợp adapter trong đợt CPU pilot',
        override_schema: {},
      },
      {
        id: 'cauhinh2',
        version: '1.0.0',
        label: 'Film review black — đang tích hợp',
        available: false,
        modules: ['render.compose'],
        unavailable_reason: 'Chưa tích hợp adapter trong đợt CPU pilot',
        override_schema: {},
      },
      {
        id: 'cauhinh3',
        version: '1.0.0',
        label: 'Movie clone — đang tích hợp',
        available: false,
        modules: ['render.compose'],
        unavailable_reason: 'Chưa tích hợp adapter trong đợt CPU pilot',
        override_schema: {},
      },
      {
        id: 'cauhinh3_wuby',
        version: '1.0.0',
        label: 'Wuby AI giữ nền — đang tích hợp',
        available: false,
        modules: ['render.compose'],
        unavailable_reason: 'Chưa tích hợp adapter trong đợt CPU pilot',
        override_schema: {},
      },
      {
        id: 'chidepdicau',
        version: '1.0.0',
        label: 'Chị đẹp đi câu — đang tích hợp',
        available: false,
        modules: ['render.compose'],
        unavailable_reason: 'Chưa tích hợp adapter trong đợt CPU pilot',
        override_schema: {},
      },
      {
        id: 'song1minhcogivui',
        version: '1.0.0',
        label: 'Sống một mình — đang tích hợp',
        available: false,
        modules: ['render.compose'],
        unavailable_reason: 'Chưa tích hợp adapter trong đợt CPU pilot',
        override_schema: {},
      },
    ],
  },

  projects: {
    _mock: true,
    items: [
      { id: '3f1d6b47-7713-407b-9149-78736ed7750f', name: 'Dự án CPU Pilot (Smoke Test)', version: 2, archived_at: null, created_at: T(120), updated_at: T(5) },
      { id: '11111111-1111-4111-8111-111111111111', name: 'Kênh Wuby — Tháng 10', version: 3, archived_at: null, created_at: T(60*48), updated_at: T(10) },
      { id: '22222222-2222-4222-8222-222222222222', name: 'Film Review Black', version: 1, archived_at: null, created_at: T(60*24), updated_at: T(120) },
    ],
    next_cursor: null,
  },

  // Job hoàn thành từ CPU Pilot thật (PostgreSQL Docker dev)
  jobPilotComplete: {
    _mock: true,
    id: 'a6d0fab3-9081-4a31-81c4-4a5f3ce1aae2',
    project_id: '3f1d6b47-7713-407b-9149-78736ed7750f',
    preset_id: 'basic_render',
    preset_version: '1.0.0',
    status: 'needs_review',
    version: 4,
    created_at: T(25),
    updated_at: T(20),
    progress: { completed_tasks: 2, total_tasks: 2, percent: 100 },
    current_task_id: null,
    error: null,
    tasks: [
      {
        id: 'effd51cb-4912-4030-a865-5d5c1c724257',
        task_key: 'probe',
        module: 'media.probe',
        action: 'run',
        module_version: '1.0.0',
        status: 'succeeded',
        attempt: 1,
        depends_on: [],
        error: null,
      },
      {
        id: '706e0d00-6777-4820-b148-0ac476d10aa3',
        task_key: 'basic_render',
        module: 'render.basic',
        action: 'run',
        module_version: '1.0.0',
        status: 'succeeded',
        attempt: 1,
        depends_on: ['effd51cb-4912-4030-a865-5d5c1c724257'],
        error: null,
      },
    ],
    outputs: [
      {
        id: 'f5d34973-487e-4794-be6b-ff927eb83218',
        kind: 'video',
        media_type: 'video/mp4',
        size_bytes: 184520,
        sha256: '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
        verification: 'verified',
        playback_url: null,
        expires_at: null,
      },
      {
        id: 'rep-smoke-001',
        kind: 'report',
        media_type: 'application/json',
        size_bytes: 1391,
        sha256: null,
        verification: 'verified',
        playback_url: null,
        expires_at: null,
      },
    ],
    qc: {
      warnings: [],
      score: 100,
      media: {
        duration: 1.0,
        width: 720,
        height: 1280,
        fps: '24/1',
        has_audio: true,
        codec: 'h264',
        frames: 24,
      },
    },
  },

  jobRunning: {
    _mock: true,
    id: 'aaaa0001-0000-4000-8000-000000000001',
    project_id: '3f1d6b47-7713-407b-9149-78736ed7750f',
    preset_id: 'basic_render',
    preset_version: '1.0.0',
    status: 'running',
    version: 2,
    created_at: T(3),
    updated_at: T(0.3),
    progress: { completed_tasks: 1, total_tasks: 2, percent: null },
    current_task_id: 'task-r2',
    error: null,
    tasks: [
      { id: 'task-r1', task_key: 'probe', module: 'media.probe', action: 'run', module_version: '1.0.0', status: 'succeeded', attempt: 1, depends_on: [], error: null },
      { id: 'task-r2', task_key: 'basic_render', module: 'render.basic', action: 'run', module_version: '1.0.0', status: 'running', attempt: 1, depends_on: ['task-r1'], error: null },
    ],
  },

  jobQueued: {
    _mock: true,
    id: '33333333-3333-4333-8333-333333333333',
    project_id: '11111111-1111-4111-8111-111111111111',
    preset_id: 'basic_render',
    preset_version: '1.0.0',
    status: 'queued',
    version: 1,
    created_at: T(1),
    updated_at: T(1),
    progress: { completed_tasks: 0, total_tasks: 2, percent: null },
    current_task_id: null,
    error: null,
    tasks: [
      { id: 'task-q1', task_key: 'probe', module: 'media.probe', action: 'run', module_version: '1.0.0', status: 'queued', attempt: 0, depends_on: [], error: null },
      { id: 'task-q2', task_key: 'basic_render', module: 'render.basic', action: 'run', module_version: '1.0.0', status: 'queued', attempt: 0, depends_on: ['task-q1'], error: null },
    ],
  },

  jobFailed: {
    _mock: true,
    id: 'bbbb0001-0000-4000-8000-000000000001',
    project_id: '22222222-2222-4222-8222-222222222222',
    preset_id: 'basic_render',
    preset_version: '1.0.0',
    status: 'failed',
    version: 3,
    created_at: T(90),
    updated_at: T(60),
    progress: { completed_tasks: 1, total_tasks: 2, percent: null },
    current_task_id: null,
    error: { code: 'RENDER_FAILED', message: 'FFmpeg CPU process kết thúc với exit code 1: codec không tương thích.' },
    tasks: [
      { id: 'task-b1', task_key: 'probe', module: 'media.probe', action: 'run', module_version: '1.0.0', status: 'succeeded', attempt: 1, depends_on: [], error: null },
      { id: 'task-b2', task_key: 'basic_render', module: 'render.basic', action: 'run', module_version: '1.0.0', status: 'failed', attempt: 3, depends_on: ['task-b1'], error: { code: 'RENDER_FAILED', message: 'FFmpeg CPU process exit code 1' } },
    ],
  },

  jobCancelling: {
    _mock: true,
    id: 'cccc0001-0000-4000-8000-000000000001',
    project_id: '11111111-1111-4111-8111-111111111111',
    preset_id: 'basic_render',
    preset_version: '1.0.0',
    status: 'cancelling',
    version: 2,
    created_at: T(5),
    updated_at: T(0.2),
    progress: { completed_tasks: 0, total_tasks: 2, percent: null },
    current_task_id: 'task-c1',
    error: null,
    tasks: [
      { id: 'task-c1', task_key: 'basic_render', module: 'render.basic', action: 'run', module_version: '1.0.0', status: 'running', attempt: 1, depends_on: [], error: null },
    ],
  },

  jobNeedsAttention: {
    _mock: true,
    id: 'dddd0001-0000-4000-8000-000000000001',
    project_id: '22222222-2222-4222-8222-222222222222',
    preset_id: 'basic_render',
    preset_version: '1.0.0',
    status: 'needs_attention',
    version: 2,
    created_at: T(180),
    updated_at: T(150),
    progress: { completed_tasks: 0, total_tasks: 2, percent: null },
    current_task_id: 'task-d1',
    error: { code: 'AGENT_LEASE_EXPIRED', message: 'Agent mất kết nối quá 45s trong lúc thực thi task. Cần đối soát tài nguyên.' },
    tasks: [
      { id: 'task-d1', task_key: 'basic_render', module: 'render.basic', action: 'run', module_version: '1.0.0', status: 'running', attempt: 1, depends_on: [], error: { code: 'AGENT_LEASE_EXPIRED', message: 'Mất heartbeat' } },
    ],
  },

  events: {
    _mock: true,
    items: [
      { id: 'ev-01', timestamp: T(24), level: 'info', code: 'TASK_CLAIMED', message: 'Agent aaaaaaaa claimed task basic_render (attempt 1)' },
      { id: 'ev-02', timestamp: T(22), level: 'info', code: 'FFMPEG_STARTED', message: 'libx264 720x1280 24fps started via CPU basic render' },
      { id: 'ev-03', timestamp: T(20), level: 'info', code: 'TASK_COMPLETED', message: 'Task basic_render completed in 1.42s; output verified' },
      { id: 'ev-04', timestamp: T(20), level: 'info', code: 'JOB_NEEDS_REVIEW', message: 'Job hoàn tất pipeline technical, chuyển sang needs_review' },
    ],
  },

  error409: {
    error: {
      code: 'CONFLICT',
      message: 'expected_version không khớp. Dữ liệu đã thay đổi bởi thao tác khác. Hãy tải lại trang.',
      request_id: 'mock-req-409',
    },
  },
  error422: {
    error: {
      code: 'VALIDATION_ERROR',
      message: 'Dữ liệu gửi lên không đúng định dạng schema 0.1.0-draft.',
      request_id: 'mock-req-422',
    },
  },
  errorModuleNotReady: {
    error: {
      code: 'MODULE_NOT_READY',
      message: 'Module yêu cầu chưa sẵn sàng trên bất kỳ Agent nào trực tuyến.',
      request_id: 'mock-req-409-mod',
    },
  },
};

/* ────────────────────────────────────────────────────────────
   MOCK API CLIENT (chạy hoàn toàn bằng fixture trong trình duyệt)
   ──────────────────────────────────────────────────────────── */
class MockApiClient {
  isMock = true;

  _delay(ms = 150) { return new Promise(r => setTimeout(r, ms + Math.random() * 50)); }

  async health() { await this._delay(60); return { ...FIXTURES.health }; }
  async ready()  { await this._delay(60); return { ...FIXTURES.ready }; }

  async getAgents() { await this._delay(); return { ...FIXTURES.agents }; }
  async getModules() { await this._delay(); return { ...FIXTURES.modules }; }
  async getPresets() { await this._delay(); return { ...FIXTURES.presets }; }

  async getProjects() { await this._delay(); return { ...FIXTURES.projects }; }
  async getProject(id) {
    await this._delay();
    const p = FIXTURES.projects.items.find(x => x.id === id);
    if (!p) throw { status: 404, body: { error: { code: 'NOT_FOUND', message: 'Dự án không tồn tại.' } } };
    return { ...p };
  }
  async createProject(name) {
    await this._delay(250);
    const p = { id: uuid4(), name, version: 1, archived_at: null, created_at: NOW(), updated_at: NOW(), _mock: true };
    FIXTURES.projects.items.unshift(p);
    return p;
  }
  async updateProject(id, name, expectedVersion) {
    await this._delay(150);
    const p = FIXTURES.projects.items.find(x => x.id === id);
    if (!p) throw { status: 404, body: { error: { code: 'NOT_FOUND', message: 'Dự án không tồn tại.' } } };
    if (p.version !== expectedVersion) throw { status: 409, body: FIXTURES.error409 };
    p.name = name; p.version++; p.updated_at = NOW();
    return { ...p };
  }

  _allMockJobs() {
    return [
      FIXTURES.jobPilotComplete,
      FIXTURES.jobRunning,
      FIXTURES.jobQueued,
      FIXTURES.jobFailed,
      FIXTURES.jobCancelling,
      FIXTURES.jobNeedsAttention,
    ];
  }

  async getProjectJobs(projectId, { status, cursor } = {}) {
    await this._delay();
    const all = this._allMockJobs().filter(j => j.project_id === projectId);
    const filtered = status ? all.filter(j => j.status === status) : all;
    return { _mock: true, items: filtered, next_cursor: null };
  }

  async getAllJobs({ status } = {}) {
    await this._delay();
    const all = this._allMockJobs();
    const filtered = status ? all.filter(j => j.status === status) : all;
    return { _mock: true, items: filtered, next_cursor: null };
  }

  async getJob(id) {
    await this._delay();
    const j = this._allMockJobs().find(x => x.id === id);
    if (!j) throw { status: 404, body: { error: { code: 'NOT_FOUND', message: 'Job không tồn tại.' } } };
    return { ...j };
  }

  async createJob(payload) {
    await this._delay(300);
    const preset = (FIXTURES.presets.items || []).find(p => p.id === payload.preset_id);
    if (preset && !preset.available) {
      throw { status: 409, body: FIXTURES.errorModuleNotReady };
    }
    if (!payload.input_refs || payload.input_refs.length === 0) {
      throw { status: 422, body: FIXTURES.error422 };
    }
    const job = {
      ...FIXTURES.jobQueued,
      id: uuid4(),
      project_id: payload.project_id,
      preset_id: payload.preset_id,
      preset_version: payload.preset_version || '1.0.0',
      created_at: NOW(), updated_at: NOW(),
      _mock: true,
    };
    return job;
  }

  async cancelJob(id, expectedVersion) {
    await this._delay(150);
    return { id, status: 'cancelling', version: expectedVersion + 1, updated_at: NOW(), _mock: true };
  }

  async retryJob(id, expectedVersion) {
    await this._delay(150);
    return { id, status: 'queued', version: expectedVersion + 1, updated_at: NOW(), _mock: true };
  }

  async getJobEvents(id) { await this._delay(); return { ...FIXTURES.events }; }
  async getJobOutputs(id) {
    await this._delay();
    const j = this._allMockJobs().find(x => x.id === id);
    return { _mock: true, items: j?.outputs || FIXTURES.jobPilotComplete.outputs || [] };
  }
  async getProjectFiles(projectId) {
    await this._delay();
    return {
      _mock: true,
      items: [
        {
          id: 'f5d34973-487e-4794-be6b-ff927eb83218',
          kind: 'video',
          media_type: 'video/mp4',
          size_bytes: 1842900,
          sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
          verification: 'verified',
        },
      ],
    };
  }

  getFileContentUrl(fileId) {
    return null; // Mock mode không stream binary thật
  }

  async fetchFileBlobUrl(fileId) {
    return null;
  }

  async fetchFileJson(fileId) {
    return null;
  }
}

/* ────────────────────────────────────────────────────────────
   REAL API CLIENT (gọi FastAPI /api/v1 có xác thực Bearer)
   ──────────────────────────────────────────────────────────── */
class RealApiClient {
  isMock = false;

  constructor(base, token) {
    this.base = (base || '/api/v1').replace(/\/+$/, '');
    this.token = token || (CC_CONFIG && CC_CONFIG.authToken) || '';
  }

  setToken(t) {
    this.token = t || '';
  }

  setBase(b) {
    this.base = (b || '/api/v1').replace(/\/+$/, '');
  }

  async _fetch(method, path, body, headers = {}) {
    const defaultHeaders = {
      'Content-Type': 'application/json',
      ...headers,
    };
    if (this.token) {
      defaultHeaders['Authorization'] = `Bearer ${this.token}`;
    }
    const opts = { method, headers: defaultHeaders };
    if (body !== undefined) opts.body = JSON.stringify(body);

    let res;
    try {
      res = await fetch(this.base + path, opts);
    } catch (networkErr) {
      throw {
        status: 0,
        body: {
          error: {
            code: 'NETWORK_ERROR',
            message: `Không thể kết nối đến API backend tại ${this.base}. Kiểm tra server đang chạy hoặc CORS/Direct IP restriction.`,
            details: [String(networkErr)],
          },
        },
      };
    }

    const json = await res.json().catch(() => null);
    if (!res.ok) throw { status: res.status, body: json };
    return json;
  }

  async health() { return this._fetch('GET', '/health'); }
  async ready()  { return this._fetch('GET', '/ready'); }
  async getAgents() { return this._fetch('GET', '/agents'); }
  async getModules() { return this._fetch('GET', '/modules'); }
  async getPresets() { return this._fetch('GET', '/presets'); }

  async getProjects(cursor, limit = 25) {
    const q = cursor ? `?cursor=${encodeURIComponent(cursor)}&limit=${limit}` : `?limit=${limit}`;
    return this._fetch('GET', `/projects${q}`);
  }
  async getProject(id) { return this._fetch('GET', `/projects/${id}`); }
  async createProject(name) { return this._fetch('POST', '/projects', { name }, { 'Idempotency-Key': uuid4() }); }
  async updateProject(id, name, expectedVersion) { return this._fetch('PATCH', `/projects/${id}`, { name, expected_version: expectedVersion }); }
  async archiveProject(id, expectedVersion) { return this._fetch('DELETE', `/projects/${id}`, { expected_version: expectedVersion }); }

  async getProjectJobs(projectId, { status, cursor, limit = 25 } = {}) {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    if (cursor) params.set('cursor', cursor);
    if (limit) params.set('limit', limit);
    const qs = params.toString() ? `?${params.toString()}` : '';
    return this._fetch('GET', `/projects/${projectId}/jobs${qs}`);
  }

  async getAllJobs({ status, cursor, limit = 25 } = {}) {
    try {
      const params = new URLSearchParams();
      if (status) params.set('status', status);
      if (cursor) params.set('cursor', cursor);
      if (limit) params.set('limit', limit);
      const qs = params.toString() ? `?${params.toString()}` : '';
      const res = await this._fetch('GET', `/jobs${qs}`);
      const items = (res.items || []).slice();
      items.sort((a, b) => new Date(b.updated_at || 0) - new Date(a.updated_at || 0));
      return { items, next_cursor: res.next_cursor || null };
    } catch (err) {
      if (err && err.status && err.status !== 404 && err.status !== 405) throw err;
      const projRes = await this.getProjects();
      const projs = projRes.items || [];
      const jobPromises = projs.map(p =>
        this.getProjectJobs(p.id, { status }).catch(() => ({ items: [] }))
      );
      const results = await Promise.all(jobPromises);
      const allItems = results.flatMap(r => r.items || []);
      allItems.sort((a, b) => new Date(b.updated_at || 0) - new Date(a.updated_at || 0));
      return { items: allItems };
    }
  }

  async getProjectFiles(projectId) {
    if (!projectId) return { items: [] };
    return this._fetch('GET', `/projects/${projectId}/files`).catch(() => ({ items: [] }));
  }

  async getJob(id) { return this._fetch('GET', `/jobs/${id}`); }
  async createJob(payload) { return this._fetch('POST', '/jobs', payload, { 'Idempotency-Key': uuid4() }); }
  async cancelJob(id, expectedVersion) { return this._fetch('POST', `/jobs/${id}/cancel`, { expected_version: expectedVersion }, { 'Idempotency-Key': uuid4() }); }
  async retryJob(id, expectedVersion) { return this._fetch('POST', `/jobs/${id}/retry`, { expected_version: expectedVersion }, { 'Idempotency-Key': uuid4() }); }
  async getJobEvents(id) { return this._fetch('GET', `/jobs/${id}/events`); }
  async getJobOutputs(id) { return this._fetch('GET', `/jobs/${id}/outputs`); }

  getFileContentUrl(fileId) {
    if (!fileId) return null;
    return `${this.base}/files/${fileId}/content`;
  }

  async fetchFileBlobUrl(fileId) {
    const url = this.getFileContentUrl(fileId);
    if (!url) return null;
    const headers = {};
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`;
    const res = await fetch(url, { headers });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    return URL.createObjectURL(blob);
  }

  async fetchFileJson(fileId) {
    const url = this.getFileContentUrl(fileId);
    if (!url) return null;
    const headers = {};
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`;
    const res = await fetch(url, { headers });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  }
}

/* ────────────────────────────────────────────────────────────
   KHỞI TẠO CLIENT
   ──────────────────────────────────────────────────────────── */
function createClient(mode = CC_CONFIG.mode) {
  if (mode === 'real') {
    return new RealApiClient(CC_CONFIG.apiBase, CC_CONFIG.authToken);
  }
  return new MockApiClient();
}

let currentApi = createClient();

// Expose to global window
window.CC_API = currentApi;
window.CC_CONFIG = CC_CONFIG;
window.ccSaveConfig = saveConfig;
window.ccSwitchMode = function(newMode, newBase, newToken) {
  saveConfig({
    mode: newMode,
    apiBase: newBase !== undefined ? newBase : CC_CONFIG.apiBase,
    authToken: newToken !== undefined ? newToken : CC_CONFIG.authToken,
  });
  window.CC_API = createClient(newMode);
  currentApi = window.CC_API;
  return currentApi;
};
window.ccUtil = { statusLabel, relativeTime, formatDate, formatBytes, shortId, uuid4, NOW };
