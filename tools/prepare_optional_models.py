"""Explicit user opt-in downloads. Run in the existing model-compatible venv."""
import argparse

def main():
    p=argparse.ArgumentParser();p.add_argument('--asr',help='Whisper model size or local CTranslate2 folder, e.g. small');p.add_argument('--ocr',action='store_true');a=p.parse_args()
    if not a.asr and not a.ocr:p.error('Specify --asr small and/or --ocr')
    if a.asr:
        from faster_whisper import WhisperModel
        m=WhisperModel(a.asr,device='cpu',compute_type='int8',local_files_only=False)
        print('ASR weights available locally:',a.asr);del m
    if a.ocr:
        import easyocr
        m=easyocr.Reader(['ch_sim','en'],gpu=False,download_enabled=True)
        print('OCR weights available locally.');del m
    print('No voice-clone weights or references were installed by this command.')
if __name__=='__main__':main()
