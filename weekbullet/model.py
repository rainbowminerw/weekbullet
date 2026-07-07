"""
weekbullet — model.py
資料模型：Document → Section → BulletItem | WeekHeader | DayEntry
"""

from dataclasses import dataclass, field
from typing import Optional

# ── bulletnote 符號語意表 ──
SYMBOL_OPEN = '●'       # 未定任務
SYMBOL_MAYBE = '○'      # 活動/待確認
SYMBOL_STAR = '★'       # 重要優先
SYMBOL_DONE_OK = 'ok'   # 已完成（字首）
SYMBOL_DONE_CHECK = '✅'  # 已完成（內嵌）
SYMBOL_PROGRESS = '⏳'   # 進行中
SYMBOL_GOAL = '🎯'      # 目標
SYMBOL_WARN = '⚠️'       # 注意
SYMBOL_CANCEL = 'Ｘ'    # 取消
SYMBOL_TRANSFER = '＞'  # 轉移
SYMBOL_TBD = '△'        # 改期待訂
SYMBOL_NOTE = '－'      # 筆記

LINE_SYMBOLS = {SYMBOL_OPEN, SYMBOL_MAYBE, SYMBOL_STAR, SYMBOL_DONE_CHECK,
                SYMBOL_PROGRESS, SYMBOL_GOAL, SYMBOL_WARN, SYMBOL_CANCEL,
                SYMBOL_TRANSFER, SYMBOL_TBD, SYMBOL_NOTE}


@dataclass
class BulletItem:
    """一個 bulletnote 條目"""
    line_no: int            # 原始行號
    raw: str                # 原始行內容
    symbol: str             # bulletnote 符號（如 ●、ok）
    text: str               # 符號後的文字內容
    is_done: bool = False   # 是否已完成（ok 或含 ✅）
    tag: str = ''           # 括號標籤如 (未定)、(聚餐)

    @property
    def display_symbol(self) -> str:
        return 'ok' if self.is_done else self.symbol


@dataclass
class DayEntry:
    """一個 ##### 日期條目"""
    line_no: int
    header: str             # 如 ##### 07/07（週二）
    bullets: list[BulletItem] = field(default_factory=list)
    raw_lines: list[str] = field(default_factory=list)  # 含 header 的完整原始行


@dataclass
class WeekHeader:
    """一個 #### 週 header"""
    line_no: int
    header: str             # 如 #### 07/06 至 07/12
    year: int               # 從檔案的 # YYYY 年 推斷
    month_start: int        # 起始月份
    day_start: int          # 起始日期
    month_end: int          # 結束月份
    day_end: int            # 結束日期
    days: list[DayEntry] = field(default_factory=list)
    bullets: list[BulletItem] = field(default_factory=list)  # 週層級的筆記


@dataclass
class Section:
    """一個 ### 區塊（如長期任務、採購清單等）"""
    line_no: int
    header: str
    items: list[BulletItem] = field(default_factory=list)
    raw_lines: list[str] = field(default_factory=list)  # 完整原始行


@dataclass
class Document:
    """整份週記文件"""
    path: str = ''
    year: int = 0
    # 頂層區塊
    long_term_tasks: Section | None = None       # ### 長期任務與未定時間項目
    periodic_reminders: Section | None = None     # ### 長期週期性提醒
    important_schedule: Section | None = None     # ### 重要行程
    shopping_list: Section | None = None          # ### 採購清單
    # 每週記錄
    weeks: list[WeekHeader] = field(default_factory=list)
    # 未歸類的原始行（保留用）
    preamble: list[str] = field(default_factory=list)
    tail: list[str] = field(default_factory=list)
    # 區塊出現順序（『tasks』『reminders』『schedule』『shopping』）
    section_order: list[str] = field(default_factory=list)
    # ── render 輔助欄位（renderer fallback 用）──
    # 原始文字行（寫入時用作基底，未修改區塊保留原樣）
    _original_lines: list[str] = field(default_factory=list)
    # 已被修改的區塊名稱 set（『tasks』『reminders』『schedule』『shopping』『entry』）
    _dirty: set[str] = field(default_factory=set)

    def get_section(self, name: str) -> Section | None:
        attr = f'{name}_section'
        return getattr(self, attr, None)
