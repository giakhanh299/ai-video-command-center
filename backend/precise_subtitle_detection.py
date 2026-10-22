"""Timed subtitle masks from repeated OCR observations near the lower third.

Coordinates always refer to the source frame. Padding is applied exactly once,
in units of the detected glyph height, never in units of translated text.
"""
import math
import re
from statistics import median
from difflib import SequenceMatcher
from collections import OrderedDict
from pathlib import Path

import cv2


def similar_text(a, b):
    # A minor OCR spelling change is not evidence that a watermark is dialogue.
    return SequenceMatcher(None, a, b, autojunk=False).ratio() >= .8


def lower_third_lines(detections, width, height, roi_top, min_center_ratio=2/3):
    """Filter crop-local OCR hits and merge adjacent words on the same line."""
    hits = []
    for points, text, confidence in detections:
        clean = ''.join(c for c in str(text) if c.isalnum()).lower()
        if float(confidence) < .45 or len(clean) < 2 or clean.isdigit():
            continue
        if not re.search(r'[a-zA-Z\u4e00-\u9fff\uac00-\ud7a3]', clean):
            continue
        xs, ys = zip(*points)
        x, right = max(0., min(xs)), min(float(width), max(xs))
        y, bottom = min(ys) + roi_top, min(float(height), max(ys) + roi_top)
        w, h = right - x, bottom - y
        # A box touching the crop top may be a clipped line; never accept half a subtitle.
        if y < roi_top + 2 or not max(8, height * .008) <= h <= height * .16:
            continue
        if (y + bottom) / 2 < height * min_center_ratio:
            continue
        if w < h * 1.2 or abs((x + right) / 2 - width / 2) > width * .40:
            continue
        hits.append(dict(x=x, y=y, right=right, bottom=bottom, text=clean,
                         confidence=float(confidence)))
    lines = []
    for hit in sorted(hits, key=lambda b: (b['y'], b['x'])):
        hh = hit['bottom'] - hit['y']
        for line in lines:
            lh = line['bottom'] - line['y']
            cy_gap = abs((hit['y'] + hit['bottom'] - line['y'] - line['bottom']) / 2)
            gap = max(hit['x'] - line['right'], line['x'] - hit['right'], 0)
            if cy_gap <= .35 * min(hh, lh) and max(hh, lh) <= 1.6 * min(hh, lh) and gap <= 1.5 * max(hh, lh):
                # Ignore duplicate OCR hits instead of manufacturing text variation.
                if hit['x'] >= line['x'] and hit['right'] <= line['right']:
                    break
                left, right = (line, hit) if line['x'] <= hit['x'] else (hit, line)
                line.update(text=left['text'] + right['text'], x=min(line['x'], hit['x']),
                            right=max(line['right'], hit['right']), y=min(line['y'], hit['y']),
                            bottom=max(line['bottom'], hit['bottom']),
                            confidence=min(line['confidence'], hit['confidence']))
                break
        else:
            lines.append(hit.copy())
    return lines


