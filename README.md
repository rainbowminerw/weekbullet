# weekbullet — 週記 CLI 管理工具

以 bulletnote 格式管理 Obsidian 週記檔案的命令列工具。

```
wb view status           # 週記狀態總覽
wb add task "內容"       # 新增長期任務
wb edit task 3 "新內容"  # 修改第3條
wb delete shopping 2     # 刪除採購第2條
wb init --year 2027      # 建立新年週記
wb maintain fix          # 自動修復結構問題
```

## 功能

### 瀏覽 (`view`)

| 指令 | 說明 |
|------|------|
| `view tasks` | 長期任務 |
| `view reminders` | 週期提醒 |
| `view schedule` | 重要行程 |
| `view shopping` | 採購清單 |
| `view week [範圍]` | 週記錄（本週 / YYYY-MM / 區間） |
| `view date YYYY-MM-DD` | 單日 all_day 彙整 |
| `view status` | 整份狀態總覽 |

### 編輯 (`add` / `edit` / `delete`)

每項修改前自動 **zip 壓縮備份**，異常時自動回滾。

```
add task "內容" [-s ●]
add entry "內容" -d YYYY-MM-DD
edit task 3 "新內容"
edit entry 2026-07-07 1 "新內容"
delete shopping 5
```

支援區塊：`task`、`reminder`、`schedule`、`shopping`、`entry`（日條目）、`week`（週區塊）。

### 維護 (`maintain`)

```
maintain scan     # 掃描結構問題（唯讀）
maintain fix      # 自動修復（含備份）
```

可偵測：空週區塊、重複日期、遺漏 bullet 符號、格式不一致。

### 初始化 (`init`)

```
init --year 2027   # 建立新年週記，拷貝特別要求區塊
```

## 安裝

```bash
# 放置到週記目錄旁
# 例如：日誌/weekbullet/

cd 日誌/weekbullet/
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

## 檔案格式

檔案為 `bulletnote` 格式的 Markdown：

```
### 長期任務與未定時間項目
● 待辦事項
● ✅ 已完成事項

## 每週記錄

#### 06/29 至 07/05
##### 06/29（週一）
● 日記事項
－ 筆記
```

支援符號：`●` 任務、`★` 重要、`○` 活動、`●?` 待確認、`● ok` 完成、`Ｘ` 取消、`＞` 轉移、`△` 待訂、`@@` 筆記、`✅` 子項目。

## 依賴

- Python ≥ 3.10
- [click](https://click.palletsprojects.com/) — CLI 框架（pip 自動安裝）

## 授權

MIT
