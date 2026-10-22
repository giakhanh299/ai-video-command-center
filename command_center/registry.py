"""Explicit registry. Nothing in JSON is imported or executed as a command."""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from jsonschema import Draft202012Validator, FormatChecker

from .errors import DomainError
from .models import CreateJob, Manifest, VERSION

MODULE_VERSION = "1.0.0"
EMPTY_CONFIG = {"type": "object", "properties": {}, "additionalProperties": False}
BASIC_CONFIG = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "width": {"type": "integer", "enum": [360, 720, 1080]},
        "height": {"type": "integer", "enum": [640, 1280, 1920]},
        "preset_profile": {"type": "string"},
        "fit_mode": {"type": "string", "enum": ["contain", "cover", "blur_bg"]},
        "voice_id": {"type": "string", "enum": [
            "original",
            "vi_female_north_ngochuyen",
            "vi_male_north_minhquang",
            "vi_female_south_thaovy",
            "vi_male_review_tram",
            "wuby_clone_v2",
            "omnivoice_auto",
        ]},
        "voice_speed": {"type": "number", "minimum": 0.5, "maximum": 2.0},
        "keep_original_audio": {"type": "boolean"},
        "bgm_style": {"type": "string", "enum": ["none", "cinematic_tension", "chill_lofi", "upbeat_viral", "emotional_piano"]},
        "blur_subtitle": {"type": "boolean"},
        "blur_mode": {"type": "string", "enum": ["none", "gaussian_box", "feather_dark", "ai_inpaint"]},
        "blur_height_pct": {"type": "integer", "minimum": 5, "maximum": 50},
        "blur_x_pct": {"type": "integer", "minimum": 0, "maximum": 95},
        "blur_y_pct": {"type": "integer", "minimum": 0, "maximum": 95},
        "blur_w_pct": {"type": "integer", "minimum": 5, "maximum": 100},
        "blur_h_pct": {"type": "integer", "minimum": 5, "maximum": 80},
        "blur_strength": {"type": "integer", "minimum": 2, "maximum": 50},
        "channel_id": {"type": "string", "maxLength": 64},
        "subtitle_style": {"type": "string", "enum": ["none", "karaoke_pop", "review_yellow_box", "neon_glow", "minimal_white"]},
        "banner_text": {"type": "string", "maxLength": 120},
        "marquee_text": {"type": "string", "maxLength": 200},
        "text_position": {"type": "string", "enum": ["bottom", "middle", "top"]},
        "mirror_flip": {"type": "boolean"},
        "color_grade": {"type": "string", "enum": ["natural", "cinematic_warm", "film_contrast", "vibrant_tiktok", "noir_bw"]},
    }, "required": ["width", "height"],
}
MODULES = {
    "media.probe": {"config_schema": EMPTY_CONFIG, "resource": "cpu:0", "available": True},
    "render.basic": {"config_schema": BASIC_CONFIG, "resource": "cpu:0", "available": True},
    "render.compose": {"config_schema": EMPTY_CONFIG, "resource": "gpu:0", "available": False},
    "render.rerender": {"config_schema": EMPTY_CONFIG, "resource": "gpu:0", "available": False},
}
PRESET_DEFAULTS = {
    "basic_render": {
        "width": 720, "height": 1280, "fit_mode": "contain",
        "voice_id": "original", "voice_speed": 1.0, "keep_original_audio": True, "bgm_style": "none",
        "blur_subtitle": False, "blur_mode": "none", "blur_height_pct": 22, "blur_strength": 18,
        "subtitle_style": "none", "banner_text": "", "marquee_text": "", "text_position": "bottom",
        "mirror_flip": False, "color_grade": "natural",
    },
    "cauhinh2": {
        "width": 720, "height": 1280, "fit_mode": "contain",
        "voice_id": "vi_male_review_tram", "voice_speed": 1.05, "keep_original_audio": True, "bgm_style": "cinematic_tension",
        "blur_subtitle": True, "blur_mode": "gaussian_box", "blur_height_pct": 24, "blur_strength": 22,
        "subtitle_style": "review_yellow_box", "banner_text": "REVIEW PHIM HAY", "marquee_text": "Theo dõi kênh để xem phần tiếp theo!", "text_position": "bottom",
        "mirror_flip": False, "color_grade": "film_contrast",
    },
    "cauhinh3": {
        "width": 720, "height": 1280, "fit_mode": "blur_bg",
        "voice_id": "vi_female_north_ngochuyen", "voice_speed": 1.05, "keep_original_audio": True, "bgm_style": "upbeat_viral",
        "blur_subtitle": True, "blur_mode": "gaussian_box", "blur_height_pct": 22, "blur_strength": 20,
        "subtitle_style": "karaoke_pop", "banner_text": "", "marquee_text": "Đừng quên thả tim và bấm theo dõi kênh nhé!", "text_position": "bottom",
        "mirror_flip": True, "color_grade": "vibrant_tiktok",
    },
    "cauhinh3_wuby": {
        "width": 720, "height": 1280, "fit_mode": "cover",
        "voice_id": "wuby_clone_v2", "voice_speed": 1.0, "keep_original_audio": True, "bgm_style": "emotional_piano",
        "blur_subtitle": True, "blur_mode": "ai_inpaint", "blur_height_pct": 20, "blur_strength": 16,
        "subtitle_style": "karaoke_pop", "banner_text": "WUBY AI STUDIO", "marquee_text": "Bản thuyết minh AI giữ nền tự động", "text_position": "bottom",
        "mirror_flip": False, "color_grade": "cinematic_warm",
    },
    "chidepdicau": {
        "width": 720, "height": 1280, "fit_mode": "blur_bg",
        "voice_id": "vi_female_north_ngochuyen", "voice_speed": 1.05, "keep_original_audio": True, "bgm_style": "upbeat_viral",
        "blur_subtitle": True, "blur_mode": "gaussian_box", "blur_height_pct": 25, "blur_strength": 20,
        "subtitle_style": "neon_glow", "banner_text": "CHỊ ĐẸP ĐI CÂU", "marquee_text": "Hành trình săn cá khủng mỗi ngày!", "text_position": "bottom",
        "mirror_flip": False, "color_grade": "vibrant_tiktok",
    },
    "song1minhcogivui": {
        "width": 720, "height": 1280, "fit_mode": "contain",
        "voice_id": "vi_female_south_thaovy", "voice_speed": 1.0, "keep_original_audio": True, "bgm_style": "chill_lofi",
        "blur_subtitle": True, "blur_mode": "feather_dark", "blur_height_pct": 20, "blur_strength": 18,
        "subtitle_style": "minimal_white", "banner_text": "SỐNG MỘT MÌNH CÓ GÌ VUI", "marquee_text": "Nhật ký chill mỗi tối một mình", "text_position": "bottom",
        "mirror_flip": False, "color_grade": "cinematic_warm",
    },
    "chuyen_hai_dua": {
        "width": 720, "height": 1280, "fit_mode": "blur_bg",
        "voice_id": "omnivoice_auto", "voice_speed": 1.0, "keep_original_audio": True, "bgm_style": "emotional_piano",
        "blur_subtitle": True, "blur_mode": "ai_inpaint", "blur_height_pct": 18, "blur_strength": 18,
        "blur_x_pct": 6, "blur_y_pct": 72, "blur_w_pct": 88, "blur_h_pct": 18,
        "subtitle_style": "karaoke_pop", "banner_text": "CHUYỆN HAI ĐỨA", "marquee_text": "@ChuyenHaiDua · Thuyết minh đa giọng Nam/Nữ giữ nền 5.1", "text_position": "bottom",
        "mirror_flip": False, "color_grade": "cinematic_warm",
    },
}
PRESETS = {
    "inspect_media": {"label": "Kiểm tra thông số video (Probe JSON)", "modules": ["media.probe"], "available": True},
    "basic_render": {"label": " Đa cấu hình Tự do — Tuỳ chỉnh Giọng đọc, Blur & Chạy chữ", "modules": ["media.probe", "render.basic"], "available": True},
    "cauhinh2": {"label": "Cấu hình 2 — Review Phim Viền Đen + Blur Sub + Voice Trầm", "modules": ["media.probe", "render.basic"], "available": True},
    "cauhinh3": {"label": "Cấu hình 3 — Movie Clone Nền Mờ 9:16 + Karaoke + Lật Gương", "modules": ["media.probe", "render.basic"], "available": True},
    "cauhinh3_wuby": {"label": "Cấu hình 3 Wuby — Giọng Wuby Clone + Xoá Sub Giữ Nền", "modules": ["media.probe", "render.basic"], "available": True},
    "chuyen_hai_dua": {"label": "Chuyện Hai Đứa (@ChuyenHaiDua) — Đa Giọng Nam/Nữ Character-Lock + 5.1 Smart", "modules": ["media.probe", "render.basic"], "available": True},
    "chidepdicau": {"label": "Kênh Chị Đẹp Đi Câu — Voice Nữ Bắc + Banner Hook + Blur Sub", "modules": ["media.probe", "render.basic"], "available": True},
    "song1minhcogivui": {"label": "Kênh Sống Một Mình — Voice Nữ Nam + Chill Lo-Fi + Sub Tối Giản", "modules": ["media.probe", "render.basic"], "available": True},
    "wuby": {"label": "Wuby GPU Legacy — chỉ chạy trên cụm GPU nội bộ", "modules": ["render.compose"], "available": False},
}


