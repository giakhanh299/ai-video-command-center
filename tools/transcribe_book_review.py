"""Recheck the recovered book video's transcript in short Chinese audio chunks."""
import gc
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'backend'), str(ROOT/'tools')]
from render_book_chuyen_hai_dua import PROJECT, WORK, IDENTITY, stage
from render_douyin_intake import FB, atomic, digest, probe
from autopilot.locks import CrossProcessFileLock


def main():
    from faster_whisper import WhisperModel
    from backend.sub_processor import SubtitleSegment, write_srt, OpenAISubtitleTranslator
    source = PROJECT/f'01_CHUA_RENDER/douyin_{IDENTITY}.mp4'
    binding = json.loads(source.with_suffix('.recovery.json').read_text(encoding='utf-8'))
    source_sha = digest(source)
    if binding['source_id'] != IDENTITY or binding['source_sha256'] != source_sha:
        raise ValueError('SOURCE_BINDING_CHANGED')
    if (WORK/'translation.corrected.json').exists():
        raise ValueError('CORRECTED_TRANSLATION_ALREADY_EXISTS')
    model = WhisperModel('large-v3', device='cuda', compute_type='float16',
                         cpu_threads=4, local_files_only=True)
    duration = probe(source)
    rows = []
    for index, offset in enumerate(range(0, int(duration)+1, 30)):
        stage('SOURCE_ASR_CHUNK', f'{index+1}/6')
        wave = WORK/f'source_chunk_{index:02}.wav'
        subprocess.run([str(ROOT/'tools/bin/ffmpeg.exe'), '-y', '-v', 'error',
            '-ss', str(offset), '-i', str(source), '-t', str(min(30, duration-offset)),
            '-vn', '-ar', '16000', '-ac', '1', str(wave)], check=True)
        segments, info = model.transcribe(str(wave), language='zh', beam_size=5,
            temperature=0.0, condition_on_previous_text=False, word_timestamps=True,
            vad_filter=True, vad_parameters={'min_silence_duration_ms': 300})
        for segment in segments:
            text = segment.text.strip()
            if text and segment.end > segment.start:
                rows.append({'start': round(segment.start+offset, 3),
                    'end': round(min(segment.end+offset, duration), 3), 'text': text,
                    'chunk': index, 'no_speech_prob': segment.no_speech_prob})
        atomic(WORK/'source.asr.chunks.json', {'source_sha256': source_sha,
            'asr_model': 'large-v3', 'language': 'zh', 'chunk_seconds': 30,
            'completed_chunks': index+1, 'segments': rows})
    del model
    gc.collect()
    import torch
    torch.cuda.empty_cache()
    if not rows or any(re.search('明镜|明鏡|订阅|訂閱', r['text']) for r in rows if r['start'] < 30):
        raise ValueError('INTRO_TRANSCRIPT_REQUIRES_MANUAL_REVIEW')
    originals = [SubtitleSegment(r['start'], r['end'], r['text']) for r in rows]
    original_path = WORK/'source.corrected.orig.srt'
    write_srt(originals, str(original_path))
    stage('TRANSLATE_CORRECTED_SOURCE', len(originals))
    # Preserve one spoken source cue per Vietnamese cue; do not borrow old text.
    translated = OpenAISubtitleTranslator().translate_segments(originals,
        batch_size=25, checkpoint_path=str(WORK/'source.corrected.srt'),
        progress_callback=stage)
    if len(translated) != len(originals) or any(
            not s.text.strip() or re.search(r'[\u3400-\u9fff]', s.text) for s in translated):
        raise ValueError('INCOMPLETE_VIETNAMESE_TRANSLATION')
    translated_path = WORK/'source.corrected.srt'
    write_srt(translated, str(translated_path))
    if digest(source) != source_sha:
        raise ValueError('SOURCE_CHANGED_DURING_ASR')
    atomic(WORK/'translation.corrected.json', {'source_id': IDENTITY,
        'source_sha256': source_sha, 'original_srt': str(original_path),
        'original_srt_sha256': digest(original_path), 'translated_srt': str(translated_path),
        'translated_srt_sha256': digest(translated_path), 'cue_count': len(translated),
        'reason': 'Old intro ASR contradicted by recovered source interval 14-30 seconds',
        'asr_model': 'large-v3', 'chunk_seconds': 30, 'language': 'zh',
        'full_human_listening': False, 'publish_permission': 'NONE'})
    stage('CORRECTED_TRANSLATION_READY', len(translated))


if __name__ == '__main__':
    os.environ['HF_HUB_OFFLINE'] = '1'
    try:
        with CrossProcessFileLock(FB/'runtime/locks/gpu_renderer.lock', timeout_seconds=0):
            main()
    except Exception as error:
        stage('TRANSCRIPT_REPAIR_FAILED', type(error).__name__)
        raise SystemExit('TRANSCRIPT_REPAIR_STOPPED_'+type(error).__name__)
