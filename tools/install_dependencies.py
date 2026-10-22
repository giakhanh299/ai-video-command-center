"""Install ONLY missing lightweight dependencies into the chosen existing venv.
Never installs/upgrades Torch, CUDA, reference models or OCR models implicitly.
"""
import argparse,importlib.util,subprocess,sys
BASE={'PIL':'Pillow>=10,<13','numpy':'numpy>=1.24,<3','scipy':'scipy>=1.11,<2',
      'soundfile':'soundfile>=0.12,<1','filelock':'filelock>=3.13,<4','dotenv':'python-dotenv>=1,<2',
      'pydub':'pydub>=0.25,<1','requests':'requests>=2.31,<3','cv2':'opencv-python>=4.8,<5',
      'openai':'openai>=1.50,<3','yt_dlp':'yt-dlp[default]','gdown':'gdown>=5,<6','pytest':'pytest>=8,<10'}
def main():
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args()
    print('Interpreter:',sys.executable,'\nPython:',sys.version)
    print('Torch/CUDA/torchaudio/transformers are NOT changed by this installer.')
    missing=[pkg for module,pkg in BASE.items() if importlib.util.find_spec(module) is None]
    print('Missing:',missing)
    if missing and a.apply:subprocess.run([sys.executable,'-m','pip','install',*missing],check=True)
    elif missing:print('Review interpreter, then run again with --apply')
    print('Optional speech/OCR: use existing compatible faster-whisper/EasyOCR environment; see docs/LOCAL_MODEL_SETUP.md')
if __name__=='__main__':main()
