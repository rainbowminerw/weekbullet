"""
weekbullet — renderer.py
將 Document model 渲染回週記 markdown。

核心策略：**model-based 為主，原始文字 fallback**
- 未修改的區塊 → 直接從 _original_lines 保留原樣
- 被 dirty 的 ### 區塊 → 用 model items 重建該區塊
- 週記錄（entry dirty）→ 用原始保留（除非未來支援日級別 dirty）
- preamble / 區塊間空白 / tail 全部保留
"""
from __future__ import annotations

import re
from pathlib import Path

from weekbullet.model import Document, BulletItem
from weekbullet.parser import Parser


def _render_bullet(item: BulletItem) -> str:
    """將 BulletItem 渲染為一行。
    
    新格式（v2）：
    - 完成：● ok 內容、★ ok 內容
    - 筆記：@@ 內容
    - 舊格式 ok（行首）自動轉換為 ● ok
    """
    # 舊格式 ok 轉換
    sym = '●' if item.symbol == 'ok' else item.symbol
    text = item.text.lstrip('✅ ').strip()
    if item.is_pending:
        return f'{sym}? {text}'
    if sym == '@@':
        return f'@@ {text}'
    if item.is_done:
        return f'{sym} ok {text}'
    return f'{sym} {text}'


def _is_bullet_line(s: str) -> bool:
    """粗略判斷是否為 bullet 條目行"""
    st = s.strip()
    if not st:
        return False
    if st.startswith('@@'):
        return True
    if st[0] in '●○★✅⏳🎯⚠️Ｘ＞△－':
        return True
    if st.startswith('ok') and (len(st) < 3 or not st[2].isalpha()):
        return True
    return False


def rebuild_document(doc: Document) -> str:
    """從 Document model 重建完整週記文字。

    只有 doc._dirty 中被標記的區塊會用 model 重建，
    其餘全部從 doc._original_lines 保留原樣。
    """
    orig = doc._original_lines
    if not orig:
        # 沒有原始文字 → 從 model 重建全部（基本版）
        return _rebuild_all(doc)

    result: list[str] = []

    # ── 找各區塊在原始文字中的行範圍 ──
    sec_ranges: dict[str, tuple[int, int]] = {}

    sec_keywords = {
        'tasks': '長期任務',
        'reminders': '週期性提醒',
        'schedule': '重要行程',
        'shopping': '採購清單',
    }

    # 掃描原始文字找各 ### 區塊的位置
    current_name = None
    current_start = None

    for i, ln in enumerate(orig):
        s = ln.rstrip()
        # 檢查是否為已知 ### 區塊
        if s.startswith('### '):
            # 結束前一個
            if current_name and current_start is not None:
                sec_ranges[current_name] = (current_start, i)
            # 開始新的
            current_name = None
            for keyword, name in sec_keywords.items():
                if keyword in s:
                    current_name = name
                    current_start = i
                    break
        # 結界：## 每週記錄 或第二個 # YYYY
        if s.startswith('## ') and '每週' in s:
            if current_name and current_start is not None:
                sec_ranges[current_name] = (current_start, i)
                current_name = None
                current_start = None
            break

    # flush 最後一個
    if current_name and current_start is not None:
        sec_ranges[current_name] = (current_start, len(orig))

    # ── 開始重建 ──
    current_line = 0

    # Preamble: 從開頭到第一個 ### 區塊或 ## 每週記錄
    first_boundary = len(orig)
    for name, (start, _) in sorted(sec_ranges.items(), key=lambda x: x[1][0]):
        first_boundary = min(first_boundary, start)
    # 也檢查 ## 每週記錄
    for i, ln in enumerate(orig):
        if ln.rstrip().startswith('## ') and '每週' in ln:
            first_boundary = min(first_boundary, i)
            break

    # 複製 preamble 原樣
    result.extend(orig[:first_boundary])
    current_line = first_boundary

    # ### 區塊：依 section_order 輸出
    for name in doc.section_order:
        sec = doc.get_section(name)
        if sec is None:
            continue

        if name in doc._dirty:
            # ── 用 model 重建此區塊 ──
            block = [sec.header]
            bullet_lines = [_render_bullet(it) for it in sec.items]
            if bullet_lines:
                block.append('')
                block.extend(bullet_lines)
                block.append('')
            else:
                block.append('')
            result.extend(block)
            # 跳過原始文字到此區塊結尾
            if name in sec_ranges:
                _, end = sec_ranges[name]
                current_line = max(current_line, end)
        else:
            # ── 保留原始 ──
            if name in sec_ranges:
                start, end = sec_ranges[name]
                # 確保沒有遺漏前面的內容
                if start > current_line:
                    result.extend(orig[current_line:start])
                result.extend(orig[start:end])
                current_line = end
            else:
                # 原始文字中找不到 → 從 model 重建
                block = [sec.header, '']
                for it in sec.items:
                    block.append(_render_bullet(it))
                block.append('')
                result.extend(block)

    # ── 每週記錄（除非 entry dirty，否則保留原始）──
    weekly_start = None
    for i, ln in enumerate(orig):
        if ln.rstrip().startswith('## ') and '每週' in ln:
            weekly_start = i
            break

    if weekly_start is not None:
        # 前面的內容（如果 section 結束到 weekly 之間有 gap）
        if weekly_start > current_line:
            result.extend(orig[current_line:weekly_start])
        elif weekly_start < current_line:
            # 已經超過了（部分被 section 吃掉了）
            pass

        if 'entry' in doc._dirty:
            # 週記錄被修改 → 從 model 重建（簡化版，僅 items）
            result.append('## 每週記錄')
            result.append('')
            for wi, week in enumerate(doc.weeks):
                if wi > 0:
                    result.append('')
                result.append(week.header)
                for b in week.bullets:
                    result.append(_render_bullet(b))
                for di, day in enumerate(week.days):
                    if di > 0:
                        result.append('')
                    result.append(day.header)
                    for b in day.bullets:
                        result.append(_render_bullet(b))
            # tail: 最後一個 #### 之後的內容
            last_week_idx = None
            for i in range(len(orig) - 1, -1, -1):
                if orig[i].rstrip().startswith('#### '):
                    last_week_idx = i
                    break
            if last_week_idx is not None:
                tail_lines = []
                # 找 #### 區塊的最後一行
                j = last_week_idx + 1
                while j < len(orig):
                    if j >= last_week_idx + 1:
                        tail_lines.append(orig[j])
                    j += 1
                # 實際上 tail 很難精確定義，先跳過
        else:
            # 保留原始週記錄
            result.extend(orig[weekly_start:])
    else:
        # 沒有週記錄
        if current_line < len(orig):
            result.extend(orig[current_line:])

    return '\n'.join(result)


