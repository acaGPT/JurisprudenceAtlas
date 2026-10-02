#!/usr/bin/env python3
"""从《法理学》课程 Wiki 抽取课程大纲，生成课程地图所需的数据层。

用途
    解析 Wiki 克隆目录中的 Course-Syllabus.md，把它从「一篇长文」还原为
    「9 个单元 / 47 章」的结构化数据，输出站点使用的 JSON。
    源仓库更新后重跑本脚本即可重新生成，站点不维护第二份内容。

用法
    python3 tools/extract-syllabus.py --wiki <wiki 克隆目录> --out <数据输出目录> [--auto]

参数
    --wiki  已克隆的 Jurisprudence.wiki 目录（须含 Course-Syllabus.md）
    --out   输出目录，脚本会写入 syllabus.json 与 meta.json
    --auto  非交互式执行；本脚本无交互环节，保留该参数以统一脚本约定

返回值
    0  成功
    1  参数缺失或源文件不可读
    2  解析结果异常（未解析出任何章节）

依赖
    仅标准库。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WIKI_BASE = "https://github.com/acaGPT/Jurisprudence/wiki"
WIKI_REPO = "https://github.com/acaGPT/Jurisprudence.wiki"

UNIT_NUMERALS = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}

RE_UNIT = re.compile(r"^###\s+第(.+?)单元\s*·\s*(.+?)（(.+?)）\s*$")
RE_HEAD = re.compile(r"^\*\*(.+?)\*\*\s*(?:——|—|–|--|-{2,})\s*(.*)$")
RE_CODE = re.compile(r"^(P[IVX]+\.[0-9a-z.]*)\.")
RE_SECTION = re.compile(r"^\*(经典文献|延伸阅读|课前概览)")
RE_ITEM = re.compile(r"^-\s+")
RE_MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
RE_ITALIC = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")


def escape_html(text: str) -> str:
    """转义 HTML 特殊字符，避免源文本中的尖括号破坏页面结构。"""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(text: str) -> str:
    """把行内 Markdown 的斜体标记转成 <em>，其余字符转义后返回。"""
    return RE_ITALIC.sub(r"<em>\1</em>", escape_html(text.strip()))


def read_source_commit(wiki_dir: Path) -> str:
    """读取 Wiki 克隆当前的 commit 短哈希，用于追溯数据版本。"""
    try:
        out = subprocess.run(
            ["git", "-C", str(wiki_dir), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def parse_unit(line: str) -> dict | None:
    """解析单元标题行，返回单元元信息；不匹配则返回 None。"""
    match = RE_UNIT.match(line)
    if not match:
        return None
    numeral, name_zh, name_en = (part.strip() for part in match.groups())
    return {
        "num": UNIT_NUMERALS.get(numeral, 0),
        "title_zh": name_zh,
        "title_en": name_en,
    }


def collect_headings(lines: list[str]) -> list[tuple[int, re.Match]]:
    """收集全部章标题行，仅保留以章号（P*.开头）的加粗行。"""
    found = []
    for index, line in enumerate(lines):
        if not line.startswith("**"):
            continue
        match = RE_HEAD.match(line)
        if match and RE_CODE.match(match.group(1).strip()):
            found.append((index, match))
    return found


def code_of(entry: tuple[int, re.Match]) -> str:
    """取标题命中里的章号。"""
    return RE_CODE.match(entry[1].group(1).strip()).group(1)


def next_chapter_start(
    headings: list[tuple[int, re.Match]], start: int, code: str, fallback: int
) -> int:
    """中英两行已配对合并时，块须越过本章两行再找下一个章号不同的标题行作终点。

    相邻章节（PVI.1.a 紧接 PVI.1.b）使得单纯的「后一个标题行」落进下一章的
    题名行，其间的经典文献、延伸阅读与课前概览小节会被整段丢弃。
    """
    for probe in range(start, len(headings)):
        if code_of(headings[probe]) != code:
            return headings[probe][0]
    return fallback


def top_level_boundaries(lines: list[str]) -> list[int]:
    """收集顶层 ## 标题行号——章节块的终点不得越过它们。

    最后一章（PIX.4）之后还有「课程政策」等小节，其列表条目不是文献，
    不截断就会被计进该章的延伸阅读。
    """
    return [i for i, line in enumerate(lines) if line.startswith("## ")]


def clamp_end(end: int, after: int, boundaries: list[int]) -> int:
    """把候选块终点收敛到下一个顶层标题之前（若存在）。"""
    later = [i for i in boundaries if i > after]
    return min(end, later[0]) if later else end


def strip_code(title: str, code: str) -> str:
    """剥去标题开头的章号前缀——章号由卡片独立徽章呈现，标题只留题名。"""
    prefix = f"{code}."
    return title[len(prefix):].strip() if title.startswith(prefix) else title


def parse_block(block: list[str]) -> dict:
    """从单个章节的文本块中统计文献条目数并抽取课前概览链接。

    课前概览小节内含多条链接时须全部收下（例如并列的两章共用该小节），
    只取首条会吞掉后列的章节；`preclass` 仍是首条，供前端判定有无概览，
    `preclass_list` 保留全部。
    """
    counts = {"refs": 0, "further": 0}
    preclass_list = []
    current = None

    for line in block:
        section = RE_SECTION.match(line)
        if section:
            current = {"经典文献": "refs", "延伸阅读": "further", "课前概览": "preclass"}[
                section.group(1)
            ]
            continue
        if current in ("refs", "further") and RE_ITEM.match(line):
            counts[current] += 1
            continue
        if current == "preclass":
            link = RE_MD_LINK.search(line)
            if link:
                item = {"title": link.group(1).strip(), "url": link.group(2).strip()}
                preclass_list.append(item)

    return {
        "refs_count": counts["refs"],
        "further_count": counts["further"],
        "preclass": preclass_list[0] if preclass_list else None,
        "preclass_list": preclass_list,
    }


def extract(wiki_dir: Path) -> tuple[dict, dict]:
    """解析大纲全文，返回 (数据层, 元信息)。"""
    source = wiki_dir / "Course-Syllabus.md"
    if not source.is_file():
        raise FileNotFoundError(f"未找到大纲文件：{source}")

    lines = source.read_text(encoding="utf-8").split("\n")

    unit_marks = []
    for index, line in enumerate(lines):
        unit = parse_unit(line)
        if unit:
            unit["start"] = index
            unit_marks.append(unit)

    headings = collect_headings(lines)
    boundaries = top_level_boundaries(lines)

    chapters = []
    cursor = 0
    while cursor < len(headings):
        index, match = headings[cursor]
        code = RE_CODE.match(match.group(1).strip()).group(1)

        zh_title, zh_desc = match.group(1).strip(), match.group(2).strip()
        en_title, en_desc = "", ""
        end = headings[cursor + 1][0] if cursor + 1 < len(headings) else len(lines)

        if cursor + 1 < len(headings):
            pair_index, pair_match = headings[cursor + 1]
            pair_code = RE_CODE.match(pair_match.group(1).strip()).group(1)
            if pair_code == code:
                en_title, en_desc = pair_match.group(1).strip(), pair_match.group(2).strip()
                end = next_chapter_start(headings, cursor + 2, code, len(lines))
                cursor += 2
            else:
                cursor += 1
        else:
            cursor += 1

        end = clamp_end(end, index, boundaries)
        block = lines[index:end]
        unit = next((u for u in reversed(unit_marks) if u["start"] < index), None)

        chapters.append({
            "code": code,
            "unit": unit["num"] if unit else 0,
            "title_zh": inline(strip_code(zh_title, code)),
            "title_en": inline(strip_code(en_title, code)),
            "desc_zh": inline(zh_desc),
            "desc_en": inline(en_desc),
            "syllabus_url": f"{WIKI_BASE}/Course-Syllabus",
            **parse_block(block),
        })

    units = [
        {
            "num": u["num"],
            "title_zh": u["title_zh"],
            "title_en": u["title_en"],
            "chapters": sum(1 for c in chapters if c["unit"] == u["num"]),
        }
        for u in unit_marks
    ]

    data = {
        "course": {
            "title_zh": "《法理学》课程地图",
            "title_en": "Jurisprudence Course Map",
            "wiki": WIKI_BASE,
            "syllabus": f"{WIKI_BASE}/Course-Syllabus",
        },
        "units": units,
        "chapters": chapters,
    }

    meta = {
        "generated_at": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %z"),
        "source_repo": WIKI_REPO,
        "source_commit": read_source_commit(wiki_dir),
        "wiki_base": WIKI_BASE,
        "stats": {
            "units": len(units),
            "chapters": len(chapters),
            "refs": sum(c["refs_count"] for c in chapters),
            "further": sum(c["further_count"] for c in chapters),
            "preclass": sum(len(c["preclass_list"]) for c in chapters),
        },
    }
    return data, meta


def main() -> int:
    parser = argparse.ArgumentParser(
        description="从《法理学》课程 Wiki 抽取大纲，生成课程地图数据层。",
    )
    parser.add_argument("--wiki", required=True, help="已克隆的 Jurisprudence.wiki 目录")
    parser.add_argument("--out", required=True, help="数据输出目录")
    parser.add_argument("--auto", action="store_true", help="非交互式执行")
    args = parser.parse_args()

    wiki_dir = Path(args.wiki).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()

    try:
        data, meta = extract(wiki_dir)
    except FileNotFoundError as error:
        print(f"错误：{error}", file=sys.stderr)
        return 1

    if not data["chapters"]:
        print("错误：未解析出任何章节，请检查大纲文件的标题格式。", file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "syllabus.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8",
    )
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8",
    )

    stats = meta["stats"]
    print(f"单元 {stats['units']} · 章节 {stats['chapters']} · "
          f"经典文献 {stats['refs']} · 延伸阅读 {stats['further']} · "
          f"已有课前概览 {stats['preclass']}")
    print(f"源 commit：{meta['source_commit']}")
    print(f"输出：{out_dir / 'syllabus.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
