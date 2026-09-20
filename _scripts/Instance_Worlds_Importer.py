#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Instance_Worlds_Importer
用于将 Thousands Minigames 世界压缩包导入到目标世界目录。
"""

import sys
import os
import ntpath
import re
import argparse
import shutil
import zipfile
import stat
from datetime import datetime

try:
    import tomllib
except ImportError:
    tomllib = None

EXIT_SUCCESS = 0
EXIT_CANCEL = 1
EXIT_CONFIG_ERROR = 2
EXIT_RUNTIME_ERROR = 3

SCRIPT_NAME = "Instance_Worlds_Importer.py"
CONFIG_FILE_NAME = "Instance_Worlds_Importer.toml"
VERSION_MAP_FILE_NAME = "Version_Map.toml"
DEFAULT_BACKUP_DIR_NAME = "_backups"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if not SCRIPT_DIR.endswith("\\"):
    SCRIPT_DIR += "\\"

BASE_DIR = os.path.dirname(SCRIPT_DIR.rstrip("\\"))
if not BASE_DIR.endswith("\\"):
    BASE_DIR += "\\"

CONFIG_DIR_NAME = "_Configs"
CONFIG_DIR = os.path.join(SCRIPT_DIR, CONFIG_DIR_NAME) + "\\"
DEFAULT_CONFIG_PATH = CONFIG_DIR + CONFIG_FILE_NAME
DEFAULT_VERSION_MAP = CONFIG_DIR + VERSION_MAP_FILE_NAME

BUILTIN_CONFIG = {
    "archive_dir": os.path.join(BASE_DIR, "_worlds_archives") + "\\",
    "world_dir": os.path.join(BASE_DIR, "worlds") + "\\",
    "backup_dir": os.path.join(BASE_DIR, "worlds", "_backups") + "\\",
    "version_map": DEFAULT_VERSION_MAP,
}

ALLOWED_CONFIG_KEYS = {
    "archive_dir",
    "world_dir",
    "backup_dir",
    "version_map",
}

HELP_ARGS = {
    "-h",
    "-H",
    "-?",
    "-help",
    "--help",
}

VERSION_CODE_RE = re.compile(r"^[0-9]{5}$")
INSTANCE_NAME_RE = re.compile(r"^[0-9]{5}_[A-Za-z0-9_-]+$")
DRIVE_PATH_RE = re.compile(r"^[A-Za-z]:/")

HELP_TEXT = r"""
Instance_Worlds_Importer

用途：
  将 Thousands Minigames 世界压缩包导入到目标世界目录。

运行环境：
  Windows 命令行。
  需要 Python 3.11 或更高版本。

用法：
  .\Instance_Worlds_Importer.py
  .\Instance_Worlds_Importer.py --create-config
  .\Instance_Worlds_Importer.py --instance 12111_TM_Example
  .\Instance_Worlds_Importer.py --instance 12111_TM_Example --overwrite
  .\Instance_Worlds_Importer.py --no-input --instance 12111_TM_Example --overwrite

参数：
  --help, -h, -H, -?, -help
    显示帮助信息并退出。

  --create-config
    将默认配置文件写入磁盘后退出，不执行后续业务流程。

  --config, -c
    TOML 配置文件。

  --instance, -i
    目标实例名。

  --archive-dir, -a
    压缩包所在目录。

  --world-dir, -w
    目标世界根目录。

  --backup-dir, -b
    备份目录。

  --version-map
    版本映射文件。

  --overwrite
    允许备份后覆盖非空目标目录。

  --no-input
    强制非交互模式。

配置文件：
  默认配置文件：
    {脚本所在目录}\_Configs\Instance_Worlds_Importer.toml

  默认配置文件可能尚未写入磁盘。
  未写入磁盘不代表配置不存在。
  脚本会使用完整内置默认配置继续运行。
  使用 --create-config 可将默认配置文件写入磁盘。

危险操作确认：
  目标目录已存在且非空时使用 [y/N] 。
  直接按回车默认选择 N 。

退出码：
  0 = 成功
  1 = 用户取消
  2 = 参数或配置错误
  3 = 运行时错误