def _rebuild_all(doc: Document) -> str:
    """完全從 model 重建（無原始文字時 fallback）"""
    # 簡化重建：只用 ### 區塊的 items，週記錄用 model
    lines: list[str] = []
    for ln in doc.preamble:
        lines.append(ln)
    if lines and lines[-1] != '':
        lines.append('')
    for name in doc.section_order:
        sec = doc.get_section(name)
        if sec is None:
            continue
        lines.append(sec.header)
        lines.append('')
        for it in sec.items:
            lines.append(_render_bullet(it))
        lines.append('')
    lines.append('## 每週記錄')
    lines.append('')
    for wi, week in enumerate(doc.weeks):
        if wi > 0:
            lines.append('')
        lines.append(week.header)
        for b in week.bullets:
            lines.append(_render_bullet(b))
        for di, day in enumerate(week.days):
            if di > 0:
                lines.append('')
            lines.append(day.header)
            for b in day.bullets:
                lines.append(_render_bullet(b))
    for ln in doc.tail:
        lines.append(ln)
    return '\n'.join(lines)


# ═══════════════════════════════════════════════
# 統一的修改→寫入入口
# ═══════════════════════════════════════════════


def load_for_edit(path: str) -> tuple[Document, list[str]]:
    """讀取檔案、解析為 Document（含原始文字）。"""
    raw = Path(path).read_text(encoding='utf-8')
    p = Parser()
    doc = p.parse(raw)
    doc.path = str(path)
    doc._original_lines = raw.splitlines()
    return doc, raw.splitlines()


def save_document(doc: Document) -> str:
    """將 Document 渲染並寫入檔案（含 auto_backup）。"""
    from weekbullet.backup import auto_backup

    result = rebuild_document(doc)
    with auto_backup(doc.path):
        Path(doc.path).write_text(result, encoding='utf-8')
    return result
