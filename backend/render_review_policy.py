"""Stable readable names and source-bound per-channel review deliveries."""
import re
import unicodedata


def review_filename(title: str, source_id: str | None = None) -> str:
    if source_id is not None and not re.fullmatch(r'[0-9]{10,24}', str(source_id)):
        raise ValueError('INVALID_SOURCE_ID')
    title = unicodedata.normalize('NFKD', str(title).replace('đ', 'd').replace('Đ', 'D'))
    title = title.encode('ascii', 'ignore').decode().lower()
    slug = re.sub(r'[^a-z0-9]+', '_', title).strip('_')[:90].rstrip('_')
    if not slug or re.fullmatch(r'(?:video|douyin|audio|test)(?:_\d+)?',slug):
        raise ValueError('CONTENT_TITLE_REQUIRED')
    return f'{slug}__{source_id}.mp4' if source_id is not None else f'{slug}.mp4'


def require_channel_destination(channel: str, directory, channel_roots) -> None:
    from pathlib import Path
    expected = Path(channel_roots[channel]).resolve() / '02_MOI_RENDER_CHO_XAC_NHAN'
    if Path(directory).resolve() != expected:
        raise ValueError('CHANNEL_OUTPUT_BINDING_MISMATCH')


def validate_voice_assignments(assignments, actual):
    """A matcher report must agree with the voices that were actually rendered."""
    if len(assignments) != len(actual):
        raise ValueError('RENDERED_VOICE_CUE_COUNT_MISMATCH')
    for expected, rendered in zip(assignments, actual):
        if expected.get('profile') != rendered.get('profile'):
            raise ValueError('RENDERED_VOICE_PROFILE_MISMATCH')
        if abs(float(expected['start'])-float(rendered['start'])) > .75:
            raise ValueError('RENDERED_VOICE_TIMING_MISMATCH')


def bound_caption_regions(cache, source, detection, width, height, duration):
    import hashlib
    from pathlib import Path
    checksum=hashlib.sha256()
    with Path(source).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            checksum.update(block)
    if (not isinstance(cache,dict) or cache.get('input_sha256') != checksum.hexdigest()
            or cache.get('subtitle_detection') != detection
            or not isinstance(cache.get('regions'),list)):
        raise ValueError('CAPTION_CACHE_SOURCE_OR_CONFIG_MISMATCH')
    for region in cache['regions']:
        box=region.get('box')
        if not 0 <= float(region['start']) < float(region['end']) <= duration+.1:
            raise ValueError('CAPTION_CACHE_INVALID_TIME')
        if box and (region.get('status') != 'verified'
                    or not 0 <= box['x'] < box['x']+box['w'] <= width
                    or not 0 <= box['y'] < box['y']+box['h'] <= height):
            raise ValueError('CAPTION_CACHE_INVALID_GEOMETRY')
    return cache['regions']
