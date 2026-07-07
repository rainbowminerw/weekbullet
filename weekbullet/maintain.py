"""
weekbullet — maintain.py
掃描週記 md 檔案的常見格式問題，並提供自動修復能力。
"""
import re
from pathlib import Path

# ── regex ──
RE_H3 = re.compile(r'^###\s')
RE_H4 = re.compile(r'^####\s')
RE_H5 = re.compile(r'^#####\s')
RE_H2 = re.compile(r'^##\s')
RE_WEEK = re.compile(r'^####\s+\d{1,2}/\d{1,2}\s+至\s+\d{1,2}/\d{1,2}')
RE_DAY_HEADER = re.compile(r'^#####\s+\d{1,2}/\d{1,2}')
RE_DATE = re.compile(r'\d{1,2}/\d{1,2}')
# 以 #### 開頭、含（週 → 疑似誤用 #### 代替 #####
RE_WRONG_DAY_HEADER = re.compile(r'^####\s+\d{1,2}/\d{1,2}（週')
RE_WIKI_LINK = re.compile(r'^\[\[.+\]\]')               # obsidian wiki link
RE_HR_OR_BLANK = re.compile(r'^[-=*_]{3,}\s*$')         # 各種水平線

# ── 已知 bullet 符號（與 model.py LINE_SYMBOLS + 'ok' 一致）──
KNOWN_BULLET = {'●', '○', '★', '✅', '⏳', '🎯', '⚠️', 'Ｘ', '＞', '△', '－'}

# ── 區塊關鍵字（模糊比對，允許 emoji 前綴）──
KNOWN_SECTION_CONTAINS = [
    '長期任務', '未定時間',
    '重要行程',
    '採購清單',
    '長期週期', '週期性',
]


def _is_known_section_header(line: str) -> bool:
    """fuzzy match：### 開頭的已知區塊"""
    h = line.rstrip()
    for kw in KNOWN_SECTION_CONTAINS:
        if kw in h:
            return True
    return False


def _is_bullet_prefix(line: str) -> bool:
    """是否為已知 bullet 開頭（含 ok 字首）"""
    s = line.lstrip()
    if not s:
        return False
    if s.startswith('ok'):
        return True
    return s[0] in KNOWN_BULLET


def _is_md_structure(line: str) -> bool:
    """是否為 Markdown 結構元素（非 bulletnote 內容）"""
    s = line.strip()
    if not s:
        return False
    if RE_HR_OR_BLANK.match(s):
        return True
    if RE_WIKI_LINK.match(s):
        return True
    return False


def _extract_day(line: str) -> str | None:
    """從 ##### MM/DD 擷取 MM/DD"""
    m = RE_DATE.search(line)
    return m.group(0) if m else None


# ═══════════════════════════════════════════════

