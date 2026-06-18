import hashlib
import os
import shutil
from datetime import datetime

_SIZE_TIERS: list[tuple[int, str]] = [
    (1024 ** 3,       "Large (1 GB+)"),
    (500 * 1024 ** 2, "Medium (500 MB – 1 GB)"),
    (100 * 1024 ** 2, "Medium (100 – 500 MB)"),
    (1024 ** 2,       "Small (1 – 100 MB)"),
    (1024,            "Tiny (1 KB – 1 MB)"),
    (0,               "Micro (under 1 KB)"),
]

def get_size_label(size_bytes: int) -> str:
    for threshold, label in _SIZE_TIERS:
        if size_bytes >= threshold:
            return label
    return "Micro (under 1 KB)"

def get_date_parts(file_path: str, mode: str = "modified") -> tuple[str, str]:
    try:
        ts = os.path.getctime(file_path) if mode == "created" else os.path.getmtime(file_path)
        dt = datetime.fromtimestamp(ts)
        return str(dt.year), dt.strftime("%m - %B")
    except Exception:
        return "Unknown", "Unknown"

# ─────────────────────────────────────────────
#  Sorting helpers
# ─────────────────────────────────────────────

def _file_sort_key(folder_path: str, filename: str, sort_variant: str):
    fp = os.path.join(folder_path, filename)
    variant = sort_variant.lower()
    if variant in ("name_asc", "name_desc"):
        return filename.lower()
    if variant == "extension":
        ext = os.path.splitext(filename)[1].lower()
        return (ext, filename.lower())
    if variant == "date_modified":
        try:
            return os.path.getmtime(fp)
        except Exception:
            return 0.0
    if variant == "date_created":
        try:
            return os.path.getctime(fp)
        except Exception:
            return 0.0
    if variant in ("size_asc", "size_desc"):
        try:
            return os.path.getsize(fp)
        except Exception:
            return 0
    return filename.lower()

def _sorted_files(folder_path: str, filenames: list[str], sort_variant: str) -> list[str]:
    reverse = sort_variant in ("name_desc", "size_desc")
    return sorted(
        filenames,
        key=lambda f: _file_sort_key(folder_path, f, sort_variant),
        reverse=reverse,
    )

# ─────────────────────────────────────────────
#  Rule Sort
# ─────────────────────────────────────────────

def apply_rules(
    folder_path: str,
    rules_list: list[tuple[str, str]],
    selected_files: list[str] | None = None,
    sort_variant: str = "name_asc",
) -> tuple[int, str]:
    """Move files into sub-folders based on extension rules.

    sort_variant options:
      "name_asc"      – A → Z filename (default)
      "name_desc"     – Z → A filename
      "extension"     – group by extension, then name
      "date_modified" – oldest-modified first
      "date_created"  – oldest-created first
      "size_asc"      – smallest first
      "size_desc"     – largest first
    """
    if not os.path.isdir(folder_path):
        return 0, "Directory not found."
    rule_map = {ext.lower(): folder for ext, folder in rules_list}
    selected = set(selected_files) if selected_files else None

    all_files = [
        f for f in os.listdir(folder_path)
        if os.path.isfile(os.path.join(folder_path, f))
        and (selected is None or f in selected)
    ]
    ordered = _sorted_files(folder_path, all_files, sort_variant)

    moved = 0
    try:
        for filename in ordered:
            src = os.path.join(folder_path, filename)
            if not os.path.isfile(src):
                continue
            ext = os.path.splitext(filename)[1].lower()
            if ext in rule_map:
                dest_dir = os.path.join(folder_path, rule_map[ext])
                os.makedirs(dest_dir, exist_ok=True)
                shutil.move(src, os.path.join(dest_dir, filename))
                moved += 1
        return moved, "Success"
    except Exception as e:
        return moved, str(e)

# ─────────────────────────────────────────────
#  Date Sort
# ─────────────────────────────────────────────

def sort_by_date(
    folder_path: str,
    mode: str = "modified",
    selected_files: list[str] | None = None,
    nest_size: bool = False,
) -> tuple[int, str]:
    if not os.path.isdir(folder_path):
        return 0, "Directory not found."
    selected = set(selected_files) if selected_files else None
    moved = 0
    try:
        for filename in os.listdir(folder_path):
            if selected and filename not in selected:
                continue
            src = os.path.join(folder_path, filename)
            if not os.path.isfile(src):
                continue
            year, month = get_date_parts(src, mode)
            parts = [folder_path, year, month]
            if nest_size:
                parts.append(get_size_label(os.path.getsize(src)))
            dest_dir = os.path.join(*parts)
            os.makedirs(dest_dir, exist_ok=True)
            shutil.move(src, os.path.join(dest_dir, filename))
            moved += 1
        return moved, "Success"
    except Exception as e:
        return moved, str(e)

