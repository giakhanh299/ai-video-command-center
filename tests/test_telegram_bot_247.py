import os
import re
import json
import time
from pathlib import Path
from dotenv import load_dotenv

def test_re_import():
    title = 'SĂN CÁ KHỦNG CÙNG CHỊ ĐẸP'
    assert not re.search(r'[\u4e00-\u9fff]', title)
    chinese_title = '测试标题'
    assert re.search(r'[\u4e00-\u9fff]', chinese_title)

def test_command_parsing():
    def parse_cmd(text):
        parts = text.strip().split()
        raw = parts[0] if parts else ''
        return raw.lower().split('@')[0] if raw.startswith('/') else ''

    assert parse_cmd('/ping') == '/ping'
    assert parse_cmd('/ping@Aios2_bot') == '/ping'
    assert parse_cmd('/STATUS@aios2_bot') == '/status'
    assert parse_cmd('/kenh') == '/kenh'
    assert parse_cmd('/set_voice nam_minh') == '/set_voice'
    assert parse_cmd('https://v.douyin.com/xyz/') == ''

def test_allowed_chats():
    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / 'backend/.env')
    allowed = {x.strip() for x in os.getenv('TELEGRAM_GROUP_ID', '').split(',') if x.strip()}
    assert '-5273638075' in allowed
    assert '-1004439918026' in allowed

def test_heartbeat_files():
    root = Path(__file__).resolve().parent.parent
    hb_file = root / 'logs/bot_heartbeat.json'
    assert hb_file.exists()
    data = json.loads(hb_file.read_text(encoding='utf-8'))
    assert data.get('status') == 'polling'
    assert data.get('pid') > 0
    # Heartbeat must be fresh (< 60s)
    assert time.time() - data.get('timestamp') < 60
