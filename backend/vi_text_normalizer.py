# -*- coding: utf-8 -*-
"""
Vietnamese Text Normalizer for TTS (Text-to-Speech)
Chuyển đổi số, ký hiệu, đơn vị đo lường, tỉ lệ thành chữ tiếng Việt chuẩn xác
để AI đọc tự nhiên, chuẩn ngữ điệu và không đọc nhầm tiếng Anh.
"""

from __future__ import annotations
import re
from typing import Any

UNITS = ['không', 'một', 'hai', 'ba', 'bốn', 'năm', 'sáu', 'bảy', 'tám', 'chín']


def read_two_digits(n: int, is_sub: bool = False) -> str:
    ten = n // 10
    unit = n % 10
    res = []
    if ten == 0:
        if is_sub:
            res.append('linh')
        res.append(UNITS[unit])
    elif ten == 1:
        res.append('mười')
        if unit == 1:
            res.append('một')
        elif unit == 5:
            res.append('lăm')
        elif unit > 0:
            res.append(UNITS[unit])
    else:
        res.append(UNITS[ten] + ' mươi')
        if unit == 1:
            res.append('mốt')
        elif unit == 4:
            res.append('tư')
        elif unit == 5:
            res.append('lăm')
        elif unit > 0:
            res.append(UNITS[unit])
    return ' '.join(res)


def read_three_digits(n: int, is_sub: bool = False) -> str:
    hundred = n // 100
    rem = n % 100
    if hundred > 0:
        res = [UNITS[hundred], 'trăm']
        if rem > 0:
            if rem < 10:
                res.extend(['linh', UNITS[rem]])
            else:
                res.append(read_two_digits(rem, is_sub=False))
        return ' '.join(res)
    else:
        if is_sub:
            res = ['không trăm']
            if rem > 0:
                if rem < 10:
                    res.extend(['linh', UNITS[rem]])
                else:
                    res.append(read_two_digits(rem, is_sub=False))
            return ' '.join(res)
        else:
            return read_two_digits(rem, is_sub=False)


def int_to_vietnamese(n: int) -> str:
    """Chuyển đổi số nguyên bất kỳ sang chữ tiếng Việt."""
    if n == 0:
        return 'không'
    if n < 0:
        return 'âm ' + int_to_vietnamese(abs(n))
    groups = []
    temp = n
    while temp > 0:
        groups.append(temp % 1000)
        temp //= 1000
    scales = ['', 'nghìn', 'triệu', 'tỷ', 'nghìn tỷ', 'triệu tỷ']
    words = []
    for i in range(len(groups) - 1, -1, -1):
        g = groups[i]
        if g > 0:
            is_sub = (i < len(groups) - 1)
            w = read_three_digits(g, is_sub=is_sub)
            words.append(w)
            if scales[i]:
                words.append(scales[i])
    return ' '.join(words)


def normalize_vietnamese_text(text: str) -> str:
    """
    Chuẩn hóa toàn bộ số, đơn vị, ký hiệu trong câu sang chữ tiếng Việt tự nhiên cho TTS.
    """
    if not text:
        return ''
    s = str(text).strip()

    # 1. Ratios: 1:1, 2:1, 16:9, etc.
    s = re.sub(
        r'(\d+)\s*:\s*(\d+)',
        lambda m: f'{int_to_vietnamese(int(m.group(1)))} {int_to_vietnamese(int(m.group(2)))}',
        s
    )

    # 2. Dimensions / rod lengths: 5m4, 3m6, 4m5, 6m3, 7m2, 8m1
    def _rod_m(m):
        m1 = int_to_vietnamese(int(m.group(1)))
        m2 = int_to_vietnamese(int(m.group(2)))
        return f'{m1} mét {m2}'
    s = re.sub(r'\b(\d+)\s*m(\d+)\b', _rod_m, s, flags=re.IGNORECASE)

    # 3. Units with numbers
    def _unit_m(m):
        num = int_to_vietnamese(int(m.group(1)))
        unit = m.group(2).lower()
        unit_map = {
            'm': 'mét', 'met': 'mét', 'mét': 'mét',
            'cm': 'xăng ti mét', 'mm': 'mi li mét', 'km': 'ki lô mét',
            'kg': 'ký', 'kí': 'ký', 'ký': 'ký', 'kilogram': 'ki lô gam',
            'g': 'gam', 'gram': 'gam', 'gam': 'gam',
            'k': 'nghìn',
            's': 'giây', 'giây': 'giây', 'giay': 'giây',
            'p': 'phút', 'phút': 'phút', 'phut': 'phút',
            'h': 'giờ', 'giờ': 'giờ', 'gio': 'giờ',
        }
        return f'{num} {unit_map.get(unit, unit)}'

    s = re.sub(
        r'\b(\d+)\s*(kg|kí|ký|kilogram|gram|gam|cm|mm|km|m|mét|met|giây|giay|phút|phut|giờ|gio|k)\b',
        _unit_m,
        s,
        flags=re.IGNORECASE
    )

    # 4. Percentages: 50%, 10%
    s = re.sub(r'(\d+)\s*%', lambda m: f'{int_to_vietnamese(int(m.group(1)))} phần trăm', s)

    # 5. Decimals: 0.4, 0,4, 1.5, 2.8
    def _decimal(m):
        integer_part = int(m.group(1))
        decimal_part = m.group(2)
        dec_words = ' '.join(UNITS[int(d)] for d in decimal_part)
        return f'{int_to_vietnamese(integer_part)} phẩy {dec_words}'

    s = re.sub(r'\b(\d+)[.,](\d+)\b', _decimal, s)

    # 6. Leading zero integers: 04, 01, 007
    def _leading_zero(m):
        digits = m.group(0)
        if len(digits) > 1 and digits.startswith('0'):
            return ' '.join(UNITS[int(d)] for d in digits)
        return int_to_vietnamese(int(digits))

    s = re.sub(r'\b0\d+\b', _leading_zero, s)

    # 7. Any remaining standalone integers
    s = re.sub(r'\b\d+\b', lambda m: int_to_vietnamese(int(m.group(0))), s)

    # 8. Clean up extra spaces
    s = re.sub(r'\s+', ' ', s).strip()
    return s