def consensus_box(observations, width, height):
    """Geometry consensus inside ONE short interval, after watermark filtering.

Two matching frames can verify a rare second line. Reject isolated large boxes;
if two competing widths are supported, request temporal subdivision instead.
"""
    clusters = []
    for frame_id, lines in observations:
        for line in lines:
            hit = dict(line, frame=frame_id)
            h = hit['bottom'] - hit['y']
            cy, cx = (hit['bottom'] + hit['y']) / 2, (hit['x'] + hit['right']) / 2
            matches = []
            for cluster in clusters:
                ch = median(b['bottom'] - b['y'] for b in cluster)
                ccy = median((b['bottom'] + b['y']) / 2 for b in cluster)
                ccx = median((b['x'] + b['right']) / 2 for b in cluster)
                if abs(cy - ccy) <= .4 * min(h, ch) and max(h, ch) <= 1.6 * min(h, ch) and abs(cx - ccx) <= max(2 * ch, width * .06):
                    matches.append((abs(cy - ccy), cluster))
            if matches:
                min(matches, key=lambda m: m[0])[1].append(hit)
            else:
                clusters.append([hit])

    def frames(cluster):
        return {b['frame'] for b in cluster}

    def score(cluster):
        return (len(frames(cluster)), len({b['text'] for b in cluster}),
                median(b['confidence'] for b in cluster))

    valid = []
    for cluster in clusters:
        if len(frames(cluster)) < 2:
            continue
        mw = median(b['right'] - b['x'] for b in cluster)
        mh = median(b['bottom'] - b['y'] for b in cluster)
        mad = median(abs(b['right'] - b['x'] - mw) for b in cluster)
        tolerance = max(mw * .25, mh * 2, mad * 3)
        inliers = [b for b in cluster if abs(b['right'] - b['x'] - mw) <= tolerance
                   and any(c['frame'] != b['frame'] and abs((c['right']-c['x'])-(b['right']-b['x'])) <= max(mh*2, min(c['right']-c['x'], b['right']-b['x'])*.25)
                           for c in cluster)]
        # MAD alone would include a bimodal width distribution. Check the extremes
        # too; repeated narrow/wide groups belong to different timed masks.
        widths = sorted((b['right'] - b['x'], b['frame']) for b in cluster)
        narrow = {f for w, f in widths if w <= widths[0][0] * 1.2}
        wide = {f for w, f in widths if w >= widths[-1][0] / 1.2}
        if widths[-1][0] > widths[0][0] * 1.6 and len(narrow) >= 2 and len(wide) >= 2:
            return None
        if len(frames(inliers)) >= 2:
            valid.append(inliers)
    if not valid:
        return None
    main = max(valid, key=score)
    selected = list(main)
    mh = median(b['bottom'] - b['y'] for b in main)
    my = median((b['y'] + b['bottom']) / 2 for b in main)
    mx = median((b['x'] + b['right']) / 2 for b in main)
    # Distinct strong baselines far apart require timed masks, not a guessed fixed one.
    for other in valid:
        oy = median((b['y'] + b['bottom']) / 2 for b in other)
        ox = median((b['x'] + b['right']) / 2 for b in other)
        if other is not main and (abs(oy - my) > 2 * mh or abs(ox - mx) > 2 * mh):
            return None
    for other in sorted(valid, key=score, reverse=True):
        if other is main or len(frames(main) & frames(other)) < 2:
            continue
        oh = median(b['bottom'] - b['y'] for b in other)
        oy = median((b['y'] + b['bottom']) / 2 for b in other)
        ox = median((b['x'] + b['right']) / 2 for b in other)
        if max(mh, oh) <= 1.5 * min(mh, oh) and .8 * min(mh, oh) <= abs(oy - my) <= 1.65 * max(mh, oh) and abs(ox - mx) <= 1.5 * max(mh, oh):
            selected.extend(other)
            break
    # Tight padding for glyph outlines, added once. Never shrink a genuine wide line.
    px, py = max(3, min(12, math.ceil(mh * .18))), max(2, min(6, math.ceil(mh * .10)))
    x = max(0, math.floor((min(b['x'] for b in selected) - px) / 2) * 2)
    y = max(0, math.floor((min(b['y'] for b in selected) - py) / 2) * 2)
    right = min(width // 2 * 2, math.ceil((max(b['right'] for b in selected) + px) / 2) * 2)
    bottom = min(height // 2 * 2, math.ceil((max(b['bottom'] for b in selected) + py) / 2) * 2)
    if bottom - y > height * .22:
        return None
    return dict(x=x, y=y, w=right-x, h=bottom-y, center_y=(y+bottom)/2)


def classify_tracks(samples, events):
    """Track fuzzy OCR text; distinguish temporal dialogue from persistent text.

Static text is accepted when bounded by a spoken cue with observed quiet frames
around it, or when other dialogue establishes the same baseline. Unresolved
static text is left unmasked, not treated as an OCR failure for the whole video.
"""
    tracks, active = [], []
    quiet_times = []
    cues = sorted((float(s), float(e)) for s, e, _ in events if e > s)
    for sample in samples:
        ts = sample['time']
        spoken = {i for i, (s, e) in enumerate(cues) if s <= ts < e}
        quiet = not any(s - .3 <= ts < e + .3 for s, e in cues)
        if cues and quiet:
            quiet_times.append(ts)
        active = [t for t in active if ts - t['last'] <= 1.0]
        for line in sample['lines']:
            cy = (line['y'] + line['bottom']) / 2
            cx = (line['x'] + line['right']) / 2
            h = line['bottom'] - line['y']
            found = next((t for t in active if abs(t['cy'] - cy) <= .5 * h
                          and abs(t['cx'] - cx) <= 2 * h and similar_text(t['text'], line['text'])), None)
            if found is None:
                found = dict(id=len(tracks), text=line['text'], first=ts, last=ts,
                             cy=cy, cx=cx, h=h, frames=set(), cues=set(), quiet=set())
                tracks.append(found)
                active.append(found)
            found['last'] = ts
            found['frames'].add(sample['frame'])
            found['cues'].update(spoken)
            if cues and quiet:
                found['quiet'].add(int(ts * 2))
            line['track'] = found['id']
    for track in tracks:
        # Repeated presence well outside speech, or the same text across many
        # different cues, is evidence of persistent overlay text.
        track['watermark'] = (len(track['quiet']) >= 2 and bool(track['cues'])) or (
            len(track['cues']) >= 4 and track['last'] - track['first'] >= 12)
        track['trusted'] = False
    eligible = [t for t in tracks if not t['watermark'] and len(t['frames']) >= 2]
    for track in eligible:
        changing_baseline = any(
            other is not track and abs(other['cy'] - track['cy']) <= .5 * track['h']
            and abs(other['cx'] - track['cx']) <= 2 * track['h']
            and not similar_text(other['text'], track['text']) for other in eligible)
        bounded_cue = any(
            abs(track['first'] - cues[i][0]) <= .6 and abs(track['last'] - cues[i][1]) <= .6
            and any(cues[i][0] - 1.5 <= t < cues[i][0] for t in quiet_times)
            and any(cues[i][1] < t <= cues[i][1] + 1.5 for t in quiet_times)
            for i in track['cues'])
        track['trusted'] = changing_baseline or bounded_cue
    primary = [t for t in eligible if t['trusted']]
    for track in eligible:
        # A short-lived second row can be verified by simultaneous dialogue on
        # the adjacent baseline; it need not recur in three different sentences.
        if not track['trusted']:
            track['trusted'] = any(
                len(track['frames'] & main['frames']) >= 2
                and .8*min(track['h'], main['h']) <= abs(track['cy']-main['cy']) <= 1.65*max(track['h'], main['h'])
                and max(track['h'], main['h']) <= 1.5*min(track['h'], main['h'])
                and abs(track['cx']-main['cx']) <= 1.5*max(track['h'], main['h'])
                for main in primary)
    return tracks


def coalesce_regions(regions):
    """Only identical adjacent masks merge; never union different widths."""
    result = []
    for region in regions:
        if result and result[-1]['box'] == region['box'] and result[-1]['status'] == region['status'] and abs(result[-1]['end'] - region['start']) < 1e-6:
            result[-1]['end'] = region['end']
        else:
            result.append(dict(region))
    return result


def scan_precise_caption_regions(video_path, events, *, ocr_backend='easyocr', min_center_ratio=2/3):
    """Scan every half second, refine uncertain intervals to 1/8 second.

No global 96-frame limit. Three probes per interval plus neighbouring probes on
uncertainty verify rare lines locally. Empty/ambiguous regions never inherit a
stale mask. OCR/model errors still propagate; ambiguous content is reported.
"""
    reader = None
    try:
        if ocr_backend == 'rapidocr':
            from rapid_ocr_service import get_rapid_ocr
            engine = get_rapid_ocr()
            class Reader:
                def readtext(self, image, **kwargs):
                    result, _ = engine(image)
                    return result or []
            reader = Reader()
        elif ocr_backend == 'easyocr':
            from wuby_ocr_overlay import get_ocr_reader
            reader = get_ocr_reader()
        else:
            raise ValueError('UNKNOWN_CAPTION_OCR_BACKEND')
    except Exception as e:
        print(f"[PreciseSubtitleOCR] Canh bao khong the khoi tao EasyOCR: {e}. Renderer se thu bo do vi tri du phong.")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f'Cannot open subtitle source: {video_path}')
    try:
        width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps
        if width < 2 or height < 2 or frame_count < 1:
            raise RuntimeError('Invalid source dimensions/duration for subtitle OCR')

        if reader is None:
            # The renderer supplies detected/estimated cue-sized backdrops.
            return [dict(start=0., end=duration, box=None, status='ocr_unavailable')]
        # Small overlap recovers full glyphs crossing the lower-third boundary.
        # Candidate centers must still be in the lower third.
        if not .5 <= float(min_center_ratio) <= .9:
            raise ValueError('INVALID_CAPTION_CENTER_RATIO')
        roi_top = max(0, math.floor(height * (float(min_center_ratio) - .06)))
        cache = OrderedDict()
        def read_at(ts):
            frame_id = max(0, min(frame_count - 1, int(ts * fps)))
            if frame_id in cache:
                return cache[frame_id]
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError(f'Subtitle OCR could not read source frame {frame_id}')
            crop = frame[roi_top:height, :]
            detections = reader.readtext(crop, paragraph=False, mag_ratio=1.5,
                                         canvas_size=max(2560, min(4096, width)))
            sample = dict(frame=frame_id, time=frame_id/fps,
                          lines=lower_third_lines(detections, width, height, roi_top, min_center_ratio))
            cache[frame_id] = sample
            if len(cache) > 512:
                cache.popitem(last=False)
            return sample

        windows, samples = [], {}
        for i in range(math.ceil(duration * 2)):
            if i % 60 == 0:
                print(f'[PreciseSubtitleOCR] sampling {i/2:.1f}/{duration:.1f}s ({ocr_backend})', flush=True)
            a, b = i / 2, min(duration, (i + 1) / 2)
            probes = [read_at(a + (b-a)*f) for f in (.2, .5, .8)]
            for probe in list(probes):
                for line in probe['lines']:
                    h = line['bottom']-line['y']
                    supported = any(p['frame'] != probe['frame'] and any(
                        similar_text(line['text'], other['text'])
                        and abs(line['y']-other['y']) <= .4*h
                        and abs((line['right']-line['x'])-(other['right']-other['x'])) <= 2*h
                        for other in p['lines']) for p in probes)
                    if not supported:
                        probes.extend(read_at(max(a, min(b-1/fps, probe['time']+delta/fps))) for delta in (-1, 1))
                        break
            probes = list({p['frame']: p for p in probes}.values())
            windows.append((a, b, probes))
            samples.update((p['frame'], p) for p in probes)
        tracks = classify_tracks(sorted(samples.values(), key=lambda p: p['time']), events)

        def trusted(line, ts):
            # Refinement probes were not in the first pass. Match only a trusted
            # text track near its actual time span; geometry alone is insufficient.
            h = line['bottom'] - line['y']
            cy, cx = (line['y'] + line['bottom'])/2, (line['x'] + line['right'])/2
            return any(t['trusted'] and t['first']-.5 <= ts <= t['last']+.5
                       and abs(t['cy']-cy) <= .5*h and abs(t['cx']-cx) <= 2*h
                       and similar_text(t['text'], line['text']) for t in tracks)

        def resolve(a, b, probes, depth=0):
            observations = [(p['frame'], [line for line in p['lines'] if trusted(line, p['time'])]) for p in probes]
            observations = list({frame: (frame, lines) for frame, lines in observations}.values())
            box = consensus_box(observations, width, height)
            # Any intermittent or uncovered trusted line triggers local resampling.
            missing = any(not lines for _, lines in observations) and any(lines for _, lines in observations)
            uncovered = any(box is None or line['x'] < box['x'] or line['right'] > box['x']+box['w']
                            or line['y'] < box['y'] or line['bottom'] > box['y']+box['h']
                            for _, lines in observations for line in lines)
            has_hits = any(lines for _, lines in observations)
            if depth < 2 and (missing or uncovered or (box is None and has_hits)):
                mid = (a+b)/2
                return [r for lo, hi in ((a, mid), (mid, b))
                        for r in resolve(lo, hi, [read_at(lo+(hi-lo)*f) for f in (.2,.5,.8)], depth+1)]
            if missing:
                box = None  # Do not smear a sampled absence across the interval.
            status = 'verified' if box else ('uncertain' if any(p['lines'] for p in probes) else 'empty')
            return [dict(start=a, end=b, box=box, status=status)]

        regions = coalesce_regions([r for a, b, probes in windows for r in resolve(a, b, probes)])
    finally:
        cap.release()
    unresolved = sum(r['end']-r['start'] for r in regions if r['status'] == 'uncertain')
    print(f'[PreciseSubtitleOCR] {len(regions)} timed regions; {unresolved:.2f}s ambiguous (renderer will apply cue backdrop fallback; see subtitle_regions.json)')
    return regions


def ensure_blur_coverage(regions, events, width, height, fallback_box=None, font_size=45):
    """Keep verified masks; give spoken cues a backdrop when OCR returned no box.

An estimated backdrop is explicitly labelled: it is not proof of source-text
location. Split at both OCR and cue boundaries, so gaps stay unmasked.
"""
    cues = [(float(s), float(e), str(t or '')) for s, e, t in events if float(e) > float(s)]
    cuts = sorted({float(r[k]) for r in regions for k in ('start', 'end')} |
                  {v for s, e, _ in cues for v in (s, e)})
    result = []
    for start, end in zip(cuts, cuts[1:]):
        region = next((r for r in regions if r['start'] < end and r['end'] > start), None)
        cue = next((c for c in cues if c[0] < end and c[1] > start), None)
        if region and region.get('box'):
            result.append(dict(region, start=start, end=end))
            continue
        if not cue:
            result.append(dict(start=start, end=end, box=None, status=(region or {}).get('status', 'empty')))
            continue
        if fallback_box:
            box = dict(fallback_box)
            status = 'fallback_detected'
        else:
            text = cue[2].replace('\\N', ' ').replace('\n', ' ')
            words = text.split()
            lines = [text]
            if len(text) > 24 and len(words) > 1:
                mid = min(range(1, len(words)), key=lambda i: abs(len(' '.join(words[:i]))-len(' '.join(words[i:]))))
                lines = [' '.join(words[:mid]), ' '.join(words[mid:])]
            bw = min(width, max(font_size * 4, math.ceil(max(map(len, lines), default=0) * font_size * .6 + 24)))
            bh = min(height, math.ceil(font_size * (1.35 * len(lines)) + 12))
            bw, bh = min(width//2*2, math.ceil(bw/2)*2), min(height//2*2, math.ceil(bh/2)*2)
            x = (width-bw)//2//2*2
            bottom = height - max(8, int(height*.035))
            y = max(0, bottom-bh)//2*2
            box = dict(x=x, y=y, w=bw, h=bh, center_y=y+bh/2)
            status = 'fallback_estimated'
        result.append(dict(start=start, end=end, box=box, status=status))
    return coalesce_regions(result)


def recover_source_caption_regions(video_path, regions, source_events, min_center_ratio=2/3):
    """Recover missing masks only from two actual OCR hits matching source speech.

Never inherit a neighbouring/global box. Missing intervals split at source cue
boundaries and half-second boundaries, so a recovered box cannot span a gap.
"""
    from rapid_ocr_service import get_rapid_ocr
    engine=get_rapid_ocr()
    clean=lambda text: ''.join(c for c in str(text) if c.isalnum()).lower()
    cues=[(float(s),float(e),clean(t)) for s,e,t in source_events if clean(t)]
    cap=cv2.VideoCapture(str(video_path))
    width,height=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps=cap.get(cv2.CAP_PROP_FPS) or 25.
    roi=max(0,int(height*(min_center_ratio-.06)))
    result=[]
    try:
        for region in regions:
            if region.get('box'):
                result.append(region);continue
            cuts=sorted({region['start'],region['end']} |
                {v for s,e,_ in cues for v in (s,e) if region['start']<v<region['end']})
            for lo,hi in zip(cuts,cuts[1:]):
                expected=[t for s,e,t in cues if s<hi and e>lo]
                steps=max(1,math.ceil((hi-lo)*2)) if expected else 1
                for i in range(steps):
                    a,b=lo+(hi-lo)*i/steps,lo+(hi-lo)*(i+1)/steps
                    observations=[]
                    for fraction in (.25,.75) if expected else ():
                        frame_id=int((a+(b-a)*fraction)*fps)
                        cap.set(cv2.CAP_PROP_POS_FRAMES,frame_id);ok,frame=cap.read()
                        if not ok:continue
                        hits,_=engine(frame[roi:height,:])
                        lines=lower_third_lines(hits or [],width,height,roi,min_center_ratio)
                        lines=[line for line in lines if any(
                            SequenceMatcher(None,line['text'],t,autojunk=False).ratio()>=.55 for t in expected)]
                        observations.append((frame_id,lines))
                    box=consensus_box(observations,width,height) if len({f for f,_ in observations})>=2 else None
                    result.append(dict(start=a,end=b,box=box,
                        status='verified' if box else region['status'],
                        verification_method='SOURCE_TRANSCRIPT_TWO_FRAME_OCR' if box else None))
    finally:
        cap.release()
    return coalesce_regions(result)


def timed_blur_filters(regions, width, height, label, mask_path, alpha=.35, sigma=16):
    """One blur + an animated alpha mask; filter count does not grow per cue."""
    from film_bars import escape_subtitle_path_windows
    def stamp(t):
        ticks = max(0, int(round(t * 100)))
        return f'{ticks//360000}:{ticks//6000%60:02}:{ticks//100%60:02}.{ticks%100:02}'
    header = f'''[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Mask,Arial,20,&H00FFFFFF,&H00FFFFFF,&H00FFFFFF,&H00FFFFFF,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    lines = []
    for r in regions:
        if not r['box']:
            continue
        box = r['box']
        x,y,w,h = (box[k] for k in ('x','y','w','h'))
        drawing = f'm {x} {y} l {x+w} {y} {x+w} {y+h} {x} {y+h}'
        lines.append(f"Dialogue: 0,{stamp(r['start'])},{stamp(r['end'])},Mask,,0,0,0,,{{\\an7\\pos(0,0)\\p1\\bord0\\shad0}}{drawing}")
    Path(mask_path).write_text(header+'\n'.join(lines)+'\n', encoding='utf-8')
    if not lines:
        return [], label
    path = escape_subtitle_path_windows(str(mask_path))
    alpha = min(1., max(0., float(alpha)))
    sigma = min(80., max(1., float(sigma)))
    if alpha >= .999:
        # Fully opaque masks must not depend on the ASS alpha plane: libass
        # antialiasing can leave partially transparent pixels and make the source
        # glyphs visible through a nominally black mask. Apply timed black boxes
        # directly to the video so every pixel inside the verified box is replaced
        # before Vietnamese subtitles are burned in later.
        filters = []
        current = label
        for idx, r in enumerate(regions):
            box = r.get('box')
            if not box:
                continue
            x = max(0, int(box['x']))
            y = max(0, int(box['y']))
            w = max(1, min(int(box['w']), int(width) - x))
            h = max(1, min(int(box['h']), int(height) - y))
            out = f'[precise_black_{idx}]'
            enable = f"between(t,{float(r['start']):.3f},{float(r['end']):.3f})"
            filters.append(
                f"{current}drawbox=x={x}:y={y}:w={w}:h={h}:color=black@1:t=fill:enable='{enable}'{out}"
            )
            current = out
        return filters, current

    soft = f'[precise_blur]gblur=sigma={sigma:g}:steps=2,drawbox=color=black@{alpha:.3f}:t=fill[precise_soft]'
    return [f'{label}split=3[precise_base][precise_blur][precise_mask]',
            soft,
            f"[precise_mask]format=gray,lut=y=0,subtitles='{path}',format=gray[precise_alpha]",
            '[precise_soft][precise_alpha]alphamerge[precise_layer]',
            '[precise_base][precise_layer]overlay=0:0:shortest=1[precise_out]'], '[precise_out]'