# ─────────────────────────────────────────────
#  Size Sort
# ─────────────────────────────────────────────

def sort_by_size(
    folder_path: str,
    selected_files: list[str] | None = None,
    nest_date: bool = False,
    date_mode: str = "modified",
) -> tuple[int, str]:
    if not os.path.isdir(folder_path):
        return 0, "Directory not found."
    selected = set(selected_files) if selected_files else None
    moved = 0
    try:
        for filename in os.listdir(folder_path):
            if selected and filename not in selected:
                continue
            src = os.path.join(folder_path, filename)
            if not os.path.isfile(src):
                continue
            parts = [folder_path, get_size_label(os.path.getsize(src))]
            if nest_date:
                year, month = get_date_parts(src, date_mode)
                parts += [year, month]
            dest_dir = os.path.join(*parts)
            os.makedirs(dest_dir, exist_ok=True)
            shutil.move(src, os.path.join(dest_dir, filename))
            moved += 1
        return moved, "Success"
    except Exception as e:
        return moved, str(e)

# ─────────────────────────────────────────────
#  Nested Sort
# ─────────────────────────────────────────────

def sort_nested(
    folder_path: str,
    levels: list[str],
    selected_files: list[str] | None = None,
) -> tuple[int, str]:
    if not os.path.isdir(folder_path):
        return 0, "Directory not found."
    selected = set(selected_files) if selected_files else None
    moved = 0

    def _subfolder(file_path: str, key: str) -> str:
        if key == "extension":
            ext = os.path.splitext(file_path)[1].lower()
            return ext.lstrip(".").upper() if ext else "No Extension"
        if key == "date_modified":
            y, m = get_date_parts(file_path, "modified")
            return os.path.join(y, m)
        if key == "date_created":
            y, m = get_date_parts(file_path, "created")
            return os.path.join(y, m)
        if key == "size":
            return get_size_label(os.path.getsize(file_path))
        return "Other"

    try:
        for filename in os.listdir(folder_path):
            if selected and filename not in selected:
                continue
            src = os.path.join(folder_path, filename)
            if not os.path.isfile(src):
                continue
            dest_dir = folder_path
            for key in levels:
                dest_dir = os.path.join(dest_dir, _subfolder(src, key))
            os.makedirs(dest_dir, exist_ok=True)
            shutil.move(src, os.path.join(dest_dir, filename))
            moved += 1
        return moved, "Success"
    except Exception as e:
        return moved, str(e)

# ─────────────────────────────────────────────
#  Duplicate detection  (multiple scan modes)
# ─────────────────────────────────────────────

def _file_hash(path: str, chunk: int = 65_536) -> str | None:
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            while block := f.read(chunk):
                h.update(block)
        return h.hexdigest()
    except Exception:
        return None

def find_duplicates(
    folder_path: str,
    recursive: bool = False,
    scan_mode: str = "hash",
) -> dict[str, list[str]]:
    """Scan for duplicate files.

    scan_mode options:
      "hash"      – MD5 content hash (most accurate, default)
      "name"      – identical base filename (case-insensitive)
      "name_size" – same filename AND same byte-size
    """
    bucket: dict[str, list[str]] = {}

    walker = (
        ((dp, fn) for dp, _, fns in os.walk(folder_path) for fn in fns)
        if recursive
        else (
            (folder_path, fn) for fn in os.listdir(folder_path)
            if os.path.isfile(os.path.join(folder_path, fn))
        )
    )

    for dirpath, fname in walker:
        fp = os.path.join(dirpath, fname)
        if not os.path.isfile(fp):
            continue

        if scan_mode == "hash":
            key = _file_hash(fp)
        elif scan_mode == "name":
            key = fname.lower()
        elif scan_mode == "name_size":
            try:
                key = f"{fname.lower()}::{os.path.getsize(fp)}"
            except Exception:
                key = None
        else:
            key = _file_hash(fp)

        if key:
            bucket.setdefault(key, []).append(fp)

    return {k: v for k, v in bucket.items() if len(v) > 1}

# ─────────────────────────────────────────────
#  Duplicate deletion
# ─────────────────────────────────────────────

def delete_duplicates(
    duplicate_groups: dict[str, list[str]],
    keep: str = "first",
) -> tuple[int, int, list[str]]:
    deleted, freed = 0, 0
    errors: list[str] = []
    for paths in duplicate_groups.values():
        keep_idx = 0 if keep == "first" else len(paths) - 1
        for i, p in enumerate(paths):
            if i == keep_idx:
                continue
            try:
                freed += os.path.getsize(p)
                os.remove(p)
                deleted += 1
            except Exception as e:
                errors.append(f"{p}: {e}")
    return deleted, freed, errors
