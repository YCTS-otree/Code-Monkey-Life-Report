import os
import re
import json
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


def get_language(filename):
    ext = filename.split('.')[-1].lower()
    for lang, exts in LANG_EXTENSIONS.items():
        if ext in exts:
            return lang
    return None


def collect_project_stats(root_dir):
    lang_stats = defaultdict(lambda: {'files': 0, 'size': 0, 'lines': 0})
    files_info = []
    earliest_file_time = float('inf')
    latest_file_time = 0

    for dirpath, _, filenames in os.walk(root_dir):
        if not INCLUDE_HIDDEN and is_hidden(dirpath):
            continue
        for file in filenames:
            if not INCLUDE_HIDDEN and is_hidden(file):
                continue
            lang = get_language(file)
            if not lang:
                continue
            filepath = os.path.join(dirpath, file)
            stat = os.stat(filepath)
            create_time = stat.st_ctime
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

            lang_stats[lang]['files'] += 1
            lang_stats[lang]['size'] += size
            lang_stats[lang]['lines'] += count_code_lines(filepath)

    if earliest_file_time == float('inf'):
        earliest_file_time = None
    if latest_file_time == 0:
        latest_file_time = None

    total_size = sum(f['size'] for f in files_info)
    total_lines = sum(count_code_lines(f['path']) for f in files_info)

    return files_info, lang_stats, total_size, total_lines, earliest_file_time, latest_file_time


# ---------- 辅助函数 ----------

def format_time(timestamp):
    if not timestamp:
        return "未知"
    dt = datetime.datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def pretty_output(data):
    summary = data["summary"]
    languages = data["languages"]

    if summary["earliest_file_time"] and summary["latest_file_time"]:
        days = int((summary["latest_file_time"] - summary["earliest_file_time"]) / 86400)
    else:
        days = 0

    total_size_human = summary["total_size_human"]

    md_output = f"""# 🎉 项目总结报告
> 🗓️ 日期：{datetime.datetime.now().strftime('%Y-%m-%d')}
> 💾 最早的代码诞生于：{format_time(summary['earliest_file_time'])}

## 📊 项目概览
- 🗃️ 文件总数：**{summary['total_files']}**
- 💾 代码体积：**{total_size_human}**
- 🧾 累计代码行数：**{summary['total_lines']:,}**
- ⌨️ 估计敲击键盘次数：**{summary['keystrokes']:,}**
- 🕰️ 编码旅程跨度：**{days} 天**

---

## 💻 按语言统计
"""

    for lang, stat in languages.items():
        md_output += (
            f"- **{lang}**：{stat['files']} 文件，{stat['lines']:,} 行代码，共 {stat['size_human']}\n"
        )

    md_output += "\n---\n🎯 继续积累，让项目越来越强大！ 🚀\n"

    if ENABLE_COLOR:
        print(Fore.CYAN + "\n📊【项目总结报告】\n" + Style.RESET_ALL)
        print(Fore.BLUE + f"总文件数：{summary['total_files']}")
        print(Fore.GREEN + f"总代码行数：{summary['total_lines']:,}")
        print(Fore.MAGENTA + f"累计体积：{total_size_human}")
        print(Fore.RED + f"键盘敲击：{summary['keystrokes']:,} 次")
        print(Fore.CYAN + f"历时：{days} 天")
        print(Fore.YELLOW + "\n🎯 继续积累，让项目越来越强大！")

    current_dir = os.path.dirname(os.path.abspath(__file__))
    report_dir = os.path.join(current_dir, "report")
    if not os.path.exists(report_dir):
        os.makedirs(report_dir)

    if EXPORT_MARKDOWN:
        md_path = os.path.join(report_dir, f"Project_Report_{datetime.date.today()}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_output)
        print(color(f"📦 已生成 Markdown 报告：{md_path}", Fore.YELLOW))

    if EXPORT_JSON:
        json_path = os.path.join(report_dir, f"Project_Report_{datetime.date.today()}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(color(f"📦 已生成 JSON 报告：{json_path}", Fore.YELLOW))



def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    print(color("🚀 正在扫描当前项目目录...", Fore.CYAN))

    files_info, lang_stats, total_size, total_lines, earliest_file_time, latest_file_time = collect_project_stats(root_dir)

    keystrokes = int(total_size / 1.5)

    summary = {
        'total_files': len(files_info),
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
    }

    pretty_output(data)

    print(color("\n🎉 项目总结完成！\n", Fore.MAGENTA))


if __name__ == "__main__":
    main()
    input('输入任意内容退出')
