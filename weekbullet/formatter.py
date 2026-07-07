"""
weekbullet — formatter.py
將 Document model 格式化為人類可讀的文字輸出。
支援 terminal 與 Telegram 兩種輸出模式。
"""

from .model import Document, Section, BulletItem, WeekHeader, DayEntry


def format_bullet_list(section: Section, show_done: bool = True) -> str:
    """將 Section 格式化為有序號的 bullet 列表"""
    lines = []
    for idx, item in enumerate(section.items, 1):
        if not show_done and item.is_done:
            continue
        tag = f" ({item.tag})" if item.tag else ""
        done_mark = " ✅" if item.is_done else ""
        display = f"{idx}. {item.symbol}{done_mark}{tag} {item.text[:80]}"
        lines.append(display)
    return '\n'.join(lines)


def format_week(week: WeekHeader, max_days: int = 0) -> str:
    """格式化一週摘要
    
    Args:
        week: 週資料
        max_days: 最多顯示幾天（0 = 全部）
    """
    lines = [f"📅 {week.header}"]
    days = week.days[:max_days] if max_days else week.days
    
    for day in days:
        count = len(day.bullets)
        if count > 0:
            lines.append(f"  {day.header} ({count} 條)")
        else:
            lines.append(f"  {day.header}")
    
    total = sum(len(d.bullets) for d in week.days)
    lines.append(f"  ── 共 {len(week.days)} 天 / {total} 條")
    return '\n'.join(lines)


def format_date(doc: Document, year: int, month: int, day: int) -> str:
    """彙整指定日期的 all_day 資訊
    
    從所有區塊尋找與該日期相關的內容：
    - 重要行程中是否有該日期
    - 週記錄中該日的條目
    - 採購清單（當日新增的，簡單顯示）
    """
    date_str = f"{year}/{month:02d}/{day:02d}"
    weekday = _weekday_name(year, month, day)
    lines = [f"━━━ {date_str}（{weekday}）━━━"]
    
    # 從週記錄找該日條目
    found = False
    for week in doc.weeks:
        for day_entry in week.days:
            # 比對日期
            if _match_date(day_entry.header, month, day):
                found = True
                lines.append(f"\n📆 {day_entry.header}")
                for item in day_entry.bullets:
                    tag = f" ({item.tag})" if item.tag else ""
                    lines.append(f"  {item.symbol}{tag} {item.text[:80]}")
    
    if not found:
        lines.append("  （該日無週記錄條目）")
    
    return '\n'.join(lines)


def format_status(doc: Document) -> str:
    """整份週記狀態總覽"""
    lines = [f"📊 週記狀態 — {doc.year}年", ""]
    
    # 各區塊條數
    for name, attr in [('長期任務', 'tasks_section'), 
                        ('週期提醒', 'reminders_section'),
                        ('重要行程', 'schedule_section'),
                        ('採購清單', 'shopping_section')]:
        sec = getattr(doc, attr, None)
        if sec:
            total = len(sec.items)
            done = sum(1 for i in sec.items if i.is_done)
            lines.append(f"📋 {name}: {total} 項（{done} 完成）")
    
    # 週記錄
    total_weeks = len(doc.weeks)
    total_days = sum(len(w.days) for w in doc.weeks)
    total_items = sum(len(d.bullets) for w in doc.weeks for d in w.days)
    lines.append(f"📅 週記錄: {total_weeks} 週 / {total_days} 天 / {total_items} 條")
    
    # 最新幾週
    lines.append(f"\n📌 最新 3 週：")
    for w in doc.weeks[:3]:
        day_count = len(w.days)
        item_count = sum(len(d.bullets) for d in w.days)
        lines.append(f"  {w.header} → {day_count} 天, {item_count} 條")
    
    return '\n'.join(lines)


def _weekday_name(year: int, month: int, day: int) -> str:
    """回傳中文星期幾"""
    import datetime as _dt
    try:
        w = _dt.date(year, month, day).weekday()  # 0=Mon
        return ['週一', '週二', '週三', '週四', '週五', '週六', '週日'][w]
    except:
        return ''


def _match_date(header: str, month: int, day: int) -> bool:
    """檢查 ##### header 是否匹配指定月/日"""
    import re
    m = re.search(r'(\d{1,2})/(\d{1,2})', header)
    if m:
        return int(m.group(1)) == month and int(m.group(2)) == day
    return False