"""


class ScriptError(Exception):
    def __init__(self, message, exit_code=EXIT_CONFIG_ERROR):
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


class UserCancel(ScriptError):
    def __init__(self, message="已取消操作。"):
        super().__init__(message, EXIT_CANCEL)


class RuntimeScriptError(ScriptError):
    def __init__(self, message):
        super().__init__(message, EXIT_RUNTIME_ERROR)


class StrictArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ScriptError(
            f"参数错误：{message}\n使用 --help 查看完整参数说明。",
            EXIT_CONFIG_ERROR,
        )


def setup_stdio():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def oprint(message=""):
    print(message, flush=True)


def eprint(message=""):
    print(message, file=sys.stderr, flush=True)


def pause(no_input):
    if no_input:
        return
    try:
        input("按回车键退出...")
    except (EOFError, KeyboardInterrupt):
        pass


def help_requested(argv):
    return any(item in HELP_ARGS for item in argv)


def print_help():
    oprint(HELP_TEXT.strip())
    oprint("")


def normalize_raw_path(raw, path_type, param_name):
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ScriptError(f"参数错误：{param_name} 必须是字符串。")
    text = raw.strip()
    if not text:
        raise ScriptError(f"参数错误：{param_name} 不能为空。")
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("\"", "'"):
        text = text[1:-1]
    text = text.replace("/", "\\")
    trailing = text.endswith("\\")
    if path_type == "file" and trailing:
        raise ScriptError(
            f"参数类型冲突：{param_name} 期望文件路径，但输入以路径分隔符结尾。\n"
            f"输入：{raw}\n"
            "说明：末尾带路径分隔符的路径必须视为文件夹。\n"
            "请移除末尾分隔符，或改用目录型参数。"
        )
    if path_type not in ("file", "dir"):
        raise ScriptError(f"错误：内部路径类型不合法：{path_type}")
    return text


def resolve_path(raw, path_type, base_dir, param_name):
    text = normalize_raw_path(raw, path_type, param_name)
    if text is None:
        return None
    base = base_dir if base_dir else os.getcwd()
    if not ntpath.isabs(base):
        base = os.path.abspath(base)
    if not ntpath.isabs(text):
        text = ntpath.join(base, text)
    norm = ntpath.normpath(text)
    if not ntpath.isabs(norm):
        norm = ntpath.abspath(norm)
    if path_type == "dir":
        if not norm.endswith("\\"):
            norm += "\\"
    else:
        norm = norm.rstrip("\\")
    return norm


def ensure_dir_if_exists(path, label):
    path_no = path.rstrip("\\")
    if os.path.exists(path_no) and not os.path.isdir(path_no):
        raise ScriptError(f"错误：{label}路径已存在但不是目录：{path}")


def escape_toml(value):
    return value.replace("\\", "\\\\").replace('"', '\\"')


def backup_file(path):
    if not os.path.exists(path):
        raise RuntimeScriptError(f"错误：备份失败，文件不存在：{path}")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = f"{path}.bak.{timestamp}"
    counter = 1
    original_backup_path = backup_path
    while os.path.exists(backup_path):
        backup_path = f"{original_backup_path}-{counter:03d}"
        counter += 1
    try:
        shutil.copy2(path, backup_path)
    except Exception as exc:
        raise RuntimeScriptError(f"错误：备份文件失败。\n原文件：{path}\n备份文件：{backup_path}\n详情：{exc}")
    return backup_path


def write_toml_atomic(path, content):
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        with open(tmp, "rb") as f:
            tomllib.load(f)
        if os.path.exists(path):
            backup_path = backup_file(path)
            oprint(f"[INFO] 已备份原配置文件: \"{backup_path}\"")
        os.replace(tmp, path)
    except Exception as exc:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise RuntimeScriptError(f"错误：写入 TOML 配置文件失败：{path}\n详情：{exc}")


def make_relative_dir(target_dir, base_dir):
    target = target_dir.rstrip("\\")
    try:
        rel = os.path.relpath(target, base_dir)
    except ValueError:
        rel = target_dir
    rel = rel.replace("/", "\\")
    if rel == ".":
        rel = ".\\"
    if not ntpath.isabs(rel):
        if not rel.startswith(".\\") and not rel.startswith("..\\"):
            rel = ".\\" + rel
    if not rel.endswith("\\"):
        rel += "\\"
    return rel


def make_relative_file(target_file, base_dir):
    target = target_file.rstrip("\\")
    try:
        rel = os.path.relpath(target, base_dir)
    except ValueError:
        rel = target_file
    rel = rel.replace("/", "\\")
    if rel == ".":
        rel = ".\\"
    if not ntpath.isabs(rel):
        if not rel.startswith(".\\") and not rel.startswith("..\\"):
            rel = ".\\" + rel
    return rel


def create_default_config(config_path):
    config_path = os.path.abspath(config_path)
    config_dir = os.path.dirname(config_path)
    if config_dir:
        try:
            os.makedirs(config_dir, exist_ok=True)
        except OSError as exc:
            raise RuntimeScriptError(f"错误：无法创建配置文件目录：{config_dir}\n详情：{exc}")

    lines = [
        "# Thousands Minigames",
        "# Instance_Worlds_Importer 配置",
        "# 相对路径相对于脚本所在目录解析。",
        "",
        "# 压缩包所在目录。目录路径。",
        f'archive_dir = "{escape_toml(make_relative_dir(BUILTIN_CONFIG["archive_dir"], SCRIPT_DIR))}"',
        "",
        "# 世界根目录。目录路径。",
        f'world_dir = "{escape_toml(make_relative_dir(BUILTIN_CONFIG["world_dir"], SCRIPT_DIR))}"',
        "",
        "# 备份目录。目录路径。",
        f'backup_dir = "{escape_toml(make_relative_dir(BUILTIN_CONFIG["backup_dir"], SCRIPT_DIR))}"',
        "",
        "# 版本映射文件。文件路径。",
        f'version_map = "{escape_toml(make_relative_file(BUILTIN_CONFIG["version_map"], SCRIPT_DIR))}"',
    ]
    write_toml_atomic(config_path, "\n".join(lines) + "\n")


def load_config_file(path):
    if tomllib is None:
        raise ScriptError("错误：无法使用 tomllib 。\n原因：需要 Python 3.11 或更高版本。")
    if not os.path.isfile(path):
        raise ScriptError(f"错误：TOML 配置文件不存在：{path}")
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except Exception as exc:
        raise ScriptError(f"错误：TOML 配置文件解析失败：{path}\n详情：{exc}")
    if not isinstance(data, dict):
        raise ScriptError(f"错误：TOML 配置文件顶层必须是键值表：{path}")
    unknown_keys = sorted(set(data.keys()) - ALLOWED_CONFIG_KEYS)
    if unknown_keys:
        raise ScriptError(f"错误：TOML 配置中存在未知字段：{', '.join(unknown_keys)}\n文件：{path}")
    for key in ALLOWED_CONFIG_KEYS:
        if key in data and not isinstance(data[key], str):
            raise ScriptError(f"错误：TOML 配置字段 {key} 必须是字符串。\n文件：{path}")
    return data


def load_version_map(path):
    if not os.path.isfile(path):
        raise ScriptError(
            f"错误：版本映射文件不存在：{path}\n"
            "请检查 Version_Map.toml 路径，或使用 --version-map / TOML 字段 version_map 指定正确文件。"
        )
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except Exception as exc:
        raise ScriptError(f"错误：Version_Map.toml 解析失败：{path}\n详情：{exc}")
    if not isinstance(data, dict):
        raise ScriptError(f"错误：Version_Map.toml 顶层必须是键值表：{path}")
    result = {}
    for code, mc_version in data.items():
        if not isinstance(code, str) or not VERSION_CODE_RE.fullmatch(code):
            raise ScriptError(
                f"错误：Version_Map.toml 中存在不合法的版本代码键名：{code}\n"
                "版本代码必须是 5 位数字。\n"
                f"文件：{path}"
            )
        if code == "00000":
            raise ScriptError(f"错误：Version_Map.toml 不允许包含版本代码 00000 。\n文件：{path}")
        if not isinstance(mc_version, str) or not mc_version.strip():
            raise ScriptError(
                f"错误：Version_Map.toml 版本代码 {code} 对应的值必须是非空字符串。\n文件：{path}"
            )
        result[code] = mc_version.strip()
    if not result:
        raise ScriptError(f"错误：Version_Map.toml 中没有有效的版本映射。\n文件：{path}")
    return result


def validate_instance_name(name, version_map):
    if not isinstance(name, str):
        raise ScriptError("错误：实例名必须是字符串。")
    value = name.strip()
    if not value:
        raise ScriptError("错误：实例名不能为空。")
    if not value.isascii():
        raise ScriptError(
            f"错误：实例名包含非 ASCII 字符：{value}\n"
            "仅允许 ASCII 字母、数字、下划线 _ 、连字符 - 。"
        )
    if not INSTANCE_NAME_RE.fullmatch(value):
        raise ScriptError(
            f"错误：实例名格式不合法：{value}\n"
            "要求：{5位版本代码}_{名称}\n"
            "名称仅允许 ASCII 字母、数字、下划线 _ 、连字符 - 。\n"
            "合法示例：10808_Bed_Wars、12111_Cool_Parkour、26012_Murder_Mystery"
        )
    code = value[:5]
    if code not in version_map:
        raise ScriptError(
            f"错误：实例名版本代码 {code} 不在版本映射表中。\n"
            f"实例名：{value}\n"
            "请检查版本代码是否来自 Version_Map.toml 。"
        )
    return code


def clean_instance_name(raw):
    if raw is None:
        return None
    name = raw.strip()
    if len(name) >= 2 and name[0] == name[-1] and name[0] in ("\"", "'"):
        name = name[1:-1]
    if name.lower().endswith(".zip"):
        name = name[:-4]
    name = name.strip()
    if "/" in name or "\\" in name:
        raise ScriptError(f"错误：--instance 只能是实例名，不能包含路径分隔符。\n输入：{raw}")
    return name


def list_zip_files(archive_dir):
    archive_no = archive_dir.rstrip("\\")
    if not os.path.isdir(archive_no):
        return []
    try:
        entries = os.scandir(archive_no)
    except OSError as exc:
        raise ScriptError(f"错误：无法读取压缩包目录：{archive_dir}\n详情：{exc}")
    files = []
    with entries:
        for entry in entries:
            if entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(".zip"):
                files.append(entry.name)
    return sorted(files)


def find_actual_instance(archive_dir, instance_name):
    zip_files = list_zip_files(archive_dir)
    zip_files_lower = {name.lower(): name for name in zip_files}
    target_zip_name = f"{instance_name}.zip"
    actual_zip_name = zip_files_lower.get(target_zip_name.lower())
    if actual_zip_name:
        return actual_zip_name[:-4]
    return None


def prompt_wait_for_zip(archive_dir, instance_name):
    target_zip_name = f"{instance_name}.zip"
    while True:
        found = find_actual_instance(archive_dir, instance_name)
        if found:
            return found
        oprint("")
        oprint(f"[WARN] 未找到对应的存档文件: \"{target_zip_name}\"")
        oprint(f"       请将压缩包放入：{archive_dir}")
        oprint("")
        oprint("可用控制：按回车重新检查，输入 r 重新输入实例名，输入 c 取消。")
        oprint("")
        try:
            choice = input("请选择操作: ").strip().lower()
        except EOFError:
            raise UserCancel()
        if choice in ("c", "cancel"):
            raise UserCancel()
        if choice in ("r", "reinput", "re-input"):
            return None


def interactive_select(archive_dir, version_map):
    while True:
        zip_files = list_zip_files(archive_dir)
        if zip_files:
            oprint("")
            oprint("=== 可导入的存档列表 ===")
            for idx, zf in enumerate(zip_files, 1):
                oprint(f"{idx}. {zf}")
            oprint("")
            oprint("可用操作：输入序号选择，或直接输入实例名。")
            oprint("可用控制：输入 r 重新搜索，输入 c 取消。")
            oprint("")
            prompt = "请输入序号或实例名: "
        else:
            oprint("")
            oprint(f"[WARN] 在 {archive_dir} 中未找到任何 .zip 存档文件。")
            oprint("       仍允许手动输入实例名。")
            oprint("")
            oprint("可用控制：输入 r 重新搜索，输入 c 取消。")
            oprint("")
            prompt = "请输入实例名: "
        while True:
            try:
                raw = input(prompt).strip()
            except EOFError:
                raise UserCancel()
            if not raw:
                oprint("[WARN] 输入不能为空，请重新输入。")
                continue
            low = raw.lower()
            if low in ("c", "cancel"):
                raise UserCancel()
            if low in ("r", "rescan", "refresh"):
                break
            if low.endswith(".zip"):
                raw = raw[:-4]
            if raw.isdigit() and zip_files:
                idx = int(raw)
                if 1 <= idx <= len(zip_files):
                    instance = zip_files[idx - 1][:-4]
                else:
                    oprint(f"[WARN] 序号超出范围 (1-{len(zip_files)}) 。")
                    continue
            else:
                instance = raw
            try:
                validate_instance_name(instance, version_map)
            except ScriptError as exc:
                oprint(exc.message)
                oprint("")
                continue
            found = find_actual_instance(archive_dir, instance)
            if found:
                return found
            found = prompt_wait_for_zip(archive_dir, instance)
            if found:
                return found


def confirm_dangerous_operation(target_dir):
    oprint("")
    oprint(f"[WARNING] 目标目录已存在且非空: \"{target_dir}\"")
    oprint("继续执行将备份现有数据并覆盖该目录。")
    try:
        answer = input("是否继续？[y/N] ").strip().lower()
    except EOFError:
        return False
    return answer in ("y", "yes")


def inspect_target(target_dir):
    target_no = target_dir.rstrip("\\")
    if not os.path.exists(target_no):
        return False, False
    if not os.path.isdir(target_no):
        raise ScriptError(f"错误：目标路径已存在但不是目录：{target_dir}")
    try:
        with os.scandir(target_no) as entries:
            nonempty = any(True for _ in entries)
    except OSError as exc:
        raise ScriptError(f"错误：无法读取目标目录：{target_dir}\n详情：{exc}")
    return True, nonempty


def validate_backup_safety(backup_root, target_dir):
    def _compare_path(path):
        p = path.replace("/", "\\")
        p = ntpath.normpath(p)
        p = os.path.normcase(p)
        if len(p) == 2 and p[1] == ":":
            p += "\\"
        if not p.endswith("\\"):
            p += "\\"
        return p

    def same_path(a, b):
        return _compare_path(a) == _compare_path(b)

    def is_within(child, parent):
        return _compare_path(child).startswith(_compare_path(parent))

    if same_path(backup_root, target_dir):
        raise ScriptError(f"错误：备份目录与目标目录不能相同。\n备份目录：{backup_root}\n目标目录：{target_dir}")
    if is_within(backup_root, target_dir):
        raise ScriptError(f"错误：备份目录不得位于目标目录内部。\n备份目录：{backup_root}\n目标目录：{target_dir}")
    if is_within(target_dir, backup_root):
        raise ScriptError(f"错误：目标目录不得位于备份目录内部。\n备份目录：{backup_root}\n目标目录：{target_dir}")


def validate_zip_structure(zip_path, instance_name):
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            if not names:
                raise ScriptError(f"错误：压缩包为空：{zip_path}")
            top_dirs = set()
            has_root_files = False
            for raw_name in names:
                name = raw_name.replace("\\", "/")
                if not name.strip():
                    continue
                if name.startswith("/"):
                    raise ScriptError(f"错误：压缩包内包含绝对路径。\n压缩包：{zip_path}\n非法条目：{raw_name}")
                if DRIVE_PATH_RE.match(name):
                    raise ScriptError(f"错误：压缩包内包含盘符路径。\n压缩包：{zip_path}\n非法条目：{raw_name}")
                parts = name.split("/")
                if any(part == ".." for part in parts):
                    raise ScriptError(f"错误：压缩包内包含路径穿越条目。\n压缩包：{zip_path}\n非法条目：{raw_name}")
                if len(parts) == 1:
                    has_root_files = True
                else:
                    if parts[0]:
                        top_dirs.add(parts[0])
            if not has_root_files and not top_dirs:
                raise ScriptError(f"错误：压缩包结构无效：{zip_path}")
            if not has_root_files and len(top_dirs) == 1:
                nested_dir = next(iter(top_dirs))
                raise ScriptError(
                    "错误：压缩包内意外包含了一层文件夹。\n"
                    f"压缩包：{zip_path}\n"
                    f"文件夹名：{nested_dir}\n"
                    f"期望结构：压缩包根目录直接包含 {instance_name} 的世界文件。\n"
                    "请修正压缩包结构，不要依赖脚本智能剥离。"
                )
    except zipfile.BadZipFile:
        raise ScriptError(f"错误：文件损坏或不是有效的 ZIP 格式：{zip_path}")
    except ScriptError:
        raise
    except Exception as exc:
        raise RuntimeScriptError(f"错误：读取 ZIP 时发生未知错误。\n压缩包：{zip_path}\n详情：{exc}")


def perform_backup(target_dir, backup_dir, instance_name):
    backup_root_no = backup_dir.rstrip("\\")
    target_no = target_dir.rstrip("\\")
    try:
        os.makedirs(backup_root_no, exist_ok=True)
    except OSError as exc:
        raise RuntimeScriptError(f"错误：无法创建备份目录：{backup_dir}\n详情：{exc}")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_name = f"{instance_name}.bak.{timestamp}"
    backup_path = os.path.join(backup_root_no, backup_name)
    counter = 1
    original_backup_path = backup_path
    while os.path.exists(backup_path):
        backup_path = f"{original_backup_path}-{counter:03d}"
        counter += 1
    backup_path_dir = backup_path + "\\"
    oprint(f"[INFO] 正在将现有目录备份至: \"{backup_path_dir}\"")
    try:
        shutil.move(target_no, backup_path.rstrip("\\"))
    except Exception as exc:
        raise RuntimeScriptError(f"错误：备份目标目录失败。\n目标目录：{target_dir}\n备份目录：{backup_path_dir}\n详情：{exc}")
    return backup_path_dir


def _on_rm_error(func, path, exc_info):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def remove_path(path):
    path_no = path.rstrip("\\")
    if os.path.isdir(path_no):
        shutil.rmtree(path_no, onerror=_on_rm_error)
    elif os.path.exists(path_no):
        os.remove(path_no)


def clear_directory(path):
    path_no = path.rstrip("\\")
    if not os.path.isdir(path_no):
        return
    with os.scandir(path_no) as entries:
        for entry in entries:
            if entry.is_dir(follow_symlinks=False):
                shutil.rmtree(entry.path, onerror=_on_rm_error)
            else:
                try:
                    os.remove(entry.path)
                except OSError:
                    pass


def extract_archive(zip_path, target_dir):
    target_no = target_dir.rstrip("\\")
    oprint(f"[INFO] 正在解压至: \"{target_dir}\"")
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(target_no)
    except Exception as exc:
        raise RuntimeScriptError(f"错误：解压失败。\n压缩包：{zip_path}\n详情：{exc}")


def perform_import(zip_path, target_dir, backup_path, target_existed, target_nonempty):
    target_no = target_dir.rstrip("\\")
    try:
        try:
            os.makedirs(target_no, exist_ok=True)
        except OSError as exc:
            raise RuntimeScriptError(f"错误：无法创建目标目录：{target_dir}\n详情：{exc}")
        extract_archive(zip_path, target_dir)
    except Exception as exc:
        try:
            if os.path.exists(target_no):
                if backup_path is not None:
                    remove_path(target_dir)
                elif not target_existed:
                    remove_path(target_dir)
                else:
                    clear_directory(target_dir)
        except Exception as cleanup_exc:
            if backup_path is not None:
                raise RuntimeScriptError(
                    f"错误：导入失败后清理未完成目标目录失败。\n备份保留：{backup_path}\n清理错误：{cleanup_exc}"
                )
            raise RuntimeScriptError(f"错误：导入失败后清理未完成目标目录失败。\n清理错误：{cleanup_exc}")
        if backup_path is not None:
            try:
                shutil.move(backup_path.rstrip("\\"), target_no)
            except Exception as restore_exc:
                raise RuntimeScriptError(
                    f"错误：导入失败且恢复备份失败。\n备份保留：{backup_path}\n恢复错误：{restore_exc}"
                )
            raise RuntimeScriptError(f"错误：导入失败，已恢复原目标目录。\n原错误：{exc}")
        if isinstance(exc, ScriptError):
            raise
        raise RuntimeScriptError(f"错误：导入失败。\n详情：{exc}")

    oprint("[INFO] 导入完成。")
    oprint("")


def build_parser():
    parser = StrictArgumentParser(
        prog=SCRIPT_NAME,
        add_help=False,
        description="Thousands Minigames 实例存档导入工具",
    )
    parser.add_argument("--config", "-c", dest="config", metavar="FILE", default=None, help="TOML 配置文件")
    parser.add_argument("--create-config", dest="create_config", action="store_true", default=False, help="将默认配置文件写入磁盘后退出")
    parser.add_argument("--instance", "-i", dest="instance", metavar="NAME", default=None, help="目标实例名")
    parser.add_argument("--archive-dir", "-a", dest="archive_dir", metavar="DIR", default=None, help="压缩包所在目录")
    parser.add_argument("--world-dir", "-w", dest="world_dir", metavar="DIR", default=None, help="目标世界根目录")
    parser.add_argument("--backup-dir", "-b", dest="backup_dir", metavar="DIR", default=None, help="备份目录")
    parser.add_argument("--version-map", dest="version_map", metavar="FILE", default=None, help="版本映射文件")
    parser.add_argument("--overwrite", dest="overwrite", action="store_true", default=False, help="允许备份后覆盖非空目标目录")
    parser.add_argument("--no-input", dest="no_input", action="store_true", default=False, help="强制非交互模式")
    return parser


def run(argv):
    setup_stdio()

    if help_requested(argv):
        print_help()
        return EXIT_SUCCESS, False

    if sys.version_info < (3, 11):
        eprint("错误：Instance_Worlds_Importer.py 需要 Python 3.11 或更高版本。")
        eprint(f"当前 Python 版本：{sys.version.split()[0]}")
        eprint("原因：脚本依赖 Python 标准库 tomllib 解析 TOML 配置。")
        eprint("")
        return EXIT_CONFIG_ERROR, False

    if tomllib is None:
        eprint("错误：无法导入 Python 标准库 tomllib 。")
        eprint("请确认 Python 版本为 3.11 或更高版本。")
        eprint("")
        return EXIT_CONFIG_ERROR, False

    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except ScriptError as exc:
        eprint(exc.message)
        eprint("")
        return exc.exit_code, False

    no_input = bool(args.no_input)
    interactive_mode = (len(argv) == 0)

    try:
        if args.create_config:
            if args.config is not None:
                target_config = resolve_path(args.config, "file", os.getcwd(), "--config")
            else:
                target_config = DEFAULT_CONFIG_PATH
            if os.path.exists(target_config):
                if not os.path.isfile(target_config):
                    raise ScriptError(f"错误：配置文件路径存在但不是文件：{target_config}")
                oprint(f"[INFO] 配置文件已存在，未写入磁盘: \"{target_config}\"")
            else:
                create_default_config(target_config)
                oprint(f"[INFO] 已将默认配置写入磁盘: \"{target_config}\"")
            return EXIT_SUCCESS, no_input

        builtin = {
            "archive_dir": resolve_path(BUILTIN_CONFIG["archive_dir"], "dir", None, "builtin archive_dir"),
            "world_dir": resolve_path(BUILTIN_CONFIG["world_dir"], "dir", None, "builtin world_dir"),
            "backup_dir": resolve_path(BUILTIN_CONFIG["backup_dir"], "dir", None, "builtin backup_dir"),
            "version_map": resolve_path(BUILTIN_CONFIG["version_map"], "file", None, "builtin version_map"),
        }

        if args.config is not None:
            config_file = resolve_path(args.config, "file", os.getcwd(), "--config")
            if not os.path.exists(config_file):
                raise ScriptError(
                    f"错误：TOML 配置文件不存在：{config_file}\n"
                    "说明：显式指定的配置文件必须存在。\n"
                    "如果只是想使用默认内置配置，请不要提供 --config 。\n"
                    "如果想将默认配置写入磁盘，请使用 --create-config 。"
                )
            if not os.path.isfile(config_file):
                raise ScriptError(f"错误：TOML 配置路径存在但不是文件：{config_file}")
        else:
            config_file = DEFAULT_CONFIG_PATH
            if os.path.exists(config_file):
                if not os.path.isfile(config_file):
                    raise ScriptError(f"错误：默认 TOML 配置路径存在但不是文件：{config_file}")
            else:
                config_file = None

        cfg = {}
        if config_file is not None:
            cfg = load_config_file(config_file)

        config_dir = SCRIPT_DIR

        def resolve_dir(cli_value, cfg_key, builtin_value, param_name):
            if cli_value is not None:
                return resolve_path(cli_value, "dir", os.getcwd(), param_name)
            if cfg_key in cfg:
                return resolve_path(cfg[cfg_key], "dir", config_dir, cfg_key)
            return builtin_value

        def resolve_file(cli_value, cfg_key, builtin_value, param_name):
            if cli_value is not None:
                return resolve_path(cli_value, "file", os.getcwd(), param_name)
            if cfg_key in cfg:
                return resolve_path(cfg[cfg_key], "file", config_dir, cfg_key)
            return builtin_value

        archive_dir = resolve_dir(args.archive_dir, "archive_dir", builtin["archive_dir"], "--archive-dir")
        world_dir = resolve_dir(args.world_dir, "world_dir", builtin["world_dir"], "--world-dir")
        version_map = resolve_file(args.version_map, "version_map", builtin["version_map"], "--version-map")

        if args.backup_dir is not None:
            backup_dir = resolve_path(args.backup_dir, "dir", os.getcwd(), "--backup-dir")
        elif "backup_dir" in cfg:
            backup_dir = resolve_path(cfg["backup_dir"], "dir", config_dir, "backup_dir")
        else:
            backup_dir = resolve_path(ntpath.join(world_dir, DEFAULT_BACKUP_DIR_NAME), "dir", world_dir, "backup_dir")

        ensure_dir_if_exists(archive_dir, "压缩包目录")
        ensure_dir_if_exists(world_dir, "世界目录")
        ensure_dir_if_exists(backup_dir, "备份目录")

        archive_no = archive_dir.rstrip("\\")
        if not os.path.isdir(archive_no):
            raise ScriptError(f"错误：压缩包目录不存在或不是目录：{archive_dir}")

        version_map_data = load_version_map(version_map)

        if interactive_mode:
            oprint("提示：当前为交互模式。")
            oprint("提示：也可以使用命令行参数执行，使用 --help 可查看完整参数说明：")
            oprint(f"      .\\{SCRIPT_NAME} --help")
            oprint("")
            oprint("当前环境配置：")
            oprint(f"  压缩包目录: {archive_dir}")
            oprint(f"  世界根目录: {world_dir}")
            oprint(f"  备份目录: {backup_dir}")
            oprint(f"  版本映射: {version_map}")
            oprint("")

        instance_name = clean_instance_name(args.instance) if args.instance else None

        if not instance_name:
            if not interactive_mode:
                raise ScriptError(
                    "错误：缺少目标实例。\n"
                    "请提供 --instance ，或在未提供任何参数时进入交互模式。"
                )
            instance_name = interactive_select(archive_dir, version_map_data)

        validate_instance_name(instance_name, version_map_data)

        zip_path = ntpath.join(archive_no, f"{instance_name}.zip")
        if not os.path.isfile(zip_path):
            raise ScriptError(f"错误：找不到对应的存档压缩包：{zip_path}")

        validate_zip_structure(zip_path, instance_name)

        target_dir = resolve_path(ntpath.join(world_dir, instance_name), "dir", world_dir, "target world directory")
        validate_backup_safety(backup_dir, target_dir)

        target_existed, target_nonempty = inspect_target(target_dir)

        backup_path = None
        if target_existed and target_nonempty:
            if not args.overwrite:
                if not interactive_mode:
                    raise ScriptError(
                        "错误：目标目录已存在且非空。\n"
                        f"路径：{target_dir}\n"
                        "非交互模式下必须提供 --overwrite 才允许覆盖。"
                    )
                if not confirm_dangerous_operation(target_dir):
                    raise UserCancel()
            backup_path = perform_backup(target_dir, backup_dir, instance_name)

        perform_import(zip_path, target_dir, backup_path, target_existed, target_nonempty)

        oprint(f"压缩包: {zip_path}")
        oprint(f"目标目录: {target_dir}")
        oprint("")
        return EXIT_SUCCESS, no_input

    except UserCancel as exc:
        oprint(exc.message)
        oprint("")
        return EXIT_CANCEL, no_input
    except ScriptError as exc:
        eprint(exc.message)
        eprint("")
        return exc.exit_code, no_input
    except Exception as exc:
        eprint("")
        eprint(f"错误：发生未预期异常。\n详情：{exc}")
        eprint("")
        return EXIT_RUNTIME_ERROR, no_input


def entry():
    try:
        exit_code, no_input = run(sys.argv[1:])
    except KeyboardInterrupt:
        oprint("")
        oprint("已取消操作。")
        oprint("")
        os._exit(0)
    pause(no_input)
    sys.exit(exit_code)


if __name__ == "__main__":
    entry()
