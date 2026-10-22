#!/usr/bin/env python3
"""Compatibility entrypoint: prerequisite report only, NEVER a clone-quality PASS.
Use test-voice + listened approval to evaluate an actual reference-conditioned sample.
"""
from __future__ import annotations
import json
from wuby_studio.cli import doctor

def main():
    report=doctor()
    report['notice']='Package/cache/CUDA checks do not verify voice identity. ZeroTTS fallback is not used for Wuby clone.'
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())
