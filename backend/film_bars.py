import os
import re

def compute_film_black_bars(vid_w: int, vid_h: int, detected_box: dict = None, top_ratio: float | None = None, bottom_ratio: float | None = None, bottom_max_ratio: float = 0.35) -> dict:
    """
    Computes top and bottom black bar heights and dialog placement for film translation mode.
    Validated according to OC-009 requirements:
    - top and bottom ratios in [0.05, 0.35]
    - total ratio <= 0.50
    - if detector found bottom subtitle box, bottom bar expands to cover it fully (up to 0.35 max)
    - output dict: top_h, bottom_h, dialogue_fs, dialogue_mv
    """
    raw_top_ratio = os.getenv("FILM_TOP_BAR_RATIO", "0.10").strip() if top_ratio is None else str(top_ratio)
    raw_bot_ratio = os.getenv("FILM_BOTTOM_BAR_RATIO", "0.22").strip() if bottom_ratio is None else str(bottom_ratio)
    
    try:
        top_ratio = float(raw_top_ratio)
    except Exception as e:
        raise ValueError(f"INVALID_FILM_RATIO: FILM_TOP_BAR_RATIO '{raw_top_ratio}' is not a valid float: {e}")
        
    try:
        bot_ratio = float(raw_bot_ratio)
    except Exception as e:
        raise ValueError(f"INVALID_FILM_RATIO: FILM_BOTTOM_BAR_RATIO '{raw_bot_ratio}' is not a valid float: {e}")
        
    if not (0.05 <= top_ratio <= 0.35):
        raise ValueError(f"INVALID_FILM_RATIO: FILM_TOP_BAR_RATIO {top_ratio} must be between 0.05 and 0.35")
        
    bottom_max_ratio = float(bottom_max_ratio)
    if not (0.05 <= bottom_max_ratio <= 0.45):
        raise ValueError(f"INVALID_FILM_RATIO: bottom_max_ratio {bottom_max_ratio} must be between 0.05 and 0.45")

    if not (0.05 <= bot_ratio <= bottom_max_ratio):
        raise ValueError(f"INVALID_FILM_RATIO: FILM_BOTTOM_BAR_RATIO {bot_ratio} must be between 0.05 and {bottom_max_ratio}")
        
    if (top_ratio + bot_ratio) > 0.50:
        raise ValueError(f"INVALID_FILM_RATIO: Total bar ratio ({top_ratio} + {bot_ratio} = {top_ratio + bot_ratio:.2f}) exceeds maximum allowed 0.50")
        
    top_h = int(round(vid_h * top_ratio))
    top_h = (top_h // 2) * 2  # even pixels
    
    bot_h = int(round(vid_h * bot_ratio))
    bot_h = (bot_h // 2) * 2
    
    # If detector found old subtitle box at the bottom, expand bottom bar to cover it completely
    if detected_box and isinstance(detected_box, dict):
        by = detected_box.get("y", 0)
        bh = detected_box.get("h", 0)
        if by > 0 and bh > 0:
            # required bottom bar height to cover from 'by' down to bottom of frame (vid_h - by)
            needed_bot_h = vid_h - by + 6  # 6px padding
            max_allowed_bot_h = int(round(vid_h * bottom_max_ratio))
            if needed_bot_h > bot_h:
                bot_h = min(needed_bot_h, max_allowed_bot_h)
                bot_h = (bot_h // 2) * 2
                
    # Double check total height doesn't exceed 55%
    if (top_h + bot_h) > int(round(vid_h * 0.55)):
        bot_h = int(round(vid_h * 0.55)) - top_h
        bot_h = (bot_h // 2) * 2

    # Vietnamese dialogue subtitle styling inside bottom black bar:
    # Centered vertically inside bottom black bar:
    # Center of bottom bar is at Y = vid_h - bot_h / 2
    # MarginV from bottom = (bot_h - font_size) / 2
    dialogue_fs = max(28, min(64, int(round(bot_h * 0.36))))
    dialogue_mv = max(12, int(round((bot_h - dialogue_fs) / 2)))

    return {
        "top_h": top_h,
        "bottom_h": bot_h,
        "dialogue_fs": dialogue_fs,
        "dialogue_mv": dialogue_mv
    }

def escape_subtitle_path_windows(path_str: str) -> str:
    """Escapes Windows path safely for FFmpeg subtitles filter graph."""
    # Slashes to forward slashes, colon escaped as \:
    # Single quotes escaped as \'
    clean = str(path_str).replace("\\", "/")
    clean = clean.replace(":", "\\:")
    clean = clean.replace("'", "\\'")
    return clean
