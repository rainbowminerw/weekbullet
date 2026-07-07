"""
weekbullet — parser.py
逐行狀態機 + regex，將 md 週記解析為 Document model。
"""

import re
from pathlib import Path

from weekbullet.model import (
    Document, Section, BulletItem, WeekHeader, DayEntry,
    LINE_SYMBOLS, SYMBOL_TASK, SYMBOL_OLD_OK, SYMBOL_EVENT,
)

# ── 區塊標題常數 ──
SEC_TASKS = '### 長期任務與未定時間項目'
SEC_REMINDERS = '### 長期週期性提醒'
SEC_SCHEDULE = '### 重要行程'
SEC_SHOPPING = '### 採購清單'
SEC_WEEKLY = '## 每週記錄'

KNOWN_SECTIONS = {SEC_TASKS, SEC_REMINDERS, SEC_SCHEDULE, SEC_SHOPPING}

# ── 解析用 regex ──
RE_H1 = re.compile(r'^#\s')
RE_H3 = re.compile(r'^###\s')
RE_H4 = re.compile(r'^####\s')
RE_H5 = re.compile(r'^#####\s')
RE_WEEK = re.compile(r'^####\s+(\d{1,2})/(\d{1,2})\s+至\s+(\d{1,2})/(\d{1,2})')
RE_DAY = re.compile(r'^#####\s+(\d{1,2})/(\d{1,2})')
RE_YEAR = re.compile(r'^#\s+(\d{4})\s*年')
RE_TAG = re.compile(r'\(([^)]+)\)')  # 括號標籤


def parse_year_from_preamble(lines: list[str]) -> int:
    for line in lines:
        m = RE_YEAR.match(line)
        if m:
            return int(m.group(1))
    return 2026  # fallback


def is_bullet(line: str) -> bool:
    """判斷一行是否為 bulletnote 條目"""
    stripped = line.strip()
    if not stripped:
        return False
    # @@ 筆記格式
    if stripped.startswith('@@'):
        return True
    # ok 是舊格式完成標記（支援 ok✅ 複合符號）
    if stripped.startswith('ok'):
        return True
    # ● ok 格式（任務符號 + ok）
    if len(stripped) >= 4 and stripped[0] in '●★' and stripped[1:].lstrip().startswith('ok'):
        return True
    if stripped[0] in LINE_SYMBOLS:
        return True
    return False


def parse_bullet(line: str, line_no: int) -> BulletItem | None:
    """解析一行 bulletnote 條目"""
    stripped = line.strip()
    if not stripped:
        return None
    # @@ 筆記格式
    if stripped.startswith('@@'):
        text = stripped[2:].strip()
        return BulletItem(
            line_no=line_no, raw=line,
            symbol='@@', text=text,
        )
    # ok 是舊格式完成標記
    if stripped.startswith('ok'):
        # 支援 ok（ok 完成事項）和 ok✅（採購清單已完成）
        prefix_len = 3 if stripped.startswith('ok✅') else 3 if stripped.startswith('ok ') else 2
        text = stripped[prefix_len:].strip()
        return BulletItem(
            line_no=line_no, raw=line,
            symbol='ok', text=text, is_done=True,
            tag=_extract_tag(text),
        )
    # ● ok 新格式（任務符號 + ok）
    if len(stripped) >= 4 and stripped[0] in '●★' and stripped[1:].lstrip().startswith('ok'):
        sym = stripped[0]
        text = stripped[1:].lstrip()
        # 去掉開頭的 ok（含後面的空白）
        if text.startswith('ok '):
            text = text[3:].strip()
        elif text == 'ok':
            text = ''
        else:
            text = text[2:].lstrip()  # 'ok✅' 等
        return BulletItem(
            line_no=line_no, raw=line,
            symbol=sym, text=text, is_done=True,
            tag=_extract_tag(text),
        )
    ch = stripped[0]
    if ch in LINE_SYMBOLS:
        text = stripped[1:].strip()
        # 舊格式 ● ✅ → 標記為完成
        done = text.startswith('✅') or text.startswith('ok')
        # ✅ 在開頭則去除
        if text.startswith('✅'):
            text = text[1:].strip()
        return BulletItem(
            line_no=line_no, raw=line,
            symbol=ch, text=text, is_done=done,
            tag=_extract_tag(text),
        )
    return None


def _extract_tag(text: str) -> str:
    m = RE_TAG.search(text)
    return m.group(1) if m else ''


def section_keyword(header: str) -> str | None:
    """從 ### header 識別區塊類型（模糊匹配，允許 emoji）"""
    h = header.rstrip()
    if '長期任務' in h or '未定時間' in h:
        return 'tasks'
    if '長期週期' in h or '週期性' in h:
        return 'reminders'
    if '重要行程' in h:
        return 'schedule'
    if '採購清單' in h or '採購' in h:
        return 'shopping'
    return None