class JournalMaintainer:
    """掃描並修復週記 md 檔案的格式問題"""

    def __init__(self, filepath: str):
        self.filepath = filepath
        raw = Path(filepath).read_text(encoding='utf-8')
        self.lines = raw.split('\n')

    # ── 掃描 ──

    def scan(self) -> list[dict]:
        """掃描並回報所有可自動修復的問題"""
        issues: list[dict] = []
        issues.extend(self._scan_day_header_format())
        issues.extend(self._scan_empty_week())
        issues.extend(self._scan_missing_bullet())
        issues.extend(self._scan_duplicate_day())
        return issues

    # ── 掃描 1：day_header_format ──

    def _scan_day_header_format(self) -> list[dict]:
        """#### 06/19（週五）→ 應為 ##### 06/19（週五）"""
        results = []
        for i, line in enumerate(self.lines):
            if RE_WRONG_DAY_HEADER.match(line):
                # 再確認不含「至」（排除 week header）
                if '至' not in line:
                    date_str = RE_DATE.search(line)
                    dd = date_str.group(0) if date_str else '??/??'
                    results.append({
                        'type': 'day_header_format',
                        'line': i,
                        'desc': f'#### {dd}（週X）→ 應為 #####',
                        'fixable': True,
                    })
        return results

    # ── 掃描 2：empty_week ──

    def _scan_empty_week(self) -> list[dict]:
        """#### XX/XX 至 XX/XX 之後無任何 ##### day header"""
        results = []
        weekly_start = None
        for i, line in enumerate(self.lines):
            if line.rstrip() == '## 每週記錄':
                weekly_start = i
                break
        if weekly_start is None:
            return results

        # 找出所有 week header 的 line no（在 weekly 區內）
        week_header_lines = []
        for i in range(weekly_start + 1, len(self.lines)):
            if RE_WEEK.match(self.lines[i]):
                week_header_lines.append(i)

        # 對每個 week，檢查之間有無 ##### day header
        for idx, wh_line in enumerate(week_header_lines):
            next_wh = (
                week_header_lines[idx + 1]
                if idx + 1 < len(week_header_lines)
                else len(self.lines)
            )
            has_day = False
            for scan_i in range(wh_line + 1, next_wh):
                if RE_DAY_HEADER.match(self.lines[scan_i]):
                    has_day = True
                    break
            if not has_day:
                line_text = self.lines[wh_line].strip()
                results.append({
                    'type': 'empty_week',
                    'line': wh_line,
                    'desc': f'空週：{line_text}',
                    'fixable': True,
                })
        return results

    # ── 掃描 3：missing_bullet ──

    def _scan_missing_bullet(self) -> list[dict]:
        """在已知區塊內，非空行非 header 且無 bullet 前綴的行"""
        results = []
        in_known_section = False

        for i, line in enumerate(self.lines):
            stripped = line.rstrip()

            # ## 邊界 → 離開已知區塊
            if RE_H2.match(stripped):
                in_known_section = False
                continue

            # ### 邊界
            if RE_H3.match(stripped):
                in_known_section = _is_known_section_header(stripped)
                continue

            if not in_known_section:
                continue

            if not stripped:
                continue
            if RE_H4.match(stripped) or RE_H5.match(stripped):
                continue
            if _is_bullet_prefix(stripped):
                continue
            if _is_md_structure(stripped):
                continue

            clip = stripped[:60]
            results.append({
                'type': 'missing_bullet',
                'line': i,
                'desc': f'缺少 bullet：{clip}',
                'fixable': True,
            })

        return results

    # ── 掃描 4：duplicate_day ──

    def _scan_duplicate_day(self) -> list[dict]:
        """同一 date（MM/DD）出現超過一次 ##### header"""
        date_lines: dict[str, list[int]] = {}
        for i, line in enumerate(self.lines):
            m = RE_DAY_HEADER.match(line)
            if m:
                dd = _extract_day(line)
                if dd:
                    date_lines.setdefault(dd, []).append(i)

        results = []
        for dd, lines in date_lines.items():
            if len(lines) > 1:
                results.append({
                    'type': 'duplicate_day',
                    'line': lines[0],
                    'desc': f'重複日期：{dd} 出現 {len(lines)} 次',
                    'fixable': False,
                })
        return results

    # ── 掃描 5：duplicate_section ──

    def _scan_duplicate_section(self) -> list[dict]:
        """偵測 ### 區塊重複出現（去重前掃描）"""
        results = []
        seen: dict[str, int] = {}  # section name → first line

        for i, line in enumerate(self.lines):
            if not RE_H3.match(line):
                continue
            for kw in KNOWN_SECTION_CONTAINS:
                if kw in line:
                    name = kw
                    if name in seen:
                        results.append({
                            'type': 'duplicate_section',
                            'line': i,
                            'desc': f'重複區塊：{line.strip()}（首次於 L{seen[name]+1}）',
                            'fixable': True,
                        })
                    else:
                        seen[name] = i
                    break
        return results

    def scan(self) -> list[dict]:
        """掃描並回報所有可自動修復的問題"""
        issues: list[dict] = []
        issues.extend(self._scan_day_header_format())
        issues.extend(self._scan_empty_week())
        issues.extend(self._scan_missing_bullet())
        issues.extend(self._scan_duplicate_day())
        issues.extend(self._scan_duplicate_section())
        return issues

    # ── 深度修復：去重複 + 排序 ——

    def fix_structure(self) -> list[dict]:
        """進階修復：使用 parser→renderer 全重建。
        
        處理項目：
        - 去掉重複的 ### 區塊（只保留第一組）
        - 區塊內項目依各區塊規則排序
        - 每週記錄依 newest first 排序
        - 週內日依 newest first 排序
        - 保留 preamble（特別要求區塊）和 tail
        """
        from weekbullet.backup import auto_backup
        from weekbullet.parser import Parser
        from weekbullet.renderer import _rebuild_all

        # 用 parser 解析（內部已 auto-sort）
        p = Parser()
        text = Path(self.filepath).read_text(encoding='utf-8')
        doc = p.parse(text)

        # 全重建（跳過 line-based fallback）
        result = _rebuild_all(doc)

        # 備份 + 寫入
        changes = []
        with auto_backup(self.filepath):
            Path(self.filepath).write_text(result, encoding='utf-8')

        changes.append({
            'type': 'fix_structure',
            'line': 0,
            'old': f'原始 {len(self.lines)} 行',
            'new': f'重建後 {result.count(chr(10)) + 1} 行',
        })
        if p.anomalies:
            for a in p.anomalies[:5]:
                changes.append({'type': 'anomaly_note', 'line': 0, 'old': '', 'new': a})
        return changes

    # ── 修復 ──

    def fix(self) -> list[dict]:
        """執行所有 fixable=True 的修復，回報變更清單"""
        from weekbullet.backup import auto_backup

        issues = self.scan()
        fixable = [i for i in issues if i['fixable']]

        if not fixable:
            return []

        # 用 auto_backup 包裹：備份 + 異常自動回滾
        with auto_backup(self.filepath):
            # 1. 從尾端往頭端修（避免 line number shift）
            fixable.sort(key=lambda x: x['line'], reverse=True)

            lines = self.lines[:]
            changes = []

            for issue in fixable:
                ln = issue['line']
                old_line = lines[ln]
                new_line: str | None = None

                if issue['type'] == 'day_header_format':
                    new_line = '#' + old_line
                elif issue['type'] == 'missing_bullet':
                    new_line = '● ' + old_line
                elif issue['type'] == 'empty_week':
                    new_line = ''

                if new_line is not None and new_line != old_line:
                    lines[ln] = new_line
                    changes.append({
                        'type': issue['type'],
                        'line': ln,
                        'old': old_line.rstrip(),
                        'new': new_line.rstrip(),
                    })

            # 3. 寫入
            src = Path(self.filepath)
            src.write_text('\n'.join(lines), encoding='utf-8')
            self.lines = lines

        return changes

    # ── 輔助 ──

    def print_scan(self, issues: list[dict]) -> str:
        """格式化掃描結果為可讀字串"""
        if not issues:
            return '✅ 無發現任何問題'
        lines_out = [f'🔍 發現 {len(issues)} 個問題：']
        for iss in issues:
            fixable = '🔧' if iss['fixable'] else '📋'
            lines_out.append(
                f'  {fixable} L{iss["line"] + 1:>4}  [{iss["type"]}]  {iss["desc"]}'
            )
        return '\n'.join(lines_out)

    def print_fix(self, changes: list[dict]) -> str:
        """格式化修復結果為可讀字串"""
        if not changes:
            return '✅ 無需修復'
        lines_out = [f'🛠️ 已修復 {len(changes)} 項（備份於 .bak）：']
        for ch in changes:
            lines_out.append(
                f'  L{ch["line"] + 1:>4}  [{ch["type"]}]  {ch["old"][:50]} → {ch["new"][:50]}'
            )
        return '\n'.join(lines_out)
