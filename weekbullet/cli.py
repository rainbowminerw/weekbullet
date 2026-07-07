"""
weekbullet — cli.py
CLI 介面 (click)，提供 view 命令瀏覽週記各區塊。
"""

import sys
from pathlib import Path
from datetime import date as _date, datetime as _datetime

import click

from weekbullet.parser import Parser
from weekbullet.formatter import (
    format_bullet_list, format_week, format_date, format_status
)

# ── 預設週記路徑（自動偵測，支援可遷移性）──
# weekbullet 放在週記目錄下，__file__ 自動定位
# __file__ = .../日常/日誌/weekbullet/weekbullet/cli.py
# 上三層 = .../日常/日誌/
_WB_DIR = Path(__file__).resolve().parent.parent.parent
_DEFAULT_YEAR = _date.today().year


def _default_path(year: int | None = None) -> str:
    """回傳指定年份的週記預設路徑"""
    y = year or _DEFAULT_YEAR
    candidate = _WB_DIR / f'{y} 年週記.md'
    if candidate.exists():
        return str(candidate)
    # fallback: 找目錄中現有的任何週記
    for f in sorted(_WB_DIR.glob('*年週記.md'), reverse=True):
        return str(f)
    return str(candidate)


DEFAULT_PATH = _default_path()


def load_doc(weekfile: str | None) -> tuple:
    """載入並解析週記檔案，回傳 (Parser, Document)"""
    path = Path(weekfile or DEFAULT_PATH)
    if not path.exists():
        click.echo(f"❌ 找不到檔案: {path}", err=True)
        sys.exit(1)
    p = Parser()
    doc = p.parse_file(str(path))
    if p.anomalies:
        click.echo(f"⚠️ 解析異常 {len(p.anomalies)} 條，可用 view status 查看", err=True)
    return p, doc


def get_section(doc, name: str):
    """取得指定名稱的 Section"""
    attr = f'{name}_section'
    sec = getattr(doc, attr, None)
    if sec is None:
        click.echo(f"❌ 找不到「{name}」區塊", err=True)
        sys.exit(1)
    return sec


# ── Click CLI ──

@click.group(invoke_without_command=False)
@click.version_option(version='0.2.0')
@click.option('--year', '-y', type=int, default=None,
              help='年份（預設自動偵測）')
@click.pass_context
def cli(ctx, year):
    """weekbullet — 週記 CLI 管理工具"""
    ctx.ensure_object(dict)
    ctx.obj['year'] = year or _DEFAULT_YEAR
    ctx.obj['file'] = _default_path(year)


@cli.group()
def view():
    """瀏覽週記各區塊內容"""


@view.command()
@click.option('--file', '-f', default=None, help='週記檔案路徑')
@click.option('--all', 'show_all', is_flag=True, help='顯示已完成項目')
def tasks(file, show_all):
    """瀏覽長期任務"""
    _, doc = load_doc(file)
    sec = get_section(doc, 'tasks')
    output = format_bullet_list(sec, show_done=show_all)
    if output:
        click.echo(f"📋 {sec.header}")
        click.echo(output)
    else:
        click.echo("📋 長期任務（無項目）")


@view.command()
@click.option('--file', '-f', default=None)
@click.option('--all', 'show_all', is_flag=True)
def schedule(file, show_all):
    """瀏覽重要行程"""
    _, doc = load_doc(file)
    sec = get_section(doc, 'schedule')
    output = format_bullet_list(sec, show_done=show_all)
    if output:
        click.echo(f"📋 {sec.header}")
        click.echo(output)
    else:
        click.echo("📋 重要行程（無項目）")


@view.command()
@click.option('--file', '-f', default=None)
@click.option('--all', 'show_all', is_flag=True)
def shopping(file, show_all):
    """瀏覽採購清單"""
    _, doc = load_doc(file)
    sec = get_section(doc, 'shopping')
    output = format_bullet_list(sec, show_done=show_all)
    if output:
        click.echo(f"📋 {sec.header}")
        click.echo(output)
    else:
        click.echo("📋 採購清單（無項目）")


