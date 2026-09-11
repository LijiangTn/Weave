"""
文件存储路径生成

storage_dir/<source>/<YYYY>/<MM>/<DD>/<original_name>

保证不会硬编码路径，全部经 StorageConfig 注入。
"""

from datetime import datetime
from pathlib import Path

def safe_filename(name: str) -> str:
    """剥离路径分隔符，只保留 basename"""
    return Path(name).name or 'file'

def relative_path(source: str, file_name: str, *, date_subdir: bool = True) -> str:
    name = safe_filename(file_name)
    if date_subdir:
        today = datetime.now().strftime('%Y/%m/%d')
        return f'{source}/{today}/{name}'
    return f'{source}/{name}'

def absolute_path(storage_dir: str, relative: str) -> Path:
    path = Path(storage_dir) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

def unique_path(storage_dir: str, relative: str) -> Path:
    """若文件已存在，追加 _1/_2 后缀"""
    path = absolute_path(storage_dir, relative)
    if not path.exists():
        return path
    stem = path.stem
    ext = path.suffix
    parent = path.parent
    i = 1
    while True:
        candidate = parent / f'{stem}_{i}{ext}'
        if not candidate.exists():
            return candidate
        i += 1