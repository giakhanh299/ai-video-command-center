import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from render_review_policy import review_filename, require_channel_destination, validate_voice_assignments


def test_vietnamese_name_keeps_source_binding():
    assert review_filename('Về Nhà Ăn Ngon Sau Giờ Làm', '7696450506177634929') == 've_nha_an_ngon_sau_gio_lam__7696450506177634929.mp4'
    assert review_filename('../Đường: về nhà?', '7696450506177634929').startswith('duong_ve_nha__')
    with pytest.raises(ValueError):
        review_filename('Tên', '../escape')
    for title in ('','视频','douyin','video_12345'):
        with pytest.raises(ValueError,match='TITLE_REQUIRED'):
            review_filename(title,'7696450506177634929')
    assert review_filename('Chuyến xe buýt') == 'chuyen_xe_buyt.mp4'


def test_config_cannot_deliver_one_channel_to_another(tmp_path):
    roots={'KENH_006':tmp_path/'KENH_006_TieuWuby','KENH_007':tmp_path/'KENH_007_Song1MinhCoGiVui'}
    require_channel_destination('KENH_007', roots['KENH_007']/'02_MOI_RENDER_CHO_XAC_NHAN', roots)
    with pytest.raises(ValueError,match='BINDING_MISMATCH'):
        require_channel_destination('KENH_007', roots['KENH_006']/'02_MOI_RENDER_CHO_XAC_NHAN', roots)


def test_wuby_button_preserves_k7_identity_and_explicit_brand_route():
    import channel_manager as manager
    _, cfg = manager.get_channel_config('KENH_007_Song1MinhCoGiVui')
    resolved = manager.apply_job_preset(cfg, 'wuby')
    assert resolved['drive_folder'].startswith('KENH_007_')
    assert resolved['_logo_type'] == 'kenh_007_song1minhcogivui'
    _, default = manager.get_channel_config('default')
    selected = manager.apply_job_preset(default, 'wuby', 'kenh_007_song1minhcogivui')
    assert selected['drive_folder'].startswith('KENH_007_')
    assert selected['subtitle_detection'] == {}


def test_k8_keeps_subtitles_and_precise_mask_after_button_selection():
    import channel_manager as manager
    _, cfg = manager.get_channel_config('default')
    selected = manager.apply_job_preset(cfg, 'cauhinh4')
    assert selected['workflow'] == 'gaidep_cauca'
    assert selected['burn_sub'] is True
    assert selected['subtitle_detection']['allow_estimated_mask'] is False
    assert selected['render']['blur_bg_alpha'] == 1.0


def test_love_preset_is_separate_and_has_emotional_clone_bank():
    import channel_manager as manager
    _, cfg = manager.get_channel_config('default')
    selected = manager.apply_job_preset(cfg, 'chuyen_hai_dua')
    assert selected['drive_folder'].startswith('THU_NGHIEM_ChuyenHaiDua/')
    assert selected['logo']['text'] == 'Chuyện Hai Đứa'
    assert {x['profile'] for x in selected['wuby_preflight']['voice_match']['voice_bank']} == {
        'omni_nam_cuon_hut','omni_nu_cam_xuc','omni_nu_diu_dang'}


def test_stale_male_audio_cannot_pass_a_new_female_voice_plan():
    expected=[{'start':0.,'profile':'omni_nu_cam_xuc'}]
    validate_voice_assignments(expected,[{'start':0.,'profile':'omni_nu_cam_xuc'}])
    with pytest.raises(ValueError,match='PROFILE_MISMATCH'):
        validate_voice_assignments(expected,[{'start':0.,'profile':'omni_laivansam'}])


def test_clone_settings_and_reference_changes_invalidate_voice_cache(tmp_path):
    from sub_processor import multivoice_cache_identity
    ref=tmp_path/'voice.wav';ref.write_bytes(b'first sample')
    profile={'engine':'omnivoice','ref_audio':str(ref),'ref_text':'Actual reference speech','num_step':24}
    first=multivoice_cache_identity('Câu cần đọc','omni_nu_cam_xuc',profile,1.)
    profile['num_step']=28
    assert multivoice_cache_identity('Câu cần đọc','omni_nu_cam_xuc',profile,1.) != first
    profile['num_step']=24;profile['ref_text']='Different reference transcript'
    assert multivoice_cache_identity('Câu cần đọc','omni_nu_cam_xuc',profile,1.) != first
    profile['ref_text']='Actual reference speech';ref.write_bytes(b'new sample')
    assert multivoice_cache_identity('Câu cần đọc','omni_nu_cam_xuc',profile,1.) != first


def test_caption_geometry_cache_cannot_cross_sources_or_configuration(tmp_path):
    import hashlib
    from render_review_policy import bound_caption_regions
    video=tmp_path/'video.mp4';video.write_bytes(b'source one')
    cfg={'mode':'lower_third_precise'}
    regions=[{'start':0.,'end':2.,'status':'verified','box':{'x':10,'y':60,'w':40,'h':20}}]
    cache={'input_sha256':hashlib.sha256(video.read_bytes()).hexdigest(),'subtitle_detection':cfg,'regions':regions}
    assert bound_caption_regions(cache,video,cfg,100,100,2.) == regions
    with pytest.raises(ValueError,match='CONFIG_MISMATCH'):
        bound_caption_regions(cache,video,{'mode':'other'},100,100,2.)
    video.write_bytes(b'different source')
    with pytest.raises(ValueError,match='SOURCE_OR_CONFIG_MISMATCH'):
        bound_caption_regions(cache,video,cfg,100,100,2.)