@view.command()
@click.option('--file', '-f', default=None)
@click.option('--all', 'show_all', is_flag=True)
def reminders(file, show_all):
    """瀏覽週期性提醒"""
    _, doc = load_doc(file)
    sec = get_section(doc, 'reminders')
    if sec is None:
        click.echo("📋 週期性提醒（無此區塊）")
        return
    output = format_bullet_list(sec, show_done=show_all)
    if output:
        click.echo(f"📋 {sec.header}")
        click.echo(output)
    else:
        click.echo("📋 週期性提醒（無項目）")


@view.command()
@click.argument('range_arg', required=False, default='')
@click.option('--file', '-f', default=None)
@click.option('--max-days', '-n', default=0, type=int, help='每週最多顯示天數')
def week(range_arg, file, max_days):
    """瀏覽週記錄
    
    RANGE_ARG 可為：
    - 空白：本週
    - YYYY-MM：整個月
    - YYYY-MM-DD~YYYY-MM-DD：日期範圍
    """
    _, doc = load_doc(file)
    
    # 解析範圍
    if not range_arg:
        # 本週
        today = _date.today()
        target_weeks = _filter_current_week(doc.weeks, today)
    elif '~' in range_arg:
        parts = range_arg.split('~')
        start = _parse_date(parts[0])
        end = _parse_date(parts[1]) if len(parts) > 1 else start
        target_weeks = _filter_week_range(doc.weeks, start, end)
    elif '-' in range_arg and range_arg.count('-') == 1:
        # YYYY-MM 整個月
        parts = range_arg.split('-')
        y, m = int(parts[0]), int(parts[1])
        target_weeks = _filter_month(doc.weeks, y, m)
    else:
        click.echo("❌ 格式錯誤。用 YYYY-MM-DD~YYYY-MM-DD 或 YYYY-MM", err=True)
        return
    
    if not target_weeks:
        click.echo("📅 該範圍無週記錄")
        return
    
    for w in target_weeks:
        click.echo(format_week(w, max_days))
        click.echo('')


@view.command()
@click.argument('date_arg', required=True)
@click.option('--file', '-f', default=None)
def date(date_arg, file):
    """瀏覽特定日期的 all_day 彙整
    
    DATE_ARG 格式：YYYY-MM-DD
    """
    _, doc = load_doc(file)
    dt = _parse_date(date_arg)
    if dt is None:
        click.echo(f"❌ 日期格式錯誤: {date_arg}（應為 YYYY-MM-DD）", err=True)
        return
    output = format_date(doc, dt.year, dt.month, dt.day)
    click.echo(output)


@view.command()
@click.option('--file', '-f', default=None)
def status(file):
    """整份週記狀態總覽"""
    p, doc = load_doc(file)
    output = format_status(doc)
    click.echo(output)
    if p.anomalies:
        click.echo(f"\n⚠️ 解析異常 {len(p.anomalies)} 條：")
        for a in p.anomalies[:5]:
            click.echo(f"  {a}")


# ── 輔助函數 ──

def _parse_date(text: str):
    """解析 YYYY-MM-DD 為 date"""
    try:
        return _datetime.strptime(text.strip(), '%Y-%m-%d').date()
    except:
        return None


def _filter_current_week(weeks, today: _date) -> list:
    """找出包含今天的週"""
    for w in weeks:
        if w.year == today.year:
            # 粗略比對月份
            if w.month_start <= today.month <= w.month_end:
                return [w]
    return weeks[:1]  # fallback: 最新一週


def _filter_week_range(weeks, start: _date, end: _date) -> list:
    """過濾出日期範圍內的週"""
    result = []
    for w in weeks:
        # 粗略比對
        w_start = _date(w.year, w.month_start, w.day_start)
        w_end = _date(w.year, w.month_end, w.day_end)
        if w_start <= end and w_end >= start:
            result.append(w)
    return result


def _filter_month(weeks, year: int, month: int) -> list:
    """過濾出指定月份的週"""
    result = []
    for w in weeks:
        if w.year == year and w.month_start <= month <= w.month_end:
            result.append(w)
    return result


# ── init 指令 ──


@click.command('init')
@click.option('--year', type=int, default=0,
              help='目標年份（預設為當年+1）')
@click.option('--source', type=str, default=None,
              help='前一年週記路徑（預設自動偵測）')
