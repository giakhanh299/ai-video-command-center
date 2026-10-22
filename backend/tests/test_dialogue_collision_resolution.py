from backend.wuby_ocr_overlay import resolve_dialogue_collisions


def test_brief_ocr_variant_cannot_cover_spoken_caption_in_same_box():
    speech = dict(start=11.97, end=12.93, box=[300, 1260, 420, 100],
                  vi_text='Hiểu bạn', source='whisper_dialogue')
    variant = dict(start=12.2, end=12.37, box=[302, 1262, 419, 98],
                   vi_text='Bạn đó', source='ocr_translation')
    assert resolve_dialogue_collisions([variant, speech]) == [speech]


def test_separate_simultaneous_food_labels_remain_visible():
    labels = [dict(start=49.6, end=51, box=[300, y, 420, 80],
                   vi_text=text, source='ocr_translation')
              for y, text in [(1050, 'Bún mì đỏ'), (1200, 'Bún mì trứng'), (1380, 'Trứng hấp sốt')]]
    assert len(resolve_dialogue_collisions(labels)) == 3


def test_partial_conflict_keeps_nonoverlapping_portions_without_mutating_input():
    speech = dict(start=2, end=3, box=[200, 1000, 400, 80],
                  vi_text='Lời thoại', source='whisper_dialogue')
    label = dict(start=1, end=4, box=[200, 1000, 400, 80],
                 vi_text='Chữ trên hình', source='ocr_translation')
    resolved = resolve_dialogue_collisions([label, speech])
    assert [(e['start'], e['end']) for e in resolved] == [(1, 2), (2, 3), (3, 4)]
    assert label['start'] == 1 and label['end'] == 4
