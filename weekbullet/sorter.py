"""
weekbullet — sorter.py
各區塊專屬排序演算法。

排序規則（師兄指定）：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【週期提醒】
① 已完成排最後
② 一期性的排前（無頻率標記 = 一期性）
③ 頻率分四階：一天多次 > 每週多次 > 每1~數週 > 每1~數月
④ 相同階內：24時制 → 週一~週日 → 1號~31號

【長期任務】
① 已完成排最後
② 依到期時間緊迫性（截止日最近的在前）
③ 無截止日在有截止日之後

【重要行程】
① 已完成排最後
② 依日期遞增（最近的在前）
③ 過期的往後

【採購清單】
① 未完成在前，已完成在後
② 無進一步排序

【每週記錄】
① 週 header：newest first
② 週內日 header：newest first
③ 日內條目：保持原始順序
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import re
from datetime import date as _date
from typing import Callable

from weekbullet.model import Document, Section, BulletItem, WeekHeader, DayEntry

# ── 頻率階層 ──
TIER_DAILY_MULTI = 0   # 一天多次
TIER_WEEKLY_MULTI = 1  # 每週多次
TIER_BIWEEKLY = 2      # 每1~數週
TIER_MONTHLY = 3       # 每1~數月
TIER_ONESHOT = 4       # 一期性（無週期標記）
TIER_DONE = 5          # 已完成

# ── 頻率偵測 regex ──
RE_TIME = re.compile(r'(\d{1,2}):(\d{2})')           # HH:MM
RE_WEEKDAY = re.compile(r'週([一二三四五六日天])')   # 週X
RE_DATE_NUM = re.compile(r'(\d{1,2})[號日]')          # X號/X日
RE_DATE_SLASH = re.compile(r'(\d{1,2})/(\d{1,2})')    # M/D (deadline detection)

# 頻率關鍵字組合（依權重由高到低判斷）
DAILY_KEYWORDS = ['每天', '每日', '早晚', '每餐', '一天']
WEEKLY_KEYWORDS = ['每週', '每周']
BIWEEKLY_KEYWORDS = ['每兩週', '每二週', '每三週', '每2週', '每3週', '隔週', '每雙週', '每單週']
MONTHLY_KEYWORDS = ['每月', '每兩個月', '每三個月', '每季', '每半年', '每年']


# ═══════════════════════════════════════════════
# 頻率偵測
# ═══════════════════════════════════════════════


def _detect_frequency_tier(text: str) -> int:
    """從文字偵測頻率階層。已完成項目自動分到 TIER_DONE。"""
    t = text.lower().replace(' ', '')
    for kw in DAILY_KEYWORDS:
        if kw in t:
            return TIER_DAILY_MULTI
    for kw in BIWEEKLY_KEYWORDS:
        if kw in t:
            return TIER_BIWEEKLY
    for kw in WEEKLY_KEYWORDS:
        if kw in t:
            return TIER_WEEKLY_MULTI
    # 有特定星期幾但無「每週」→ 假設每週多次
    if RE_WEEKDAY.search(text):
        return TIER_WEEKLY_MULTI
    for kw in MONTHLY_KEYWORDS:
        if kw in t:
            return TIER_MONTHLY
    return TIER_ONESHOT


def _extract_frequency_sort_key(text: str) -> tuple:
    """回傳頻率排序用 tuple：(tier, hour, minute, weekday, day_num)"""
    tier = _detect_frequency_tier(text)

    # 提取時間 HH:MM
    m_time = RE_TIME.search(text)
    hour = int(m_time.group(1)) if m_time else 99
    minute = int(m_time.group(2)) if m_time else 99

    # 提取星期
    m_wd = RE_WEEKDAY.search(text)
    wd_map = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '日': 7, '天': 7}
    weekday = wd_map.get(m_wd.group(1), 99) if m_wd else 99

    # 提取日期數字
    m_dn = RE_DATE_NUM.search(text)
    day_num = int(m_dn.group(1)) if m_dn else 99

    return (tier, hour, minute, weekday, day_num)


# ═══════════════════════════════════════════════
# 任務截止日偵測
# ═══════════════════════════════════════════════


def _extract_deadline(text: str) -> tuple:
    """從任務文字提取截止日。回傳 (month, day) 或 (99, 99)。"""
    # 格式：(截止：M/D)
    m = re.search(r'截止[：:]?\s*(\d{1,2})/(\d{1,2})', text)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    # 格式：(M/D-M/D) 或 (M/D起)
    m = re.search(r'[（(](\d{1,2})/(\d{1,2})', text)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    # 格式：M/D（週X）— 行程用
    m = re.search(r'(\d{1,2})/(\d{1,2})（週', text)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return (99, 99)


def _extract_schedule_date(text: str) -> tuple:
    """從行程文字提取日期。回傳 (month, day) 或 (99, 99)。"""
    # 格式：M/D-D（週X）或 M/D（週X）
    m = re.search(r'(\d{1,2})/(\d{1,2})', text)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return (99, 99)


# ═══════════════════════════════════════════════
# 區塊排序
# ═══════════════════════════════════════════════


def sort_tasks(items: list[BulletItem]):
    """長期任務排序：已完成最後，其餘依截止日緊迫性"""
    def key(item: BulletItem) -> tuple:
        if item.is_done:
            return (1, 99, 99)  # 全部已完成排最後
        mo, da = _extract_deadline(item.text)
        # 無截止日的在後
        if mo == 99:
            return (0, 99, 99)
        return (0, mo, da)
    items.sort(key=key)


def sort_schedule(items: list[BulletItem]):
    """重要行程排序：已完成最後，其餘依日期遞增"""
    def key(item: BulletItem) -> tuple:
        if item.is_done:
            return (1, 99, 99)
        mo, da = _extract_schedule_date(item.text)
        if mo == 99:
            return (0, 99, 99)
        return (0, mo, da)
    items.sort(key=key)


def sort_reminders(items: list[BulletItem]):
    """週期提醒排序：已完成最後，其餘依頻率階層→時間→星期→日期"""
    def key(item: BulletItem) -> tuple:
        if item.is_done:
            return (TIER_DONE, 99, 99, 99, 99)
        return _extract_frequency_sort_key(item.text)
    items.sort(key=key)


def sort_shopping(items: list[BulletItem]):
    """採購清單排序：未完成在前，已完成在後"""
    def key(item: BulletItem) -> bool:
        return item.is_done
    items.sort(key=key)


# ── 區塊排序對照表 ──
SECTION_SORTERS: dict[str, Callable] = {
    'tasks': sort_tasks,
    'schedule': sort_schedule,
    'reminders': sort_reminders,
    'shopping': sort_shopping,
}


# ═══════════════════════════════════════════════
# 每週記錄排序
# ═══════════════════════════════════════════════


def sort_weeks(doc: Document):
    """週記錄排序：newest first"""
    doc.weeks.sort(
        key=lambda w: (w.year, w.month_start, w.day_start),
        reverse=True,
    )


def sort_days(week: WeekHeader):
    """週內日 header 排序：newest first"""
    week.days.sort(
        key=lambda d: _extract_day_date(d.header, week.year),
        reverse=True,
    )


def _extract_day_date(header: str, year: int) -> _date:
    """從 ##### MM/DD（週X）提取 date object"""
    m = RE_DATE_SLASH.search(header)
    if m:
        try:
            return _date(year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            pass
    return _date(1, 1, 1)


# ═══════════════════════════════════════════════
# Document 層級排序
# ═══════════════════════════════════════════════


def sort_document(doc: Document):
    """對整個 Document 進行完整排序（區塊 + 週記錄）"""
    # 1. 區塊內排序
    for name, sorter in SECTION_SORTERS.items():
        sec = doc.get_section(name)
        if sec and sec.items:
            sorter(sec.items)

    # 2. 週記錄排序（newest first）
    sort_weeks(doc)

    # 3. 週內日排序
    for w in doc.weeks:
        sort_days(w)