def init_cmd(year: int, source: str | None):
    """建立新年度週記，拷貝前一年的特別要求區塊"""
    from weekbullet.init import create_new_journal
    try:
        path = create_new_journal(year=year, source_path=source)
        click.echo(f'✅ 已建立：{path}')
    except FileNotFoundError as e:
        click.echo(f'❌ {e}', err=True)
        sys.exit(1)
    except FileExistsError as e:
        click.echo(f'⚠️ 已存在：{e}', err=True)
        sys.exit(0)


cli.add_command(init_cmd)


# ── maintain 指令 ──


@cli.group()
def maintain():
    """維護週記結構（掃描問題 / 自動修復）"""


@maintain.command('scan')
@click.option('-f', '--file', type=str, default=None,
              help='週記路徑（預設自動偵測）')
def maintain_scan(file: str | None):
    """掃描週記結構問題（唯讀）"""
    from weekbullet.maintain import JournalMaintainer
    path = file or DEFAULT_PATH
    m = JournalMaintainer(path)
    click.echo(m.print_scan(m.scan()))


@maintain.command('fix')
@click.option('-f', '--file', type=str, default=None,
              help='週記路徑（預設自動偵測）')
def maintain_fix(file: str | None):
    """自動修復可修復的結構問題（將先備份）"""
    from weekbullet.maintain import JournalMaintainer
    path = file or DEFAULT_PATH
    m = JournalMaintainer(path)
    click.echo(m.print_fix(m.fix()))


cli.add_command(maintain)


# ── add 指令 ──


@cli.group()
@click.option('--dry-run', is_flag=True, default=False,
              help='僅預覽，不實際寫入')
@click.pass_context
def add(ctx, dry_run):
    """新增條目到週記各區塊"""
    ctx.obj['dry_run'] = dry_run


@add.command()
@click.argument('text')
@click.option('--symbol', '-s', default='●',
              help='bullet 符號（預設 ●）')
@click.option('-f', '--file', default=None, help='週記路徑')
@click.option('--date', '-d', default=None, help='日期 YYYY-MM-DD（單日/截止日）')
@click.option('--end', '-e', 'end_date', default=None, help='結束日 YYYY-MM-DD（與--date搭配表示區間）')
@click.option('--pending', is_flag=True, default=False, help='標記為待確認（顯示 ●?）')
@click.pass_context
def task(ctx, text: str, symbol: str, file: str | None, date: str | None, end_date: str | None, pending: bool):
    """新增長期任務"""
    from weekbullet.editor import add_section_item
    path = file or ctx.obj.get('file') or DEFAULT_PATH
    dry_run = ctx.obj.get('dry_run', False)
    try:
        msg = add_section_item(path, 'tasks', text, symbol, dry_run=dry_run, date_str=date, end_str=end_date, pending=pending)
        click.echo(msg)
    except Exception as e:
        click.echo(f'❌ {e}', err=True)
        sys.exit(1)


@add.command()
@click.argument('text')
@click.option('-f', '--file', default=None)
@click.option('--date', '-d', default=None, help='日期 YYYY-MM-DD（起始日）')
@click.option('--end', '-e', 'end_date', default=None, help='結束日 YYYY-MM-DD')
@click.pass_context
def reminder(ctx, text: str, file: str | None, date: str | None, end_date: str | None):
    """新增週期性提醒"""
    from weekbullet.editor import add_section_item
    path = file or ctx.obj.get('file') or DEFAULT_PATH
    try:
        msg = add_section_item(path, 'reminders', text, '○', date_str=date, end_str=end_date)
        click.echo(msg)
    except Exception as e:
        click.echo(f'❌ {e}', err=True)
        sys.exit(1)


@add.command()
@click.argument('text')
@click.option('--symbol', '-s', default='●')
@click.option('-f', '--file', default=None)
@click.option('--date', '-d', default=None, help='日期 YYYY-MM-DD（起始日）')
@click.option('--end', '-e', 'end_date', default=None, help='結束日 YYYY-MM-DD')
@click.pass_context
def schedule(ctx, text: str, symbol: str, file: str | None, date: str | None, end_date: str | None):
    """新增重要行程"""
    from weekbullet.editor import add_section_item
    path = file or ctx.obj.get('file') or DEFAULT_PATH
    try:
        msg = add_section_item(path, 'schedule', text, symbol, date_str=date, end_str=end_date)
        click.echo(msg)
    except Exception as e:
        click.echo(f'❌ {e}', err=True)
        sys.exit(1)


