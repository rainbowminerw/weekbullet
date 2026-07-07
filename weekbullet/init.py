"""
weekbullet — init.py
建立新年度週記，使用 parser 的 regex 功能讀取「### 特別要求」區塊。
"""
import re
from pathlib import Path
from datetime import date

from weekbullet.parser import RE_H3, RE_YEAR, parse_year_from_preamble


def _find_source() -> Path:
    """自動偵測前一年週記檔位置（跟 weekbullet 套件同目錄）"""
    # __file__ = .../日誌/weekbullet/weekbullet/init.py
    # 上三層 = .../日誌/
    journal_dir = Path(__file__).resolve().parent.parent.parent
    return journal_dir / '2026 年週記.md'


def _extract_special_requirements(lines: list[str]) -> list[str]:
    """從行列表中取出「### 特別要求」區塊（含 header 到下一 ### 前）

    使用 parser 的 RE_H3 識別區塊邊界。
    行號範圍：從 ### 特別要求 到 下一個 ### 前。
    """
    start = None
    end = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == '### 特別要求':
            start = i
        elif start is not None and RE_H3.match(stripped) and i > start:
            end = i
            break
    if start is None:
        return []
    return lines[start:end]


def create_new_journal(year: int, source_path: str | None = None) -> str:
    """
    建立新年度週記。

    Args:
        year: 目標年份
        source_path: 前一年週記路徑，None 表示自動偵測

    Returns:
        新檔案絕對路徑

    Raises:
        FileNotFoundError: 來源檔案不存在
        FileExistsError: 目標檔案已存在
    """
    # ── 來源檔案 ──
    src = Path(source_path) if source_path else _find_source()
    if not src.exists():
        raise FileNotFoundError(f'找不到來源週記：{src}')

    # ── 目標路徑（與 source 同一目錄）──
    target = src.parent / f'{year} 年週記.md'
    if target.exists():
        raise FileExistsError(f'目標檔案已存在：{target}')

    # ── 讀取來源 ──
    src_lines = src.read_text(encoding='utf-8').splitlines()

    # ── 取出特別要求區塊 ──
    special = _extract_special_requirements(src_lines)

    # ── 組合新檔案內容 ──
    new_lines = [f'# {year} 年週記', '']

    if special:
        new_lines.extend(special)
        new_lines.extend(['', ''])

    # 標準 sections（新建年度不需任何任務/行程/提醒資料）
    new_lines.append('### 長期任務與未定時間項目')
    new_lines.extend(['', ''])
    new_lines.append('### 重要行程')
    new_lines.extend(['', ''])
    new_lines.append('### 採購清單')
    new_lines.extend(['', ''])
    new_lines.append('### 📅 長期週期性提醒')
    new_lines.extend(['', '', ''])
    new_lines.append('## 每週記錄')
    new_lines.append('')

    # ── 寫入 ──
    target.write_text('\n'.join(new_lines), encoding='utf-8')
    return str(target.resolve())
