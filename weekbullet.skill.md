---
name: weekbullet
description: 週記 CLI 管理工具 — bulletnote 格式的 Obsidian 週記檔案操作
category: productivity
triggers:
  - weekbullet
  - wb
  - 週記
  - 週記 cli
---

# weekbullet — 週記 CLI 管理工具

以 bulletnote 格式管理 Obsidian 週記檔案的命令列工具。

## 位置

套件放在週記目錄的同層 `weekbullet/` 目錄下，透過 `__file__` 自動定位。

```tree
日誌/
├── 2026 年週記.md
├── .gitignore
├── README.md
├── pyproject.toml
├── venv/
├── weekbullet/
│   ├── __init__.py
│   ├── backup.py     — zip 壓縮備份與回滾
│   ├── cli.py        — Click CLI（view/add/edit/delete/init/maintain）
│   ├── editor.py     — model-based 編輯操作（add/edit/delete items）
│   ├── formatter.py  — 終端輸出格式化
│   ├── init.py       — 新年週記初始化
│   ├── maintain.py   — 結構掃描與修復
│   ├── model.py      — 資料模型（Document/Section/BulletItem/WeekHeader/DayEntry）
│   ├── parser.py     — 逐行狀態機解析器
│   └── renderer.py   — model→文字，含原文 fallback
```

## CLI 指令

### 瀏覽（view）

```bash
wb view tasks              # 長期任務
wb view reminders          # 週期提醒
wb view schedule           # 重要行程
wb view shopping           # 採購清單
wb view week               # 本週記錄
wb view week 2026-07       # 指定月份
wb view week 06/29~07/05   # 指定日期區間
wb view date 2026-07-07    # 單日 all_day 彙整
wb view status             # 整份狀態總覽
```

### 編輯（add / edit / delete）

```bash
wb add task "內容"                     # 新增長期任務
wb add reminder "內容"                 # 新增週期提醒
wb add schedule "內容"                 # 新增重要行程
wb add shopping "內容"                 # 新增採購項目
wb add entry "內容" -d 2026-07-07      # 新增日條目
wb add week --start 07/07              # 新增週區塊

wb edit task 3 "新內容"                # 修改第3條任務
wb edit entry 2026-07-07 1 "新內容"    # 修改日條目
wb edit shopping 5 --symbol ✅         # 修改符號

wb delete task 3                       # 刪除第3條任務
wb delete entry 2026-07-07 1           # 刪除日條目

# 預覽模式（不實際寫入）
wb add --dry-run task "內容"
wb edit --dry-run task 3 "新內容"
wb delete --dry-run task 3
```

每項修改前自動 zip 壓縮備份，異常時自動回滾。備份保留最近 10 份。

### 維護

```bash
wb maintain scan    # 掃描結構問題
wb maintain fix     # 自動修復（含備份）
```

可偵測：空週區塊、重複日期、遺漏 bullet 符號、非標準格式。

### 初始化

```bash
wb init --year 2027     # 建立新年週記（拷貝特別要求區塊）
wb -y 2027 view status  # 查看指定年份
```

## 檔案格式（bulletnote）

```markdown
# 2026 年週記

### 長期任務與未定時間項目
● 待辦事項
● ✅ 已完成事項

### 📅 長期週期性提醒
○ 每週提醒

### 重要行程
● 行程1

### 採購清單
● 待買
ok✅ 已買

## 每週記錄

#### 06/29 至 07/05
##### 06/29（週一）
● 日記事項
－ 筆記
##### 06/30（週二）
★ 重要事項
```

符號表：`●` 未完成、`● ✅` 已完成、`★` 重要、`○` 待確認、`⏳` 進行中、`🎯` 目標、`⚠️` 注意、`Ｘ` 取消、`＞` 轉移、`△` 待定、`－` 筆記、`ok✅` 結案。

排序規則：週與週 newest first、週內天數 newest first、任務未完成 > 已排程 > 已完成。

## 安裝

```bash
# 放置到週記目錄旁
cd 日誌/weekbullet/
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

依賴：Python ≥ 3.10、click。

## 注意事項

- 路徑自動偵測：使用 `__file__` 相對定位，整包搬到任何位置都能用
- 跨年支援：`--year` 或自動偵測當前年份
- MIT 授權