@add.command('shopping')
@click.argument('text')
@click.option('-f', '--file', default=None)
def add_shopping(text: str, file: str | None):
    """新增採購清單項目"""
    from weekbullet.editor import add_section_item
    path = file or DEFAULT_PATH
    try:
        msg = add_section_item(path, 'shopping', text, '●')
        click.echo(msg)
    except Exception as e:
        click.echo(f'❌ {e}', err=True)
        sys.exit(1)


@add.command('entry')
@click.argument('text')
@click.option('--date', '-d', required=True,
              help='日期 YYYY-MM-DD')
@click.option('--symbol', '-s', default='－',
              help='bullet 符號（預設 － 筆記）')
@click.option('-f', '--file', default=None)
def add_entry(text: str, date: str, symbol: str, file: str | None):
    """新增條目到特定日期的週記錄"""
    from weekbullet.editor import add_day_entry
    path = file or DEFAULT_PATH
    try:
        msg = add_day_entry(path, date, text, symbol)
        click.echo(msg)
    except ValueError as e:
        click.echo(f'❌ {e}', err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f'❌ {e}', err=True)
        sys.exit(1)


@add.command('week')
@click.option('--start', required=True,
              help='起始日 MM/DD')
@click.option('--end', default=None,
              help='結束日 MM/DD（預設 +6 天）')
@click.option('-f', '--file', default=None)
def add_week_cmd(start: str, end: str | None, file: str | None):
    """新增週區塊（若已存在則跳過）"""
    from weekbullet.editor import add_week
    path = file or DEFAULT_PATH
    try:
        parts = start.split('/')
        sm, sd = int(parts[0]), int(parts[1])
        em, ed = None, None
        if end:
            ep = end.split('/')
            em, ed = int(ep[0]), int(ep[1])
        msg = add_week(path, sm, sd, em, ed)
        click.echo(msg)
    except Exception as e:
        click.echo(f'❌ {e}', err=True)
        sys.exit(1)


# ── edit 指令 ──


@cli.group()
@click.option('--dry-run', is_flag=True, default=False,
              help='僅預覽，不實際寫入')
@click.pass_context
def edit(ctx, dry_run):
    """修改週記中的條目"""
    ctx.obj['dry_run'] = dry_run


@edit.command()
@click.argument('index', type=int)
@click.argument('new_text')
@click.option('--symbol', '-s', default=None,
              help='新的 bullet 符號（不指定則保留原符號）')
@click.option('-f', '--file', default=None)
@click.option('--date', '-d', default=None, help='設定日期 YYYY-MM-DD')
@click.option('--end', '-e', 'end_date', default=None, help='結束日 YYYY-MM-DD')
def task(index: int, new_text: str, symbol: str | None, file: str | None, date: str | None, end_date: str | None):
    """修改長期任務第 N 條"""
    from weekbullet.editor import edit_section_item
    path = file or DEFAULT_PATH
    try:
        msg = edit_section_item(path, 'tasks', index, new_text, symbol, date_str=date, end_str=end_date)
        click.echo(msg)
    except Exception as e:
        click.echo(f'❌ {e}', err=True)
        sys.exit(1)


@edit.command()
@click.argument('index', type=int)
@click.argument('new_text')
@click.option('-f', '--file', default=None)
@click.option('--date', '-d', default=None, help='設定日期 YYYY-MM-DD')
@click.option('--end', '-e', 'end_date', default=None, help='結束日 YYYY-MM-DD')
def reminder(index: int, new_text: str, file: str | None, date: str | None, end_date: str | None):
    """修改週期性提醒第 N 條"""
    from weekbullet.editor import edit_section_item
    path = file or DEFAULT_PATH
    try:
        msg = edit_section_item(path, 'reminders', index, new_text, date_str=date, end_str=end_date)
        click.echo(msg)
    except Exception as e:
        click.echo(f'❌ {e}', err=True)
        sys.exit(1)


