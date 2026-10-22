"""Opt-in font install on the user's machine. No fonts are shipped in the ZIP."""
from pathlib import Path
import argparse,urllib.request,hashlib,json
ROOT=Path(__file__).resolve().parents[1]
FONT='https://raw.githubusercontent.com/google/fonts/main/ofl/bevietnampro/BeVietnamPro-Bold.ttf'
LICENSE='https://raw.githubusercontent.com/google/fonts/main/ofl/bevietnampro/OFL.txt'
def main():
    p=argparse.ArgumentParser();p.add_argument('--font',action='store_true');a=p.parse_args()
    if not a.font:p.error('Use --font to download the font and its OFL license')
    target=ROOT/'assets/fonts';target.mkdir(parents=True,exist_ok=True)
    for url,name in [(FONT,'BeVietnamPro-Bold.ttf'),(LICENSE,'BeVietnamPro-OFL.txt')]:
        req=urllib.request.Request(url,headers={'User-Agent':'WubyLocal/7'})
        with urllib.request.urlopen(req,timeout=45) as res:data=res.read(3*1024*1024)
        if name.endswith('.ttf') and data[:4] not in (b'\x00\x01\x00\x00',b'OTTO'):raise RuntimeError('Not a TrueType/OpenType font response')
        path=target/name;tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_bytes(data);tmp.replace(path)
        print(name,hashlib.sha256(data).hexdigest())
    print('Font installed locally. No cloud account required.')
if __name__=='__main__':main()
