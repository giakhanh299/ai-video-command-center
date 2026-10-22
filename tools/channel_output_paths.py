"""Resolve the same per-channel review folder used by the renderer."""
import os
from pathlib import Path
from dotenv import dotenv_values

def channel_review_path(base_dir, channel_key, channel_config, legacy_output):
    if not channel_key.startswith('KENH_'):
        return legacy_output
    root=os.getenv('GOOGLE_DRIVE_DIR') or dotenv_values(Path(base_dir)/'backend'/'.env').get('GOOGLE_DRIVE_DIR')
    folder=channel_config.get('drive_folder')
    if not root or not folder:
        raise ValueError('Missing render output configuration for '+channel_key)
    root=Path(root).resolve();destination=(root/folder).resolve()
    if not destination.is_relative_to(root) or destination.parent.name!=channel_key or destination.name!='02_MOI_RENDER_CHO_XAC_NHAN':
        raise ValueError('Invalid per-channel review folder: '+channel_key)
    return destination.as_posix()
