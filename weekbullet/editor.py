"""
weekbullet — editor.py
以 model-based 方式進行 add / edit / delete 操作。

核心流程：
1. load_for_edit() → parse 為 Document（保留原始文字作 fallback）
2. 在 model 上執行操作（add / edit / delete item）
3. 標記被修改的區塊為 dirty
4. save_document() → renderer 只重建 dirty 區塊，其餘保留原始 → auto_backup 寫入
"""
from __future__ import annotations

import re
from pathlib import Path
from datetime import date as _date

from weekbullet.model import BulletItem
from weekbullet.parser import Parser, RE_DAY
from weekbullet.renderer import load_for_edit, save_document
from weekbullet.sorter import SECTION_SORTERS


def _format_date_prefix(
    date_str: str | None,
    end_str: str | None,
    section_name: str,
    text: str,
) -> str:
    """依區塊類型將日期格式化為文字前綴/後綴。

    schedule: 前綴 → M/D（週X）事件 或 M/D-D（週X～Y）事件
    task:     後綴 → 事件（截止：M/D）或 事件（M/D-M/D）
    reminder: 後綴 → 事件（M/D起）或 事件（M/D-M/D）

    跨年處理：自動依各日期所屬年份計算星期。
    """
    if not date_str:
        return text
    from datetime import datetime as _dt
    wdays = ['一', '二', '三', '四', '五', '六', '日']
    start = _dt.strptime(date_str, '%Y-%m-%d')
    sw = wdays[start.weekday()]
    sf = f'{start.month}/{start.day}'

    if section_name == 'schedule':
        if end_str:
            end = _dt.strptime(end_str, '%Y-%m-%d')
            ew = wdays[end.weekday()]
            ef = f'{end.month}/{end.day}'
            if start.year != end.year:
                return f'{sf}（{sw}）至 {ef}（{ew}）{text}'
            if start.month == end.month:
                return f'{sf}-{end.day}（{sw}～{ew}）{text}'
            return f'{sf}（{sw}）至 {ef}（{ew}）{text}'
        return f'{sf}（{sw}）{text}'

    if section_name == 'tasks':
        if end_str:
            end = _dt.strptime(end_str, '%Y-%m-%d')
            return f'{text}（{sf}-{end.month}/{end.day}）'
        return f'{text}（截止：{sf}）'

    if section_name == 'reminders':
        if end_str:
            end = _dt.strptime(end_str, '%Y-%m-%d')
            return f'{text}（{sf}-{end.month}/{end.day}）'
        return f'{text}（{sf}起）'

    return text


# ═══════════════════════════════════════════════
# ### 區塊操作
# ═══════════════════════════════════════════════

def _find_day(doc, year: int, month: int, day: int):
    """從 doc 中找到對應的 DayEntry"""
    for week in doc.weeks:
        if week.year != year:
            continue
        for d in week.days:
            m = RE_DAY.match(d.header)
            if m and int(m.group(1)) == month and int(m.group(2)) == day:
                return d
    return None


def _find_day_by_str(doc, date_str: str):
    parts = date_str.split('-')
    if len(parts) != 3:
        return None
    return _find_day(doc, int(parts[0]), int(parts[1]), int(parts[2]))


def add_section_item(
    path: str,
    section_name: str,
    text: str,
    symbol: str = '●',
    dry_run: bool = False,
    date_str: str | None = None,
    end_str: str | None = None,
    pending: bool = False,
) -> str:
    """在指定區塊新增一條 item（model-based）"""
    doc = load_for_edit(path)[0]
    sec = doc.get_section(section_name)
    if sec is None:
        raise ValueError(f'找不到「{section_name}」區塊')

    final_text = _format_date_prefix(date_str, end_str, section_name, text)

    item = BulletItem(
        line_no=0,  # renderer 會重新計算
        raw='',
        symbol=symbol,
        text=final_text,
        is_done=(symbol == 'ok'),
        is_pending=pending,
        tag='',
    )
    if dry_run:
        sym_display = f'{symbol}?' if pending else symbol
        return f'🔍 預覽：將新增「{sym_display} {final_text}」至「{sec.header}」'
    sec.items.append(item)
    # 排序
    sorter = SECTION_SORTERS.get(section_name)
    if sorter:
        sorter(sec.items)
    doc._dirty.add(section_name)

    save_document(doc)
    return f'✅ 已新增至「{sec.header}」：{_render_item_str(item)}'


def edit_section_item(
    path: str,
    section_name: str,
    index: int,
    new_text: str | None = None,
    new_symbol: str | None = None,
    dry_run: bool = False,
    date_str: str | None = None,
    end_str: str | None = None,
) -> str:
    """修改區塊中第 N 條 item（1-based）"""
    doc = load_for_edit(path)[0]
    sec = doc.get_section(section_name)
    if sec is None:
        raise ValueError(f'找不到「{section_name}」區塊')
    if index < 1 or index > len(sec.items):
        raise ValueError(f'索引 {index} 超出範圍（1~{len(sec.items)}）')

    item = sec.items[index - 1]
    old = f'{item.symbol} {item.text}'
    if new_text is not None:
        item.text = new_text
    if new_symbol is not None:
        item.symbol = new_symbol
        if new_symbol == 'ok':
            item.is_done = True
    if date_str is not None:
        item.text = _format_date_prefix(date_str, end_str, section_name, item.text)
    if dry_run:
        return f'🔍 預覽：將修改第 {index} 項「{old}」→「{item.symbol} {item.text}」'
    doc._dirty.add(section_name)

    save_document(doc)
    return f'✅ 已修改第 {index} 項：{_render_item_str(item)}'


