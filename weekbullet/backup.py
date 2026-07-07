"""
weekbullet — backup.py
壓縮備份與回滾模組。使用 zipfile（使用者指定），備份在原始檔案同目錄下。
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

MAX_BACKUPS = 10
# 保留的最新備份份數。超過此數的舊備份會在 backup() 時自動清理。

_RE_TIMESTAMP = re.compile(r'_(\d{8}_\d{6})(?:_\d+)?\.zip$')
# 從備份檔名中擷取時間戳的 regex。


@dataclass
class BackupInfo:
    path: Path          # 原始檔案
    backup_path: Path   # 備份檔 (.zip)
    timestamp: datetime
    size_bytes: int


# ═══════════════════════════════════════════════
# 核心函式


def backup(path: str | Path) -> BackupInfo:
    """
    備份指定檔案到同目錄下的 zip 壓縮檔。

    - 壓縮檔名：{filename}_{YYYYMMDD_HHMMSS}.zip
    - 使用 zipfile.ZIP_DEFLATED 壓縮。
    - 自動清理超過 MAX_BACKUPS 份的舊備份。
    - 回傳 BackupInfo。

    * path 可以是檔案或目錄（目錄會壓縮整個目錄的內容）。
    """
    obj = Path(path)
    now = datetime.now()
    ts = now.strftime('%Y%m%d_%H%M%S')
    backup_path = obj.parent / f'{obj.name}_{ts}.zip'

    # 確保不蓋寫（同一秒多個備份時加計數器）
    counter = 1
    while backup_path.exists():
        backup_path = obj.parent / f'{obj.name}_{ts}_{counter}.zip'
        counter += 1

    if obj.is_dir():
        _zip_dir(obj, backup_path)
    else:
        _zip_file(obj, backup_path)

    info = BackupInfo(
        path=obj,
        backup_path=backup_path,
        timestamp=now,
        size_bytes=backup_path.stat().st_size,
    )

    _clean_old_backups(obj)
    return info


def rollback(path: str | Path, version: str | None = None) -> bool:
    """
    回滾到指定版本。

    - version = None  → 最新備份
    - version = '20260707_143000'  → 指定時間點
    - 回滾前會自動備份當前狀態（雙重保險）。
    - 回傳是否成功。
    """
    obj = Path(path)
    if not obj.exists():
        return False

    backups = list_backups(obj)
    if not backups:
        return False

    target: BackupInfo | None = None
    if version is None:
        target = backups[0]  # 最新
    else:
        for b in backups:
            if b.timestamp.strftime('%Y%m%d_%H%M%S') == version:
                target = b
                break
        if target is None:
            for b in backups:
                if b.timestamp.strftime('%Y%m%d_%H%M%S').startswith(version):
                    target = b
                    break

    if target is None:
        return False

    # 自動備份當前狀態（雙重保險）
    backup(obj)

    try:
        with zipfile.ZipFile(target.backup_path, 'r') as zf:
            if obj.is_dir():
                for child in obj.iterdir():
                    if child.is_dir():
                        _rmtree(child)
                    else:
                        child.unlink()
                zf.extractall(obj)
            else:
                names = zf.namelist()
                if len(names) == 1:
                    data = zf.read(names[0])
                    obj.write_bytes(data)
                else:
                    zf.extractall(obj.parent)
        return True
    except Exception:
        return False


def list_backups(path: str | Path) -> list[BackupInfo]:
    """列出所有備份版本（按時間遞減排序）"""
    obj = Path(path)
    pattern = f'{obj.name}_????????_??????*.zip'
    candidates = sorted(obj.parent.glob(pattern), reverse=True)

    result: list[BackupInfo] = []
    for zipp in candidates:
        ts_str = _parse_timestamp(zipp.name)
        if ts_str is None:
            continue
        try:
            ts = datetime.strptime(ts_str, '%Y%m%d_%H%M%S')
        except ValueError:
            continue
        result.append(BackupInfo(
            path=obj,
            backup_path=zipp,
            timestamp=ts,
            size_bytes=zipp.stat().st_size,
        ))
    result.sort(key=lambda x: x.timestamp, reverse=True)
    return result


# ═══════════════════════════════════════════════
# Context Manager


class auto_backup:
    """
    Context manager：進入時自動備份，離開時若發生 Exception 自動回滾。

    用法::

        with auto_backup('weekly.md') as bak:
            ...  # 修改檔案
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def __enter__(self) -> BackupInfo:
        self.bak = backup(self.path)
        return self.bak

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is not None:
            ts = self.bak.timestamp.strftime('%Y%m%d_%H%M%S')
            rollback(self.path, ts)
            return False  # 不吞 exception
        return False


# ═══════════════════════════════════════════════
# 內部輔助


def _parse_timestamp(name: str) -> str | None:
    """從檔名中擷取 YYYYMMDD_HHMMSS 時間戳"""
    m = _RE_TIMESTAMP.search(name)
    return m.group(1) if m else None


def _zip_file(src: Path, dst: Path) -> None:
    """壓縮單一檔案"""
    with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(src, arcname=src.name)


def _zip_dir(src: Path, dst: Path) -> None:
    """壓縮整個目錄（包含子目錄結構）"""
    with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as zf:
        for entry in sorted(src.rglob('*')):
            arcname = str(entry.relative_to(src.parent))
            if entry.is_dir():
                zf.mkdir(arcname)
            else:
                zf.write(entry, arcname=arcname)


def _clean_old_backups(path: Path) -> None:
    """清理超過 MAX_BACKUPS 份的舊備份"""
    backups = list_backups(path)
    if len(backups) <= MAX_BACKUPS:
        return
    for old in backups[MAX_BACKUPS:]:
        try:
            old.backup_path.unlink(missing_ok=True)
        except OSError:
            pass


def _rmtree(path: Path) -> None:
    """遞迴刪除目錄"""
    for child in path.iterdir():
        if child.is_dir():
            _rmtree(child)
        else:
            child.unlink()
    path.rmdir()
