from pathlib import Path
import numpy as np
import soundfile as sf
import pytest
from wuby_studio.config import merge,DEFAULT

@pytest.fixture
def cfg(tmp_path):
    return merge(DEFAULT,{'_root':str(tmp_path),'width':360,'height':640,'threads':1,'audio':{'mode':'preserve'},'cleanup':{'mode':'none'},'speech_qc':{'enabled':False},'logo':{'enabled':False}})

@pytest.fixture
def tone():
    def make(path,sec=.4,hz=330,sr=24000,amp=.15):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        t=np.arange(round(sec*sr))/sr;sf.write(path,amp*np.sin(2*np.pi*hz*t),sr)
        return path
    return make

@pytest.fixture
def source_video(tmp_path):
    from wuby_studio.common import run,binary
    p=tmp_path/'source.mp4'
    run([binary('ffmpeg'),'-y','-v','error','-f','lavfi','-i','color=c=0xe0eefa:s=360x640:r=24:d=2.5',
         '-f','lavfi','-i','sine=frequency=330:sample_rate=48000:duration=2.5','-c:v','libx264','-threads','1','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(p)])
    return p