class Parser:
    """逐行狀態機解析器"""

    def __init__(self):
        self.doc = Document()
        self.lines: list[str] = []
        self.anomalies: list[str] = []

    def parse(self, text: str) -> Document:
        self.lines = text.split('\n')
        self.doc = Document()
        self.anomalies = []

        state = 'preamble'
        current_section: Section | None = None
        current_week: WeekHeader | None = None
        current_day: DayEntry | None = None
        section_buf: list[str] = []

        def finish_day(day: DayEntry):
            if current_week is not None:
                current_week.days.append(day)

        def finish_week(week: WeekHeader):
            if current_day is not None:
                finish_day(current_day)
            self.doc.weeks.append(week)

        for i, line in enumerate(self.lines):
            stripped = line.rstrip()

            # ── 檔頭年份 ──
            m_year = RE_YEAR.match(stripped)
            if m_year:
                self.doc.year = int(m_year.group(1))

            # ── 每週記錄結界 ──
            if stripped == SEC_WEEKLY:
                if current_section and section_buf:
                    self._finish_section(current_section, section_buf)
                    section_buf = []
                current_section = None
                state = 'weekly'
                continue

            # ── ### 區塊 ──
            if RE_H3.match(stripped):
                kw = section_keyword(stripped)
                if kw:
                    # 完成前一個 section
                    if current_section and section_buf:
                        self._finish_section(current_section, section_buf)
                        section_buf = []
                    current_section = Section(line_no=i, header=stripped)
                    setattr(self.doc, f'{kw}_section', current_section)
                    if kw not in self.doc.section_order:
                        self.doc.section_order.append(kw)
                    state = 'section'
                    continue

            # ── #### 週 header ──
            if RE_H4.match(stripped):
                m = RE_WEEK.match(stripped)
                if m:
                    if current_week and current_day:
                        finish_day(current_day)
                        current_day = None
                    if current_week:
                        finish_week(current_week)
                    current_week = WeekHeader(
                        line_no=i, header=stripped, year=self.doc.year,
                        month_start=int(m.group(1)), day_start=int(m.group(2)),
                        month_end=int(m.group(3)), day_end=int(m.group(4)),
                    )
                    state = 'week'
                    continue
                else:
                    # 可能是殘留的 #### 06/19（週五）單日格式
                    self.anomalies.append(f"非標準週格式: line {i+1} - {stripped}")
                    state = 'week'
                    continue

            # ── ##### 日 header ──
            if RE_H5.match(stripped):
                m = RE_DAY.match(stripped)
                if m and current_week is not None:
                    if current_day:
                        finish_day(current_day)
                    current_day = DayEntry(line_no=i, header=stripped)
                    state = 'day'
                    continue

            # ── 根據 state 處理內容行 ──
            if state == 'preamble':
                self.doc.preamble.append(line)

            elif state == 'section':
                if current_section:
                    if is_bullet(stripped):
                        item = parse_bullet(stripped, i)
                        if item:
                            current_section.items.append(item)
                    section_buf.append(line)

            elif state == 'week':
                if current_week:
                    if is_bullet(stripped):
                        item = parse_bullet(stripped, i)
                        if item:
                            current_week.bullets.append(item)

            elif state == 'day':
                if current_day:
                    if is_bullet(stripped):
                        item = parse_bullet(stripped, i)
                        if item:
                            current_day.bullets.append(item)
                    current_day.raw_lines.append(line)

        # ── 結束時 flush ──
        if current_section and section_buf:
            self._finish_section(current_section, section_buf)
        if current_day:
            finish_day(current_day)
        if current_week:
            finish_week(current_week)

        # 記錄行數
        self.doc.path = getattr(self.doc, 'path', '')

        # 偵測週記錄中的非標準內容
        self._detect_weekly_nonstandard()

        return self.doc

    def _detect_weekly_nonstandard(self):
        """掃描週記錄區塊，找出非標準格式的內容並記錄為 anomaly"""
        in_weekly = False
        for i, line in enumerate(self.lines):
            stripped = line.rstrip()
            if stripped == SEC_WEEKLY:
                in_weekly = True
                continue
            if not in_weekly:
                continue
            # 跳過 ## 每週記錄之後的標準內容
            # #### header
            if RE_H4.match(stripped):
                if not RE_WEEK.match(stripped):
                    self.anomalies.append(f"非標準週格式: L{i+1} - {stripped}")
                continue
            # ##### day header
            if RE_H5.match(stripped):
                # 標準格式：##### MM/DD（週X）
                # day 格式檢查
                if not RE_DAY.match(stripped):
                    self.anomalies.append(f"非標準日標題: L{i+1} - {stripped}")
                continue
            # 非標準自由文字（僅抓明顯的格式違規）
            if stripped and not is_bullet(stripped):
                if RE_H3.match(stripped):
                    self.anomalies.append(f"週記錄中的 ###: L{i+1} - {stripped}")
                elif '# ' in stripped and '年' not in stripped:
                    self.anomalies.append(f"週記錄中非標準標題: L{i+1} - {stripped}")

        return self.doc

    def _finish_section(self, section: Section, buf: list[str]):
        section.raw_lines = buf

    def parse_file(self, path: str) -> Document:
        text = Path(path).read_text(encoding='utf-8')
        return self.parse(text)
