"""
weekbullet — model.py
資料模型：Document → Section → BulletItem | WeekHeader | DayEntry
"""

from dataclasses import dataclass, field
from typing import Optional

# ── bulletnote 符號語意表（v2 簡化版）──
# 核心任務符號（行首）
SYMBOL_TASK = '●'       # 一般任務
SYMBOL_STAR = '★'       # 重要任務
SYMBOL_EVENT = '○'      # 活動/約定

# 完成標記：任務符號 + ok（如 ● ok、★ ok）
# 子項目完成用 ✅

# 狀態符號
SYMBOL_CANCEL = 'Ｘ'    # 取消
SYMBOL_TRANSFER = '＞'  # 轉移（標明轉移至何時）
SYMBOL_TBD = '△'        # 待訂（抄寫至待定清單）
SYMBOL_NOTE = '@@'      # 筆記（重要用 @@★）

# 向後相容（舊格式仍可解析）
SYMBOL_OLD_OK = 'ok'        # 舊格式：行首 ok（轉換為 ● ok）
SYMBOL_OLD_CHECK = '✅'     # 舊格式：行首 ✅（轉換為 ● ok）
SYMBOL_OLD_NOTE = '－'     # 舊格式：－ 筆記
SYMBOL_OLD_PROGRESS = '⏳'  # 舊格式：進行中
SYMBOL_OLD_GOAL = '🎯'     # 舊格式：目標
SYMBOL_OLD_WARN = '⚠️'      # 舊格式：注意

# 行首符號集合（含向後相容）
LINE_SYMBOLS = {SYMBOL_TASK, SYMBOL_STAR, SYMBOL_EVENT,
                SYMBOL_CANCEL, SYMBOL_TRANSFER, SYMBOL_TBD,
                SYMBOL_OLD_CHECK, SYMBOL_OLD_PROGRESS, SYMBOL_OLD_GOAL,
                SYMBOL_OLD_WARN, SYMBOL_OLD_NOTE}

# 筆記符號集合（@@ 和向後相容 －）
NOTE_SYMBOLS = {SYMBOL_NOTE, SYMBOL_OLD_NOTE}


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
        """顯示用符號（完成時顯示 ● ok）"""
        if self.is_done:
            return f'{self.symbol} ok' if self.symbol not in ('ok', '@@') else '● ok'
        return self.symbol if self.symbol != 'ok' else '●'


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
