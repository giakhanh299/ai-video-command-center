"""Keep manual and scheduled fishing renders on the restored voiced preset."""
import channel_manager


def test_config4_restored_for_both_entrypoints():
    channel_manager.load_channels_config(force_reload=True)
    _, scheduled = channel_manager.get_channel_config('KENH_008_ChiDepDiCau')
    manual = channel_manager.apply_job_preset(scheduled, 'cauhinh4')
    for cfg in (manual, scheduled):
        assert cfg['tts_enabled'] is True
        assert cfg['voice'] == 'omni_nu_cute'
        assert cfg['speed'] == 1.4
        assert cfg['_voice_profile']['synthesis_speed'] == 0.9
        assert cfg['_voice_profile']['playback_speed'] == 1.4
        assert cfg['_voice_profile']['duration_match']['adaptive'] is False
        assert cfg['burn_sub'] is True
        assert cfg['bg_volume'] == 0.5
        assert cfg['mute_original_speech'] is True
        assert cfg['dialogue_replace']['enabled'] is True
        assert cfg['dialogue_replace']['hard_replace'] is True
        assert cfg['dialogue_replace']['required'] is True
        assert cfg['dialogue_replace']['mute_original_speech'] is True
        assert cfg['dialogue_replace']['instrumental_volume'] == 0.5
        assert cfg['voice_accuracy']['min_accuracy'] == 0.95
        assert cfg['voice_accuracy']['enabled'] is True
        assert cfg['_voice_profile']['engine'] == 'omnivoice'
        assert cfg['_voice_profile']['require_clone'] is True
        assert cfg['_voice_profile']['fallback_voice'] is None
        assert cfg['render']['blur_bg_alpha'] == 0.0
        assert cfg['render']['blur_strength'] == 20
        assert cfg['render']['subtitle']['style_mode'] == 'karaoke'
        assert cfg['drive_folder'] == 'KENH_008_ChiDepDiCau/02_MOI_RENDER_CHO_XAC_NHAN'
