"""Strict dubbing failures must never silently return original dialogue."""
import ast
from pathlib import Path

import pytest
import dialogue_replace


def test_required_separation_failure_stops_before_mix(monkeypatch, tmp_path):
    def fail(**kwargs):
        raise RuntimeError('separator unavailable')
    monkeypatch.setattr(dialogue_replace, 'prepare_dialogue_replacement', fail)
    monkeypatch.setattr(dialogue_replace, 'final_mix_hard_replace',
                        lambda **kwargs: pytest.fail('must not mix after separator failure'))
    with pytest.raises(RuntimeError, match='hard_replace=True'):
        dialogue_replace.apply_final_audio('source.mp4', 'rendered.mp4', 'voice.wav',
            tmp_path / 'out.mp4', {'dialogue_replace': {'enabled': True, 'hard_replace': True}})
    assert not (tmp_path / 'out.mp4').exists()


def test_missing_voice_rejected_before_original_audio_fallback(tmp_path):
    # Execute the exact production guard without loading video/GPU dependencies.
    path = Path(__file__).resolve().parents[1] / 'video_merger.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == 'process_video_sub_and_mute')
    index = next(i for i, n in enumerate(fn.body) if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == 'strict_dialogue' for t in n.targets))
    guard = ast.Module(body=fn.body[index:index+2], type_ignores=[])
    scope = {'channel_cfg': {'dialogue_replace': {'enabled': True, 'required': True}},
             'has_voice': False}
    with pytest.raises(RuntimeError, match='DUBBED_AUDIO_REQUIRED'):
        exec(compile(guard, str(path), 'exec'), scope)