@edit.command()
@click.argument('index', type=int)
@click.argument('new_text')
@click.option('-f', '--file', default=None)
@click.option('--date', '-d', default=None, help='設定日期 YYYY-MM-DD')
@click.option('--end', '-e', 'end_date', default=None, help='結束日 YYYY-MM-DD')
def schedule(index: int, new_text: str, file: str | None, date: str | None, end_date: str | None):
    """修改重要行程第 N 條"""
    from weekbullet.editor import edit_section_item
    path = file or DEFAULT_PATH
    try:
        msg = edit_section_item(path, 'schedule', index, new_text, date_str=date, end_str=end_date)
        click.echo(msg)
    except Exception as e:
        click.echo(f'❌ {e}', err=True)
        sys.exit(1)


@edit.command('shopping')
@click.argument('index', type=int)
@click.argument('new_text')
@click.option('-f', '--file', default=None)
def edit_shopping(index: int, new_text: str, file: str | None):
    """修改採購清單第 N 條"""
    from weekbullet.editor import edit_section_item
    path = file or DEFAULT_PATH
    try:
        msg = edit_section_item(path, 'shopping', index, new_text)
        click.echo(msg)
    except Exception as e:
        click.echo(f'❌ {e}', err=True)
        sys.exit(1)


@edit.command('entry')
@click.argument('date_str')
@click.argument('index', type=int)
@click.argument('new_text')
@click.option('--symbol', '-s', default=None)
@click.option('-f', '--file', default=None)
def edit_entry(date_str: str, index: int, new_text: str,
               symbol: str | None, file: str | None):
    """修改特定日期第 N 條"""
    from weekbullet.editor import edit_day_entry
    path = file or DEFAULT_PATH
    try:
        msg = edit_day_entry(path, date_str, index, new_text, symbol)
        click.echo(msg)
    except ValueError as e:
        click.echo(f'❌ {e}', err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f'❌ {e}', err=True)
        sys.exit(1)


# ── delete 指令 ──


@cli.group()
@click.option('--dry-run', is_flag=True, default=False,
              help='僅預覽，不實際寫入')
@click.pass_context
def delete(ctx, dry_run):
    """刪除週記中的條目"""
    ctx.obj['dry_run'] = dry_run


@delete.command()
@click.argument('index', type=int)
@click.option('-f', '--file', default=None)
def task(index: int, file: str | None):
    """刪除長期任務第 N 條"""
    from weekbullet.editor import delete_section_item
    path = file or DEFAULT_PATH
    try:
        msg = delete_section_item(path, 'tasks', index)
        click.echo(msg)
    except Exception as e:
        click.echo(f'❌ {e}', err=True)
        sys.exit(1)


@delete.command()
@click.argument('index', type=int)
@click.option('-f', '--file', default=None)
def reminder(index: int, file: str | None):
    """刪除週期性提醒第 N 條"""
    from weekbullet.editor import delete_section_item
    path = file or DEFAULT_PATH
    try:
        msg = delete_section_item(path, 'reminders', index)
        click.echo(msg)
    except Exception as e:
        click.echo(f'❌ {e}', err=True)
        sys.exit(1)


@delete.command()
@click.argument('index', type=int)
@click.option('-f', '--file', default=None)
def schedule(index: int, file: str | None):
    """刪除重要行程第 N 條"""
    from weekbullet.editor import delete_section_item
    path = file or DEFAULT_PATH
    try:
        msg = delete_section_item(path, 'schedule', index)
        click.echo(msg)
    except Exception as e:
        click.echo(f'❌ {e}', err=True)
        sys.exit(1)


@delete.command('shopping')
@click.argument('index', type=int)
@click.option('-f', '--file', default=None)
def delete_shopping(index: int, file: str | None):
    """刪除採購清單第 N 條"""
    from weekbullet.editor import delete_section_item
    path = file or DEFAULT_PATH
    try:
        msg = delete_section_item(path, 'shopping', index)
        click.echo(msg)
    except Exception as e:
        click.echo(f'❌ {e}', err=True)
        sys.exit(1)


@delete.command('entry')
@click.argument('date_str')
@click.argument('index', type=int)
@click.option('-f', '--file', default=None)
def delete_entry(date_str: str, index: int, file: str | None):
    """刪除特定日期第 N 條"""
    from weekbullet.editor import delete_day_entry
    path = file or DEFAULT_PATH
    try:
        msg = delete_day_entry(path, date_str, index)
        click.echo(msg)
    except ValueError as e:
        click.echo(f'❌ {e}', err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f'❌ {e}', err=True)
        sys.exit(1)


def main():
    cli()


if __name__ == '__main__':
    main()