def validate_manifest(data: dict) -> Manifest:
    try:
        manifest = Manifest.model_validate(data)
        created = datetime.fromisoformat(manifest.created_at.replace("Z", "+00:00"))
        if created.tzinfo is None or created.utcoffset() is None:
            raise ValueError("Timezone required")
        if len(set(manifest.input_refs)) != len(manifest.input_refs):
            raise ValueError("Duplicate input")
        ids = {t.task_id for t in manifest.pipeline}
        if len(ids) != len(manifest.pipeline) or len({t.task_key for t in manifest.pipeline}) != len(ids):
            raise ValueError("Duplicate task")
        graph = {}
        for task in manifest.pipeline:
            module = MODULES.get(task.module)
            if not module or not module["available"] or task.module_version != MODULE_VERSION:
                raise ValueError("Unregistered module")
            Draft202012Validator(module["config_schema"]).validate(task.config)
            if len(set(task.depends_on)) != len(task.depends_on) or not set(task.depends_on) <= ids:
                raise ValueError("Invalid dependency")
            if not set(task.input_refs) <= set(manifest.input_refs):
                raise ValueError("Unbound input")
            if len(set(task.input_refs)) != len(task.input_refs) or len(set(task.output_refs)) != len(task.output_refs):
                raise ValueError("Duplicate reference")
            graph[task.task_id] = task.depends_on
        done, visiting = set(), set()

        def visit(node):
            if node in visiting:
                raise ValueError("Cycle")
            if node in done:
                return
            visiting.add(node)
            for dep in graph[node]:
                visit(dep)
            visiting.remove(node)
            done.add(node)

        for node in graph:
            visit(node)
        return manifest
    except Exception as exc:
        raise DomainError("INVALID_MANIFEST", 422) from exc


