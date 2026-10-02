#!/usr/bin/env python3
"""递增 README 中声明的版本号（补丁位 +1），供自动同步流程建 Release 使用。

用途
    课程地图的 Wiki 同步走「自动递增补丁版本并建 Release」。版本号是 README 里
    唯一的事实来源，本脚本把它读出来、递增补丁位、写回，并回显新版本号，
    供调用方拿去打 tag。幂等保护：文件已是目标版本时直接报错退出，不产生空提交。

用法
    python3 tools/bump-version.py [--readme FILE] [--version vX.Y.Z] [--dry-run]

参数
    --readme    目标 README，默认仓库根的 README.md
    --version   直接指定新版本，覆盖默认的「补丁位 +1」
    --dry-run   只回显将要写入的版本，不落盘（CI 里用于先取号后提交）

返回值
    0  成功，并把新版本号打印到标准输出
    1  未找到版本号、或文件已是该版本

依赖
    仅标准库。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RE_VERSION = re.compile(r"(\*\*当前版本\*\*：\s*)v(\d+)\.(\d+)\.(\d+)")


def bump(readme: Path, explicit: str | None = None) -> tuple[str, str]:
    """读回 README 的当前版本，给出新版本字符串。

    返回 (新版本, 旧版本)；未匹配到版本号行时抛 RuntimeError。
    注意只做读与推算，写盘在调用方判断幂等之后再发生。
    """
    text = readme.read_text(encoding="utf-8")
    match = RE_VERSION.search(text)
    if not match:
        raise RuntimeError(f"{readme} 中未找到「**当前版本**：vX.Y.Z」格式的版本声明")

    if explicit:
        new_version = explicit if explicit.startswith("v") else f"v{explicit}"
    else:
        major, minor, patch = (int(part) for part in match.groups()[1:])
        new_version = f"v{major}.{minor}.{patch + 1}"

    old_version = match.group(0).split("：")[-1].strip()
    return new_version, old_version


def replace(readme: Path, new_version: str) -> None:
    """把 README 中的版本声明替换成新版本并写回。

    由调用方先做幂等判断，本函数假定目标版本与现值不同，只负责落盘。
    """
    text = readme.read_text(encoding="utf-8")
    new_text, count = RE_VERSION.subn(
        lambda m: f"{m.group(1)}{new_version}", text, count=1,
    )
    if count != 1:
        raise RuntimeError(f"{readme} 中未找到「**当前版本**：vX.Y.Z」格式的版本声明")
    readme.write_text(new_text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="递增 README 声明的版本号（补丁位 +1）。",
    )
    parser.add_argument("--readme", help="目标 README 路径")
    parser.add_argument("--version", help="直接指定新版本，如 v0.2.0")
    parser.add_argument("--dry-run", action="store_true", help="只回显不落盘")
    args = parser.parse_args()

    readme = Path(args.readme).expanduser().resolve() if args.readme else \
        Path(__file__).resolve().parent.parent / "README.md"

    try:
        new_version, old_version = bump(readme, args.version)
        # 幂等判断必须落在写盘之前：先比再写，否则文件已被改成目标版本，
        # 二次运行时会读到「已是目标版本」，误伤正常递增。
        if old_version == new_version:
            print(f"错误：{readme} 已是 {new_version}，无需递增。", file=sys.stderr)
            return 1
        if not args.dry_run:
            replace(readme, new_version)
    except (RuntimeError, OSError) as error:
        print(f"错误：{error}", file=sys.stderr)
        return 1

    if not args.dry_run:
        print(f"版本 {old_version} → {new_version}")
    print(new_version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
