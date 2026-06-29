#!/usr/bin/env python3
"""Read-only scanner for risky Git/Codex workspaces.

Reports large files, aggregate file risk, suspicious directories, and existing
.git/objects bloat. It never deletes, moves, stages, or modifies files.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable

MB = 1024 * 1024
GB = 1024 * MB

RISKY_SUFFIXES = {
    ".vdi",
    ".vmdk",
    ".vhd",
    ".vhdx",
    ".qcow2",
    ".qed",
    ".hdd",
    ".img",
    ".raw",
    ".sav",
    ".vmem",
    ".vmss",
    ".vmsn",
    ".vmsd",
    ".iso",
    ".viso",
    ".ova",
    ".ovf",
    ".nvram",
    ".vbox-prev",
    ".zip",
    ".7z",
    ".rar",
    ".tar",
    ".gz",
    ".mp4",
    ".mov",
    ".mkv",
}

SUSPICIOUS_DIR_NAMES = {
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "target",
    ".cache",
    "coverage",
    ".next",
    ".nuxt",
    "snapshots",
    "virtualbox vms",
    "vms",
    "iso",
    "isos",
}

SUSPICIOUS_DIR_SUFFIXES = (".pvm", ".utm", ".vmwarevm")


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{size} B"


def iter_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for filename in filenames:
            yield current / filename


def safe_stat(path: Path):
    try:
        return path.stat()
    except OSError:
        return None


def is_risky_file(path: Path) -> bool:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if suffix in RISKY_SUFFIXES:
        return True
    return any(name.endswith(suffix) for suffix in RISKY_SUFFIXES if suffix.count(".") > 1)


def dir_total(path: Path, limit_files: int = 100000) -> tuple[int, int]:
    total = 0
    count = 0
    for file_path in iter_files(path):
        stat = safe_stat(file_path)
        if stat is None:
            continue
        total += stat.st_size
        count += 1
        if count >= limit_files:
            break
    return count, total


def collect_git_objects(git_objects: Path) -> dict[str, int]:
    result = {
        "exists": int(git_objects.exists()),
        "files": 0,
        "bytes": 0,
        "tmp_files": 0,
        "tmp_bytes": 0,
        "pack_files": 0,
        "pack_bytes": 0,
    }
    if not git_objects.exists():
        return result
    for path in git_objects.rglob("*"):
        if not path.is_file():
            continue
        stat = safe_stat(path)
        if stat is None:
            continue
        size = stat.st_size
        result["files"] += 1
        result["bytes"] += size
        if path.name.startswith("tmp_obj_"):
            result["tmp_files"] += 1
            result["tmp_bytes"] += size
        if path.suffix in {".pack", ".idx", ".rev"} or "pack" in path.parts:
            result["pack_files"] += 1
            result["pack_bytes"] += size
    return result


def risk_level(
    total_files: int,
    total_bytes: int,
    large_files: list[tuple[int, Path]],
    risky_files: list[tuple[int, Path]],
    mid_file_count: int,
    suspicious_dir_count: int,
    git_stats: dict[str, int],
    args: argparse.Namespace,
) -> tuple[str, list[str]]:
    critical_reasons: list[str] = []
    high_reasons: list[str] = []
    medium_reasons: list[str] = []

    if git_stats["bytes"] >= 5 * GB:
        critical_reasons.append(".git/objects >= 5 GiB")
    if git_stats["tmp_bytes"] >= GB or git_stats["tmp_files"] >= 100:
        critical_reasons.append("tmp_obj_* >= 1 GiB or >= 100 files")
    if any(size >= GB and is_risky_file(path) for size, path in risky_files):
        critical_reasons.append("VM/disk/snapshot/image/archive/media file >= 1 GiB")
    if total_bytes >= 10 * GB:
        critical_reasons.append("aggregate candidate size >= 10 GiB")

    if large_files:
        high_reasons.append(f"{len(large_files)} file(s) >= {args.large_mb} MiB")
    if total_bytes >= args.aggregate_mb * MB:
        high_reasons.append(f"aggregate candidate size >= {args.aggregate_mb} MiB")
    if total_files >= args.many_files:
        high_reasons.append(f"candidate file count >= {args.many_files}")
    if mid_file_count >= args.many_mid_files:
        high_reasons.append(f"{mid_file_count} file(s) >= {args.mid_mb} MiB")
    if risky_files:
        high_reasons.append(f"{len(risky_files)} risky extension file(s)")
    if suspicious_dir_count:
        high_reasons.append(f"{suspicious_dir_count} suspicious directories")
    if git_stats["bytes"] >= args.aggregate_mb * MB:
        high_reasons.append(f".git/objects >= {args.aggregate_mb} MiB")
    if git_stats["tmp_files"]:
        high_reasons.append(".git/objects contains tmp_obj_*")

    if 100 * MB <= total_bytes < args.aggregate_mb * MB:
        medium_reasons.append("aggregate candidate size is 100-500 MiB")

    if critical_reasons:
        return "CRITICAL", critical_reasons + high_reasons
    if high_reasons:
        return "HIGH", high_reasons
    if medium_reasons:
        return "MEDIUM", medium_reasons
    return "LOW", ["no configured large-file, aggregate, suspicious-directory, or Git object bloat threshold matched"]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only scanner for large Git/Codex workspace risk."
    )
    parser.add_argument("path", nargs="?", default=".", help="Workspace path to scan.")
    parser.add_argument("--large-mb", type=int, default=100, help="Large-file threshold.")
    parser.add_argument("--aggregate-mb", type=int, default=500, help="Aggregate warning threshold.")
    parser.add_argument("--many-files", type=int, default=1000, help="File count warning threshold.")
    parser.add_argument("--mid-mb", type=int, default=10, help="Mid-sized file threshold.")
    parser.add_argument("--many-mid-files", type=int, default=100, help="Mid-sized file count threshold.")
    parser.add_argument("--top", type=int, default=20, help="Number of top findings to print.")
    args = parser.parse_args()

    root = Path(args.path).expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"Path does not exist: {root}")

    large_threshold = args.large_mb * MB
    aggregate_threshold = args.aggregate_mb * MB
    mid_threshold = args.mid_mb * MB

    total_files = 0
    total_bytes = 0
    large_files: list[tuple[int, Path]] = []
    risky_files: list[tuple[int, Path]] = []
    mid_file_count = 0
    suspicious_dirs: dict[Path, tuple[int, int]] = {}

    for file_path in iter_files(root):
        stat = safe_stat(file_path)
        if stat is None:
            continue
        size = stat.st_size
        total_files += 1
        total_bytes += size
        if size >= large_threshold:
            large_files.append((size, file_path))
        if size >= mid_threshold:
            mid_file_count += 1
        if is_risky_file(file_path):
            risky_files.append((size, file_path))

    for dirpath, dirnames, _ in os.walk(root):
        current = Path(dirpath)
        if current.name == ".git":
            dirnames[:] = []
            continue
        for dirname in list(dirnames):
            lowered = dirname.lower()
            child = current / dirname
            if lowered in SUSPICIOUS_DIR_NAMES or lowered.endswith(SUSPICIOUS_DIR_SUFFIXES):
                suspicious_dirs[child] = dir_total(child)

    git_stats = collect_git_objects(root / ".git" / "objects")

    level, risk_reasons = risk_level(
        total_files,
        total_bytes,
        large_files,
        risky_files,
        mid_file_count,
        len(suspicious_dirs),
        git_stats,
        args,
    )

    print("# Large Git Workspace Scan")
    print(f"Workspace: {root}")
    print()
    print("## Summary")
    print(f"- Candidate files scanned: {total_files}")
    print(f"- Aggregate candidate size: {human_size(total_bytes)}")
    print(f"- Files >= {args.large_mb} MiB: {len(large_files)}")
    print(f"- Files >= {args.mid_mb} MiB: {mid_file_count}")
    print(f"- Risky extension files: {len(risky_files)}")
    print(f"- Suspicious directories: {len(suspicious_dirs)}")
    if git_stats["exists"]:
        print(f"- .git/objects size: {human_size(git_stats['bytes'])} across {git_stats['files']} file(s)")
        print(f"- .git/objects tmp_obj_*: {git_stats['tmp_files']} file(s), {human_size(git_stats['tmp_bytes'])}")
        print(f"- .git/objects pack-related: {git_stats['pack_files']} file(s), {human_size(git_stats['pack_bytes'])}")
    else:
        print("- .git/objects: not found")
    print()

    if level != "LOW":
        print("## Risk Status")
        print(f"RISK DETECTED: {level}")
        for reason in risk_reasons:
            print(f"- {reason}")
    else:
        print("## Risk Status")
        print("No obvious large Git workspace risk detected by this scanner.")
        for reason in risk_reasons:
            print(f"- {reason}")
    print()

    print("## Assessment Standard")
    print("- CRITICAL: .git/objects >= 5 GiB, tmp_obj_* >= 1 GiB or >= 100 files, any risky VM/disk/image/archive/media file >= 1 GiB, or aggregate candidate size >= 10 GiB.")
    print("- HIGH: any file >= large-file threshold, aggregate size >= aggregate threshold, many files, many mid-sized files, risky extensions, suspicious directories, .git/objects >= aggregate threshold, or any tmp_obj_*.")
    print("- MEDIUM: aggregate candidate size is 100-500 MiB or similar suspicious signals below HIGH thresholds.")
    print("- LOW: no configured threshold matched.")
    print()

    def print_findings(title: str, rows: list[tuple[int, Path]]) -> None:
        print(f"## {title}")
        if not rows:
            print("None")
            print()
            return
        for size, path in sorted(rows, reverse=True)[: args.top]:
            try:
                rel = path.relative_to(root)
            except ValueError:
                rel = path
            print(f"- {human_size(size)}  {rel}")
        print()

    print_findings("Largest Files", large_files)
    print_findings("Risky Extension Files", risky_files)

    print("## Suspicious Directories")
    if not suspicious_dirs:
        print("None")
    else:
        rows = sorted(
            ((stats[1], stats[0], path) for path, stats in suspicious_dirs.items()),
            reverse=True,
        )
        for total, count, path in rows[: args.top]:
            try:
                rel = path.relative_to(root)
            except ValueError:
                rel = path
            print(f"- {human_size(total)} across {count} file(s)  {rel}")
    print()

    print("## Suggested Next Steps")
    if level != "LOW":
        print("- Do not run `git add .`, `git hash-object`, workspace snapshots, or cleanup deletes yet.")
        print("- Review the findings and add generated, VM, cache, dependency, or archive paths to `.gitignore`.")
        print("- If cleanup is needed, list exact paths first, gather generation/deletability evidence, and require explicit confirmation.")
    else:
        print("- Continue to use normal Git caution. Re-run this scan before broad Git writes.")

    print()
    print("## Deletion Evidence Required")
    print("- This scanner identifies risk and cleanup candidates; it does not prove that anything is safe to delete.")
    print("- Before deletion, collect evidence such as build/package-manager logs, VM/application logs, Codex session logs, shell history, process command lines, timestamps matching an interrupted command, and proof that no related process is active.")
    print("- Treat VM disks, snapshots, ISOs, exports, backups, and media as user data unless the user or platform logs prove they are disposable.")
    print("- For .git/objects/tmp_obj_* cleanup, verify no Git process is active and show timestamp/command evidence before asking for confirmation.")

    return 2 if level != "LOW" else 0


if __name__ == "__main__":
    raise SystemExit(main())