def make_manifest(request: CreateJob, job_id, created_at):
    preset = PRESETS.get(request.preset_id)
    if not preset or request.preset_version != MODULE_VERSION:
        raise DomainError("INVALID_PRESET", 422)
    if not preset["available"]:
        raise DomainError("MODULE_NOT_READY")
    if len(request.input_refs) != 1:
        raise DomainError("SINGLE_VIDEO_REQUIRED", 422)
    if request.overrides.title:
        raise DomainError("OVERRIDE_NOT_SUPPORTED", 422)
    if request.preset_id == "inspect_media" and (request.overrides.width is not None or request.overrides.height is not None):
        raise DomainError("OVERRIDE_NOT_SUPPORTED", 422)

    defaults = PRESET_DEFAULTS.get(request.preset_id, {})
    width = request.overrides.width or defaults.get("width", 720)
    height = request.overrides.height or defaults.get("height", 1280)

    raw_overrides = request.overrides.model_dump(exclude_none=True)
    raw_overrides.pop("title", None)
    has_extra_overrides = any(k not in ("width", "height") for k in raw_overrides)

    if request.preset_id == "basic_render" and not has_extra_overrides:
        compose_config = {"width": width, "height": height}
    else:
        compose_config = {**defaults, **raw_overrides, "width": width, "height": height, "preset_profile": request.preset_id}

    tasks = []
    for index, module in enumerate(preset["modules"]):
        task_id = uuid4()
        tasks.append({
            "task_id": str(task_id), "task_key": "probe" if index == 0 else "compose",
            "module": module, "action": "run", "module_version": MODULE_VERSION,
            "depends_on": [tasks[-1]["task_id"]] if tasks else [],
            "config": compose_config if module == "render.basic" else {},
            "input_refs": [str(v) for v in request.input_refs], "output_refs": [],
            "status": "queued", "attempt": 0,
        })
    value = {"schema_version": VERSION, "project_id": str(request.project_id), "job_id": str(job_id),
             "created_at": created_at.isoformat(), "pipeline": tasks,
             "input_refs": [str(v) for v in request.input_refs], "output_refs": []}
    return validate_manifest(value).model_dump(mode="json")


def module_dtos():
    return [{"id": k, "version": MODULE_VERSION, "actions": ["run"], "resource": v["resource"],
             "config_schema": v["config_schema"], "available": v["available"],
             "unavailable_reason": None if v["available"] else "ADAPTER_NOT_INTEGRATED"}
            for k, v in MODULES.items()]


def preset_dtos():
    return [{"id": k, "version": MODULE_VERSION, "label": v["label"], "available": v["available"],
             "modules": v["modules"],
             "default_config": PRESET_DEFAULTS.get(k, {}),
             "override_schema": (BASIC_CONFIG if "render.basic" in v["modules"] else EMPTY_CONFIG) if v["available"] else CreateJob.model_json_schema()["$defs"]["Overrides"]}
            for k, v in PRESETS.items()]
