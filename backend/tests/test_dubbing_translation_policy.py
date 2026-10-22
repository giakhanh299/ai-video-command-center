import sub_processor as sp


def test_duration_policy_retranslates_old_cache_and_preserves_source_timestamps(tmp_path, monkeypatch):
    source=tmp_path/'source.srt'
    target=tmp_path/'translated.srt'
    source.write_text('1\n00:00:01,000 --> 00:00:03,000\n叔叔您好\n\n2\n00:00:04,000 --> 00:00:06,000\n您好\n',encoding='utf-8')
    target.write_text('1\n00:00:01,000 --> 00:00:03,000\nBản dịch cũ quá dài\n',encoding='utf-8')
    calls=[]
    class Translator:
        def __init__(self, dubbing_speed=None):
            assert dubbing_speed == 1.4
        def translate_segments(self, segments, **kwargs):
            calls.append(kwargs['checkpoint_path'])
            return [sp.SubtitleSegment(s.start,s.end,'Chào chú ạ') for s in segments]
    monkeypatch.setattr(sp,'OpenAISubtitleTranslator',Translator)
    result=sp.translate_srt_to_vietnamese_srt(str(source),str(target),dubbing_speed=1.4)
    assert [(s.start,s.end,s.text) for s in result] == [(1,3,'Chào chú ạ'), (4,6,'Chào chú ạ')]
    assert (tmp_path/'translated.srt.before_timing_policy.srt').exists()
    sp.translate_srt_to_vietnamese_srt(str(source),str(target),dubbing_speed=1.4)
    assert len(calls)==1
    source.write_text(source.read_text(encoding='utf-8').replace('叔叔您好','你好'),encoding='utf-8')
    sp.translate_srt_to_vietnamese_srt(str(source),str(target),dubbing_speed=1.4)
    assert len(calls)==2 and calls[0] != calls[1]
