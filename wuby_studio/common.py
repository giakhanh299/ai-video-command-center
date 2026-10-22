from __future__ import annotations
import hashlib, json, math, os, shutil, subprocess, tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
class WubyError(RuntimeError): pass
class NeedsReview(WubyError): pass
class TimingError(NeedsReview): pass
class ConfigError(WubyError): pass

def sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()

def _default_serializer(o):
    if hasattr(o, 'item'): return o.item()
    if hasattr(o, '__int__'): return int(o)
    if hasattr(o, '__float__'): return float(o)
    if isinstance(o, Path): return str(o)
    return str(o)

def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False, default=_default_serializer).encode()).hexdigest()

def atomic_json(path: str | Path, value: Any) -> None:
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=path.name+'.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False, default=_default_serializer); f.flush(); os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)

def resolve(value: str | Path, root: Path = ROOT) -> Path:
    p = Path(value).expanduser()
    return (p if p.is_absolute() else root / p).resolve()

def inside(root: Path, name: str) -> Path:
    p = (root / name).resolve()
    if not p.is_relative_to(root.resolve()): raise ConfigError('PATH_OUTSIDE_ALLOWED_DIRECTORY')
    return p

def binary(name: str) -> str:
    env_name = 'FFMPEG_BINARY' if name == 'ffmpeg' else 'FFPROBE_BINARY'
    override = os.getenv(env_name)
    if override:
        if not Path(override).is_file(): raise ConfigError(f'{env_name} points to a missing file')
        return override
    found = shutil.which(name)
    if found: return found
    if name == 'ffprobe' and os.getenv('FFMPEG_BINARY'):
        p = Path(os.environ['FFMPEG_BINARY']).with_name('ffprobe.exe' if os.name=='nt' else 'ffprobe')
        if p.is_file(): return str(p)
    raise ConfigError(f'{name} not found. Install FFmpeg binary (not the Python package).')

def run(args: list[str], timeout: float = 1800, **kwargs) -> subprocess.CompletedProcess:
    result = subprocess.run([str(a) for a in args], capture_output=True, timeout=timeout, **kwargs)
    if result.returncode:
        err = result.stderr.decode('utf-8', errors='replace') if isinstance(result.stderr, bytes) else result.stderr
        raise WubyError(f'COMMAND_FAILED [{Path(args[0]).name}]: {err[-6000:]}')
    return result

def finite(value: Any, low: float, high: float, name: str) -> float:
    v = float(value)
    if not math.isfinite(v) or not low <= v <= high: raise ConfigError(f'{name}: expected {low}..{high}')
    return v
