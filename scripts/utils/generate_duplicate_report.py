
import os
import re
from pathlib import Path

TARGET_DIR = os.environ.get("BOOK_ORGANIZER_TARGET_DIR", str(Path.home() / "Books"))
REPORT_FILE = "duplicates_report.md"

def normalize_title(filename):
    # Remove extension
    name = os.path.splitext(filename)[0]

    # Split by colon (half or full width)
    # The user said "Before : including full/half width"
    match = re.search(r'[:：]', name)
    if match:
        main_title = name[:match.start()].strip()
        subtitle = name[match.start()+1:].strip()
    else:
        main_title = name.strip()
        subtitle = ""

    return main_title, subtitle, name

def extract_author(full_name):
    # Common formats: "Title - Author", "Title (Author)", "Title [Author]"
    # Try to find the last " - " or "-"
    # This is a heuristic.
    author = "Unknown"

    # Strategy 1: Last " - "
    if " - " in full_name:
        parts = full_name.rsplit(" - ", 1)
        author = parts[1]
    # Strategy 2: [...] at end
    elif full_name.endswith("]"):
        try:
            start = full_name.rindex("[")
            author = full_name[start+1:-1]
        except ValueError:
            pass
    # Strategy 3: (...) at end
    elif full_name.endswith(")"):
        try:
            start = full_name.rindex("(")
            author = full_name[start+1:-1]
        except ValueError:
            pass

    return author.strip()

def find_duplicates():
    if not os.path.exists(TARGET_DIR):
        print(f"Directory not found: {TARGET_DIR}")
        return

    groups = {}

    for root, dirs, files in os.walk(TARGET_DIR):
        for file in files:
            if file.lower().endswith('.epub') and not file.startswith('._'):
                main_title, subtitle, full_name_no_ext = normalize_title(file)

                if main_title not in groups:
                    groups[main_title] = []

                groups[main_title].append({
                    "path": os.path.join(root, file),
                    "filename": file,
                    "full_name_no_ext": full_name_no_ext,
                    "subtitle": subtitle,
                    "author": extract_author(full_name_no_ext)
                })

    # Filter for groups > 1
    raw_duplicates = {k: v for k, v in groups.items() if len(v) > 1}

    # Categorize
    high_confidence = {}
    likely_series = {}
    collisions = {}

    for title, items in raw_duplicates.items():
        authors = set(item['author'] for item in items)
        known_authors = {a for a in authors if a != "Unknown"}

        if len(known_authors) > 1:
            collisions[title] = items
            continue

        # Helper to check if difference between two strings is only volume indicators
        def are_different_volumes(sub1, sub2):
            # Volume patterns: (上), (下), (一), (二), (1), (2), 上册, 下册, 卷一, 卷二
            # We look for specific keywords that indicate volume.

            # Extract potential volume markers from both strings
            vol_pattern = r'[（\(]?\s*(上|下|中|一|二|三|四|五|六|七|八|九|十|\d+)\s*[）\)]?|第\s*[一二三四五六七八九十\d]+\s*[卷册部辑]|(?:上|下|中|全)[册卷]'

            matches1 = set(re.findall(vol_pattern, sub1))
            matches2 = set(re.findall(vol_pattern, sub2))

            # If both have volume markers, and they are NOT identical sets -> likely different volumes
            if matches1 and matches2 and matches1 != matches2:
                # Also check: if we verify they are same "base" string excluding these markers?
                base1 = re.sub(vol_pattern, '', sub1).strip()
                base2 = re.sub(vol_pattern, '', sub2).strip()
                # If bases are very similar (or empty), then they differ ONLY by volume
                if base1 == base2 or (not base1 and not base2):
                    return True
            return False

        def clean_sub(s):
            # Don't aggressively remove everything in brackets, as it might contain volume info.
            # Instead, remove specific metadata like extension, file type, or known junk.
            # But for the purpose of 'grouping', previous logic was "remove all brackets".
            # Let's keep the previous clean logic for *grouping* (identifying true duplicates that might change brackets),
            # BUT adding the volume check as a filter.
            return re.sub(r'[\[\(【（].*?[\]\)】）]', '', s).strip().lower()

        # First, try to group by "cleaned" subtitle to find obvious duplicates
        sub_map = {}
        for item in items:
            c = clean_sub(item['subtitle'])
            if c not in sub_map:
                sub_map[c] = []
            sub_map[c].append(item)

        group_dupes = []
        possible_series_in_group = False

        for c, sub_items in sub_map.items():
            # If multiple items map to same cleaned subtitle, they might be duplicates.
            # BUT, they might also be "Book (Shang)" and "Book (Xia)" because clean_sub removes brackets!
            if len(sub_items) > 1:
                # Check for hidden volume conflict inside this group
                is_volumes = False
                for i in range(len(sub_items)):
                    for j in range(i + 1, len(sub_items)):
                        if are_different_volumes(sub_items[i]['subtitle'], sub_items[j]['subtitle']):
                            is_volumes = True
                            break
                    if is_volumes:
                        break

                if is_volumes:
                    # These are actually series volumes that got collapsed by clean_sub
                    possible_series_in_group = True
                else:
                    group_dupes.extend(sub_items)

        if len(group_dupes) > 1 and not possible_series_in_group:
            seen_paths = set()
            unique_dupes = []
            for d in group_dupes:
                if d['path'] not in seen_paths:
                    seen_paths.add(d['path'])
                    unique_dupes.append(d)
            high_confidence[title] = unique_dupes
        else:
            likely_series[title] = items

    # Generate Markdown
    lines = []
    lines.append("# 图书重复检查报告")
    lines.append(f"\n检查目录: `{TARGET_DIR}`")
    lines.append(f"\n生成时间: {os.popen('date').read().strip()}")

    lines.append("\n## 📋 操作说明")
    lines.append("> 请在下方 **勾选** (☑️) 您希望 **保留** 的文件。")
    lines.append("> **未勾选** 的文件将被视为多余副本，在后续清理步骤中可能会被移除。")

    lines.append("\n## 🛑 可能的重复 (同名/同作者)")
    lines.append("> 建议保留其中一份。默认已勾选第一项。")
    if not high_confidence:
        lines.append("\n_无_")
    for title, items in sorted(high_confidence.items()):
        lines.append(f"\n### 📖 {title}")
        for i, item in enumerate(items):
            # Default: Keep first, remove others
            checked = "x" if i == 0 else " "
            lines.append(f"- [{checked}] **文件**: `{item['filename']}`")
            lines.append(f"  - 📍 地址: `{item['path']}`")

    lines.append("\n---\n")

    lines.append("\n## ⚠️ 标题冲突 (不同作者/内容)")
    lines.append("> 这些书主标题相同但作者不同，可能是不同的书。默认 **全部保留**。")
    if not collisions:
        lines.append("\n_无_")
    for title, items in sorted(collisions.items()):
        lines.append(f"\n### 📚 {title}")
        for item in items:
            # Default: Keep all
            lines.append(f"- [x] **文件**: `{item['filename']}` (作者: {item['author']})")
            lines.append(f"  - 📍 地址: `{item['path']}`")

    lines.append("\n## ℹ️ 疑似系列/多卷本 (已排除)")
    lines.append("> 以下书籍主标题相同，但副标题均不相同，推测为丛书或系列文集。")
    lines.append(f"\n(共发现 {len(likely_series)} 组系列书籍，此处仅列出名称)\n")
    for title in sorted(likely_series.keys()):
        lines.append(f"- {title} ({len(likely_series[title])} 册)")

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Report generated at {os.path.abspath(REPORT_FILE)}")

if __name__ == "__main__":
    find_duplicates()
