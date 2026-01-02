import os
import re
import sys
import json
import time
import datetime
from collections import defaultdict

try:
    from colorama import Fore, Style, init as color_init
    color_init(autoreset=True)
except ImportError:
    class Dummy:
        def __getattr__(self, _): return ''
    Fore = Style = Dummy()

# ========== 可调参数 ==========
LANG_EXTENSIONS = {
    'Python': ['py', 'pyw'],
    'C': ['c', 'h'],
    'C++': ['cpp', 'hpp', 'cc', 'cxx'],
    'C#': ['cs'],
    'JavaScript': ['js', 'jsx'],
    'Java': ['java'],
    'Go': ['go'],
}

MERGE_SIMILAR_FILES = False     #是否合并相似文件（防止虚高）
INCLUDE_HIDDEN = False          #是否包含隐藏文件/文件夹
ENABLE_COLOR = True             #是否启用彩色输出
EXPORT_MARKDOWN = True          #是否导出 Markdown 报告
EXPORT_JSON = True              #是否导出 JSON 报告
# ==============================

def color(text, c):
    return f"{c}{text}{Style.RESET_ALL}" if ENABLE_COLOR else text

def is_hidden(path):
    return any(part.startswith('.') for part in path.split(os.sep))

def human_size(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"

def count_code_lines(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0

def normalize_name(filename):
    name = os.path.splitext(filename)[0]
    return re.sub(r'[\d\._-]+$', '', name)

def get_language(filename):
    ext = filename.split('.')[-1].lower()
    for lang, exts in LANG_EXTENSIONS.items():
        if ext in exts:
            return lang
    return None

def parse_root_dirs(input_text):
    parts = [p.strip() for p in re.split(r"[;,]+", input_text or "") if p.strip()]
    return parts

def _unique_project_name(project_stats, project_name, root_dir):
    if project_name not in project_stats:
        return project_name
    root_tag = os.path.basename(os.path.abspath(root_dir)) or "root"
    candidate = f"{project_name} ({root_tag})"
    if candidate not in project_stats:
        return candidate
    counter = 2
    while True:
        candidate = f"{project_name} ({root_tag}-{counter})"
        if candidate not in project_stats:
            return candidate
        counter += 1

def collect_stats(root_dirs, year=None):
    project_stats = {}
    lang_stats = defaultdict(lambda: {'files': 0, 'size': 0, 'lines': 0})
    earliest_project_time = float('inf')
    latest_project_time = 0
    visited_dirs = set()
    visited_projects = set()

    if isinstance(root_dirs, str):
        root_dirs = [root_dirs]

    for root_dir in root_dirs:
        root_dir = os.path.abspath(root_dir)
        if not os.path.isdir(root_dir):
            continue
        for project_name in os.listdir(root_dir):
            project_path = os.path.join(root_dir, project_name)
            if not os.path.isdir(project_path):
                continue
            if not INCLUDE_HIDDEN and is_hidden(project_path):
                continue

            project_realpath = os.path.realpath(project_path)
            if project_realpath in visited_projects:
                continue
            visited_projects.add(project_realpath)
            project_key = _unique_project_name(project_stats, project_name, root_dir)

            files_info = []
            earliest_file_time = float('inf')
            latest_file_time = 0

            for dirpath, dirnames, filenames in os.walk(project_path):
                real_dirpath = os.path.realpath(dirpath)
                if real_dirpath in visited_dirs:
                    dirnames[:] = []
                    continue
                visited_dirs.add(real_dirpath)

                if not INCLUDE_HIDDEN and is_hidden(dirpath):
                    dirnames[:] = []
                    continue
                if not INCLUDE_HIDDEN:
                    dirnames[:] = [d for d in dirnames if not d.startswith('.')]

                for file in filenames:
                    lang = get_language(file)
                    if not lang:
                        continue
                    filepath = os.path.join(dirpath, file)
                    if not INCLUDE_HIDDEN and is_hidden(file):
                        continue

                    stat = os.stat(filepath)
                    create_time = stat.st_ctime
                    if year:
                        if datetime.datetime.fromtimestamp(create_time).year != year:
                            continue
                    size = stat.st_size

                    files_info.append({
                        'path': filepath,
                        'name': file,
                        'lang': lang,
                        'size': size,
                        'ctime': create_time
                    })
                    earliest_file_time = min(earliest_file_time, create_time)
                    latest_file_time = max(latest_file_time, create_time)

            if MERGE_SIMILAR_FILES:
                merged = {}
                for f in files_info:
                    base = normalize_name(f['name'])
                    if base not in merged or merged[base]['ctime'] < f['ctime']:
                        merged[base] = f
                files_info = list(merged.values())

            if not files_info:
                continue

            total_size = sum(f['size'] for f in files_info)
            total_lines = sum(count_code_lines(f['path']) for f in files_info)
            for f in files_info:
                lang_stats[f['lang']]['files'] += 1
                lang_stats[f['lang']]['size'] += f['size']
                lang_stats[f['lang']]['lines'] += count_code_lines(f['path'])

            project_stats[project_key] = {
                'file_count': len(files_info),
                'total_size': total_size,
                'total_lines': total_lines,
                'earliest_file_time': earliest_file_time
            }
            earliest_project_time = min(earliest_project_time, earliest_file_time)
            latest_project_time = max(latest_project_time, latest_file_time)

    if earliest_project_time == float('inf'):
        earliest_project_time = None
    if latest_project_time == 0:
        latest_project_time = None

    return project_stats, lang_stats, earliest_project_time, latest_project_time

    


# ---------- 辅助函数 ----------
def format_time(timestamp):
    if not timestamp:
        return "未知"
    dt = datetime.datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def level_comment(lines):
    """代码行数等级"""
    if lines < 1000:
        return f"💎 精炼的{lines:,}行代码，每一行都经过深思熟虑"
    elif lines < 10000:
        return f"💪 从hello world到{lines:,}行，你的成长肉眼可见"
    elif lines < 20000:
        return f"🔥 {lines:,}行代码！这相当于写了本《三体》的技术版"
    elif lines < 30000:
        return f"💪 {lines:,}行代码的积累，你已接近技术巅峰！"
    elif lines < 50000:
        return f"🤯 {lines:,}行代码？！大佬请收下我的膝盖！"
    else:
        return f"👑 传说级程序员警告！{lines:,}行代码已经突破人类极限"

def size_comment(size_human):
    return f"🗂️ 你的项目累计 {size_human}，知识的重量正在突破次元壁！"

def project_comment(projects):
    if projects >= 40:
        return f"🤯 {projects}个项目？！大佬你是住在IDE里了吗？"
    elif projects >= 30:
        return f"🎮 项目狂魔实锤！{projects}个作品证明你是真正的全栈选手"
    elif projects >= 20:
        return f"🌟 {projects}个数字世界！从萌新到多开玩家，每个项目都是你的星辰大海"
    elif projects >= 10:
        return f"🌱 {projects}颗种子已种下，明年会开出怎样的花？"
    else:
        return f"🎯 专注是种美德！这{projects}个项目见证了你从0到1的突破"

def keystroke_comment(keystrokes):
    if keystrokes < 50000:
        return f"⌨️ {keystrokes:,}次敲击，每个字符都是思想的结晶"
    elif keystrokes < 100000:
        return f"🚀 {keystrokes:,}次敲击！你的手指在键盘上开出了花"
    elif keystrokes < 1000000:
        return f"💻 键盘：已冒烟！{keystrokes:,}次敲击见证你的奋斗"
    elif keystrokes < 2000000:
        return f"🌟 {keystrokes:,}次敲击！百万敲击俱乐部欢迎你！键盘都要包浆了..."
    else:
        return f"🔥 {keystrokes//10000}万次？！这还是碳基生物？！就是你小子害键盘涨价的吧？"
    

def duration_comment(days):
    if days >= 1825:
        return f'🏆 呦，老码农了。你还记得{days//365}年前写下的第一个文件吗？我猜是"Hellow_world吧？"。'
    elif days >= 1000:
        return f"🔥 {days}天的热爱！编程已成为你生活的一部分"
    elif days >= 500:
        return f"🎯 千日计划进行中，{days}天的积累开始显现威力"
    elif days >= 100:
        return f"🔥 {days} 天的积累，热爱与毅力并行。"
    else:
        return f"🌱 从{days}天前种下第一行代码，未来可期"

def annual_project_comment(projects):
    return "【年度项目成就评语待填写】"

def annual_level_comment(lines):
    return "【年度代码行数成就评语待填写】"

def annual_keystroke_comment(keystrokes):
    return "【年度键盘敲击成就评语待填写】"

def annual_size_comment(size_human):
    return "【年度体积成就评语待填写】"

def annual_duration_comment(days):
    return "【年度时长成就评语待填写】"

# ---------- 输出函数 ----------
def pretty_output(data, mode="lifetime", year=None):
    summary = data["summary"]
    languages = data["languages"]

    # 时间跨度
    if summary["earliest_file_time"] and summary["latest_file_time"]:
        if mode == "annual":
            days = int((summary["latest_file_time"] - summary["earliest_file_time"]) / 86400)
        else:
            now = datetime.datetime.now().timestamp()
            days = int((now - summary["earliest_file_time"]) / 86400)
    else:
        days = 0
    lines = summary["total_lines"]
    keystrokes = summary["keystrokes"]
    total_size_human = summary["total_size_human"]
    projects = summary["project_count"]

    is_annual = mode == "annual"
    title = "年度总结报告" if is_annual else "码农生涯成就报告"
    date_line = f"> 🗓️ 年度：{year}\n" if is_annual else f"> 🗓️ 日期：{datetime.datetime.now().strftime('%Y-%m-%d')}\n"

    # Markdown 输出
    md_output = f"""# 🎉 {title}
{date_line}> 💾 最早的代码诞生于：{format_time(summary["earliest_file_time"])}

## 📊 总览成就
- 🧠 累计项目数：**{projects}**
- 🗃️ 文件总数：**{summary["total_files"]}**
- 💾 代码体积：**{total_size_human}**
- 🧾 累计代码行数：**{lines:,}**
- ⌨️ 估计敲击键盘次数：**{keystrokes:,}**
- 🕰️ 编码旅程跨度：**{days} 天**

---

## 💬 成就评语

- {annual_project_comment(projects) if is_annual else project_comment(projects)}
- {annual_level_comment(lines) if is_annual else level_comment(lines)}
- {annual_keystroke_comment(keystrokes) if is_annual else keystroke_comment(keystrokes)}
- {annual_size_comment(total_size_human) if is_annual else size_comment(total_size_human)}
- {annual_duration_comment(days) if is_annual else duration_comment(days)}

---

## 💻 按语言统计
"""

    for lang, stat in languages.items():
        md_output += (
            f"- **{lang}**：{stat['files']} 文件，{stat['lines']:,} 行代码，共 {stat['size_human']}\n"
        )

    md_output += "\n---\n🎯 保持热爱，奔赴下一场代码的山海！ 🚀\n"

    # 彩色输出
    if ENABLE_COLOR:
        header_title = "年度总结报告" if is_annual else "码农生涯报告"
        print(Fore.CYAN + f"\n📊【{header_title}】\n" + Style.RESET_ALL)
        print(Fore.YELLOW + f"项目数量：{projects}")
        print(Fore.GREEN + f"总代码行数：{lines:,}")
        print(Fore.BLUE + f"总文件数：{summary['total_files']}")
        print(Fore.MAGENTA + f"累计体积：{total_size_human}")
        print(Fore.RED + f"键盘敲击：{keystrokes:,} 次")
        print(Fore.CYAN + f"历时：{days} 天")
        if is_annual:
            print(Fore.WHITE + "\n💬 " + annual_level_comment(lines))
            print(Fore.WHITE + annual_project_comment(projects))
            print(Fore.WHITE + annual_keystroke_comment(keystrokes))
            print(Fore.WHITE + annual_size_comment(total_size_human))
            print(Fore.WHITE + annual_duration_comment(days))
            print(Fore.YELLOW + "\n\n🎯 这一年辛苦啦，继续用代码改变世界吧！")
        else:
            print(Fore.WHITE + "\n💬 " + level_comment(lines))
            print(Fore.WHITE + project_comment(projects))
            print(Fore.WHITE + keystroke_comment(keystrokes))
            print(Fore.WHITE + size_comment(total_size_human))
            print(Fore.WHITE + duration_comment(days))
            print(Fore.YELLOW + "\n\n🎯 新的一年，继续用代码改变世界吧！")

    current_dir = os.path.dirname(os.path.abspath(__file__))

    if not os.path.exists(f"{current_dir}\\report"):
        os.makedirs(f"{current_dir}\\report")

    # Markdown 输出文件
    report_tag = f"Annual_{year}" if is_annual else "Code"

    if EXPORT_MARKDOWN:
        with open(f"{current_dir}\\report\{report_tag}_Report_{datetime.date.today()}.md", "w", encoding="utf-8") as f:
            f.write(md_output)
        print(color(f"📦 已生成 Markdown 报告：\\report\{report_tag}_Report_{datetime.date.today()}.md", Fore.YELLOW))

    # JSON 输出文件
    if EXPORT_JSON:
        with open(f"{current_dir}\\report\{report_tag}_Report_{datetime.date.today()}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(color(f"📦 已生成 JSON 报告：\\report\{report_tag}_Report_{datetime.date.today()}.json", Fore.YELLOW))



def main():
    print("请选择统计模式：")
    print("1. 生涯总结（多项目）")
    print("2. 年度总结（指定年份）")
    mode_choice = input("请输入模式编号：").strip() or "1"

    root_input = input("请输入要统计的文件夹路径（多个用逗号/分号分隔）：").strip()
    root_dirs = parse_root_dirs(root_input)
    if not root_dirs:
        print("❌ 未输入有效的文件夹路径")
        return
    valid_dirs = []
    for path in root_dirs:
        if os.path.exists(path):
            valid_dirs.append(path)
        else:
            print(f"⚠️ 路径不存在，已跳过：{path}")
    if not valid_dirs:
        print("❌ 没有可用的文件夹路径")
        return

    print(color("🚀 正在扫描你的代码宇宙...", Fore.CYAN))
    year = None
    mode = "lifetime"
    if mode_choice == "2":
        mode = "annual"
        year_input = input("请输入年度（如 2024）：").strip()
        if not year_input.isdigit():
            print("❌ 年度输入有误")
            return
        year = int(year_input)

    project_stats, lang_stats, earliest_file_time, latest_file_time = collect_stats(valid_dirs, year=year)

    total_files = sum(p['file_count'] for p in project_stats.values())
    total_lines = sum(p['total_lines'] for p in project_stats.values())
    total_size = sum(p['total_size'] for p in project_stats.values())
    keystrokes = int(total_size / 1.5)  # 简单估算：1 字节 ≈ 1.5 按键（含空格/缩进等）

    summary = {
        'project_count': len(project_stats),
        'total_files': total_files,
        'total_lines': total_lines,
        'total_size': total_size,
        'total_size_human': human_size(total_size),
        'keystrokes': keystrokes,
        'earliest_file_time': earliest_file_time,
        'latest_file_time': latest_file_time,
    }

    data = {
        "summary": summary,
        "languages": {
            lang: {
                "files": stat["files"],
                "lines": stat["lines"],
                "size": stat["size"],
                "size_human": human_size(stat["size"])
            } for lang, stat in lang_stats.items()
        },
        "projects": project_stats,
    }

    pretty_output(data, mode=mode, year=year)

    print(color("\n🎉 Happy Programmer’s Day! 继续创造属于你的代码宇宙吧。\n", Fore.MAGENTA))

if __name__ == "__main__":
    main()
    input('输入任意内容退出')