def delete_section_item(
    path: str,
    section_name: str,
    index: int,
    dry_run: bool = False,
) -> str:
    """刪除區塊中第 N 條 item（1-based）"""
    doc = load_for_edit(path)[0]
    sec = doc.get_section(section_name)
    if sec is None:
        raise ValueError(f'找不到「{section_name}」區塊')
    if index < 1 or index > len(sec.items):
        raise ValueError(f'索引 {index} 超出範圍（1~{len(sec.items)}）')

    item = sec.items[index - 1]
    if dry_run:
        return f'🔍 預覽：將刪除第 {index} 項「{_render_item_str(item)}」'
    removed = sec.items.pop(index - 1)
    doc._dirty.add(section_name)

    save_document(doc)
    return f'🗑️ 已刪除第 {index} 項：{_render_item_str(removed)}'


def _render_item_str(item: BulletItem) -> str:
    """簡易渲染（用於預覽/回顯）"""
    sym = '●' if item.symbol == 'ok' else item.symbol
    text = item.text.lstrip('✅ ').strip()
    if item.is_pending:
        return f'{sym}? {text}'
    if item.is_done:
        return f'{sym} ok {text}'
    return f'{sym} {text}'


# ═══════════════════════════════════════════════
# 日條目操作
# ═══════════════════════════════════════════════


def add_day_entry(
    path: str,
    date_str: str,
    text: str,
    symbol: str = '－',
    dry_run: bool = False,
) -> str:
    """在指定日期的週記錄中新增一條 item"""
    doc = load_for_edit(path)[0]
    day = _find_day_by_str(doc, date_str)
    if day is None:
        raise ValueError(f'找不到日期「{date_str}」的條目')

    if dry_run:
        return f'🔍 預覽：將新增「{symbol} {text}」至 {date_str}'
    item = BulletItem(
        line_no=0, raw='',
        symbol=symbol, text=text,
        is_done=False, tag='',
    )
    day.bullets.append(item)
    doc._dirty.add('entry')

    save_document(doc)
    return f'✅ 已新增至 {date_str}：{symbol} {text}'


def edit_day_entry(
    path: str,
    date_str: str,
    index: int,
    new_text: str | None = None,
    new_symbol: str | None = None,
    dry_run: bool = False,
) -> str:
    """修改指定日期第 N 條 item"""
    doc = load_for_edit(path)[0]
    day = _find_day_by_str(doc, date_str)
    if day is None:
        raise ValueError(f'找不到日期「{date_str}」的條目')
    if index < 1 or index > len(day.bullets):
        raise ValueError(f'索引 {index} 超出範圍（1~{len(day.bullets)}）')

    item = day.bullets[index - 1]
    old = f'{item.symbol} {item.text}'
    if new_text is not None:
        item.text = new_text
    if new_symbol is not None:
        item.symbol = new_symbol
    if dry_run:
        return f'🔍 預覽：將修改 {date_str} 第 {index} 項「{old}」→「{item.symbol} {item.text}」'
    doc._dirty.add('entry')

    save_document(doc)
    return f'✅ 已修改 {date_str} 第 {index} 項：{item.symbol} {item.text}'


def delete_day_entry(
    path: str,
    date_str: str,
    index: int,
    dry_run: bool = False,
) -> str:
    """刪除指定日期第 N 條 item"""
    doc = load_for_edit(path)[0]
    day = _find_day_by_str(doc, date_str)
    if day is None:
        raise ValueError(f'找不到日期「{date_str}」的條目')
    if index < 1 or index > len(day.bullets):
        raise ValueError(f'索引 {index} 超出範圍（1~{len(day.bullets)}）')

    item = day.bullets[index - 1]
    preview = f'{item.symbol} {item.text}'
    if dry_run:
        return f'🔍 預覽：將刪除 {date_str} 第 {index} 項「{preview}」'
    removed = day.bullets.pop(index - 1)
    doc._dirty.add('entry')

    save_document(doc)
    return f'🗑️ 已刪除 {date_str} 第 {index} 項：{removed.symbol} {removed.text}'


# ═══════════════════════════════════════════════
# 週操作
# ═══════════════════════════════════════════════


def add_week(path: str, start_m: int, start_d: int,
             end_m: int | None = None, end_d: int | None = None,
             dry_run: bool = False) -> str:
    """新增週區塊（若已存在則跳過）"""
    from datetime import date as _date, timedelta

    doc = load_for_edit(path)[0]

    # 推算結束日
    if end_m is None or end_d is None:
        today = _date.today()
        start = _date(today.year, start_m, start_d)
        end = start + timedelta(days=6)
        end_m, end_d = end.month, end.day

    header_str = f'#### {start_m:02d}/{start_d:02d} 至 {end_m:02d}/{end_d:02d}'

    # 檢查是否已存在
    for w in doc.weeks:
        if w.header == header_str:
            return f'⚠️ 週區塊已存在：{header_str}'

    if dry_run:
        return f'🔍 預覽：將新增週區塊「{header_str}」'

    from weekbullet.model import WeekHeader, DayEntry

    week = WeekHeader(
        line_no=0, header=header_str,
        year=doc.year,
        month_start=start_m, day_start=start_d,
        month_end=end_m, day_end=end_d,
    )
    # 建立第一天條目
    wdays = ['一', '二', '三', '四', '五', '六', '日']
    first_wday = wdays[_date(doc.year, start_m, start_d).weekday()]
    day = DayEntry(
        line_no=0,
        header=f'##### {start_m:02d}/{start_d:02d}（週{first_wday}）',
    )
    week.days.append(day)
    doc.weeks.append(week)  # 加到最後（後面需排序）
    doc._dirty.add('entry')

    # 排序：newest first
    doc.weeks.sort(key=lambda w: (w.year, w.month_start, w.day_start), reverse=True)

    save_document(doc)
    return f'✅ 已新增週區塊：{header_str}'
