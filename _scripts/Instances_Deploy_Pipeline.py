#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Instances_Deploy_Pipeline
用于按固定流程部署一个或多个 Thousands Minigames 实例。
"""

import sys
import os
import ntpath
import re
import argparse
import shutil
import subprocess
from datetime import datetime

try:
    import tomllib
except ImportError:
    tomllib = None

EXIT_SUCCESS = 0
EXIT_CANCEL = 1
EXIT_CONFIG_ERROR = 2
EXIT_RUNTIME_ERROR = 3

SCRIPT_NAME = "Instances_Deploy_Pipeline.py"
CONFIG_FILE_NAME = "Instances_Deploy_Pipeline.toml"
VERSION_MAP_FILE_NAME = "Version_Map.toml"
IMPORTER_SCRIPT_NAME = "Instance_Worlds_Importer.py"
CONFIG_CLONER_SCRIPT_NAME = "Instance_Configs_Cloner.py"
STARTUP_GENERATOR_SCRIPT_NAME = "Instance_Startup_Scripts_Generator.py"

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
    "configs_root": os.path.join(BASE_DIR, "configs") + "\\",
    "template_root": os.path.join(SCRIPT_DIR, "TM_Example_Configs", "configs") + "\\",
    "output_dir": os.path.join(BASE_DIR, "_startup_scripts_legacy") + "\\",
    "version_map": DEFAULT_VERSION_MAP,
}

IMPORTER_SCRIPT_PATH = SCRIPT_DIR + IMPORTER_SCRIPT_NAME
CONFIG_CLONER_SCRIPT_PATH = SCRIPT_DIR + CONFIG_CLONER_SCRIPT_NAME
STARTUP_GENERATOR_SCRIPT_PATH = SCRIPT_DIR + STARTUP_GENERATOR_SCRIPT_NAME

ALLOWED_CONFIG_KEYS = {
    "archive_dir",
    "world_dir",
    "configs_root",
    "template_root",
    "output_dir",
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

HELP_TEXT = r"""
Instances_Deploy_Pipeline

用途：
  按固定流程部署一个或多个 Thousands Minigames 实例。

运行环境：
  Windows 命令行。
  需要 Python 3.11 或更高版本。

部署流程：
  1. 调用 Instance_Worlds_Importer.py 导入存档。
  2. 调用 Instance_Configs_Cloner.py 复制配置。
  3. 调用 Instance_Startup_Scripts_Generator.py 生成启动脚本。

用法：
  .\Instances_Deploy_Pipeline.py
  .\Instances_Deploy_Pipeline.py --create-config
  .\Instances_Deploy_Pipeline.py --instance 12111_TM_Example
  .\Instances_Deploy_Pipeline.py --all
  .\Instances_Deploy_Pipeline.py --all --overwrite
  .\Instances_Deploy_Pipeline.py --instance 12111_TM_Example --dry-run
  .\Instances_Deploy_Pipeline.py --instance 12111_TM_Example --skip-world-import

参数：
  --help, -h, -H, -?, -help
    显示帮助信息并退出。

  --create-config
    将默认配置文件写入磁盘后退出，不执行后续业务流程。

  --config, -c
    TOML 配置文件。

  --instance, -i
    目标实例名。

  --all
    批量部署 archive_dir 中所有合法存档压缩包。

  --overwrite
    允许子步骤在必要时备份后覆盖已有目标。

  --dry-run
    仅显示执行计划和将要执行的命令，不实际调用子脚本。

  --skip-world-import
    跳过导入存档。

  --skip-config-clone
    跳过复制配置。

  --skip-startup-script
    跳过生成启动脚本。

  --no-input
    强制非交互模式。

交互模式：
  仅在未提供任何命令行参数时进入交互模式。
  输入序号可选择单个实例。
  输入逗号分隔序号可多选，例如 1,3,5 。
  输入 all 可选择全部实例。
  输入 r 可重新搜索。
  输入 c 可取消。

配置文件：
  默认配置文件：
    {脚本所在目录}\_Configs\Instances_Deploy_Pipeline.toml

  默认配置文件可能尚未写入磁盘。
  未写入磁盘不代表配置不存在。
  脚本会使用完整内置默认配置继续运行。
  使用 --create-config 可将默认配置文件写入磁盘。

危险操作确认：
  检测到已有目标时使用 [y/N] 。
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
        "# Instances_Deploy_Pipeline 配置",
        "# 相对路径相对于脚本所在目录解析。",
        "",
        "# 压缩包所在目录。目录路径。",
        f'archive_dir = "{escape_toml(make_relative_dir(BUILTIN_CONFIG["archive_dir"], SCRIPT_DIR))}"',
        "",
        "# 世界根目录。目录路径。",
        f'world_dir = "{escape_toml(make_relative_dir(BUILTIN_CONFIG["world_dir"], SCRIPT_DIR))}"',
        "",
        "# 实例配置根目录。目录路径。",
        f'configs_root = "{escape_toml(make_relative_dir(BUILTIN_CONFIG["configs_root"], SCRIPT_DIR))}"',
        "",
        "# 模板配置根目录。目录路径。",
        f'template_root = "{escape_toml(make_relative_dir(BUILTIN_CONFIG["template_root"], SCRIPT_DIR))}"',
        "",
        "# 启动脚本输出目录。目录路径。",
        f'output_dir = "{escape_toml(make_relative_dir(BUILTIN_CONFIG["output_dir"], SCRIPT_DIR))}"',
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
            "请检查 Version_Map.toml 路径，或使用 --config 指定包含正确 version_map 的配置。"
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


def list_valid_zip_instances(archive_dir, version_map):
    archive_no = archive_dir.rstrip("\\")
    if not os.path.isdir(archive_no):
        return []
    try:
        entries = os.scandir(archive_no)
    except OSError as exc:
        raise ScriptError(f"错误：无法读取压缩包目录：{archive_dir}\n详情：{exc}")
    instances = []
    with entries:
        for entry in entries:
            if not entry.is_file(follow_symlinks=False):
                continue
            if not entry.name.lower().endswith(".zip"):
                continue
            stem = entry.name[:-4]
            try:
                validate_instance_name(stem, version_map)
                instances.append(stem)
            except ScriptError:
                continue
    return sorted(instances)


def find_actual_instance(archive_dir, instance_name):
    archive_no = archive_dir.rstrip("\\")
    if not os.path.isdir(archive_no):
        return None
    target_zip_name = f"{instance_name}.zip".lower()
    try:
        entries = os.scandir(archive_no)
    except OSError:
        return None
    with entries:
        for entry in entries:
            if not entry.is_file(follow_symlinks=False):
                continue
            if entry.name.lower() == target_zip_name:
                return entry.name[:-4]
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


def parse_index_selection(raw, max_index):
    normalized = raw.replace("，", ",")
    parts = [part.strip() for part in normalized.split(",")]
    parts = [part for part in parts if part]
    if not parts:
        raise ValueError("未识别到有效序号。")
    indices = []
    for part in parts:
        low = part.lower()
        if low == "all":
            raise ValueError("all 必须单独输入，不能与序号混用。")
        if low in ("r", "rescan", "refresh", "c", "cancel"):
            raise ValueError("多选序号中不能包含控制命令。")
        if not part.isdigit():
            raise ValueError("多选模式下，逗号分隔的每一项都必须是数字序号。")
        idx = int(part)
        if idx < 1 or idx > max_index:
            raise ValueError(f"序号 {idx} 超出范围 (1-{max_index}) 。")
        indices.append(idx)
    return sorted(set(indices))


def confirm_selected_instances(selected_instances):
    oprint("")
    oprint(f"已选择 {len(selected_instances)} 个实例：")
    oprint("")
    for idx, name in enumerate(selected_instances, 1):
        oprint(f"{idx}. {name}")
    oprint("")
    if not confirm("是否继续？[Y/n] ", True):
        raise UserCancel()


def confirm(prompt, default_yes=False):
    while True:
        try:
            answer = input(prompt).strip().lower()
        except EOFError:
            return False
        if not answer:
            return default_yes
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        oprint("无效输入。请输入 y / yes 或 n / no 。")
        oprint("")


def interactive_select_instances(archive_dir, version_map):
    while True:
        instances = list_valid_zip_instances(archive_dir, version_map)
        if instances:
            oprint("")
            oprint("=== 可部署的实例列表 ===")
            for idx, name in enumerate(instances, 1):
                oprint(f"{idx}. {name}")
            oprint("")
            oprint("可用操作：输入序号选择，支持用逗号分隔多选，输入 all 选择全部，或直接输入实例名。")
            oprint("可用控制：输入 r 重新搜索，输入 c 取消。")
            oprint("")
            prompt = "请输入序号或实例名: "
        else:
            oprint("")
            oprint(f"[WARN] 在 {archive_dir} 中未找到任何合法存档压缩包。")
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
            if low == "all":
                if not instances:
                    oprint("[WARN] 当前没有可选实例，无法使用 all 。")
                    oprint("       请输入实例名，或输入 r 重新搜索。")
                    continue
                selected = instances[:]
                confirm_selected_instances(selected)
                return selected
            normalized_raw = raw.replace("，", ",")
            if "," in normalized_raw:
                if not instances:
                    oprint("[WARN] 当前没有可选实例，无法使用序号多选。")
                    oprint("       请输入实例名，或输入 r 重新搜索。")
                    continue
                try:
                    indices = parse_index_selection(raw, len(instances))
                except ValueError as exc:
                    oprint(f"错误：{exc}")
                    oprint("")
                    continue
                selected = [instances[idx - 1] for idx in indices]
                confirm_selected_instances(selected)
                return selected
            if raw.isdigit() and instances:
                idx = int(raw)
                if 1 <= idx <= len(instances):
                    selected = [instances[idx - 1]]
                    confirm_selected_instances(selected)
                    return selected
                oprint(f"[WARN] 序号超出范围 (1-{len(instances)}) 。")
                continue
            instance = raw
            if instance.lower().endswith(".zip"):
                instance = instance[:-4]
            try:
                validate_instance_name(instance, version_map)
            except ScriptError as exc:
                oprint(exc.message)
                oprint("")
                continue
            found = find_actual_instance(archive_dir, instance)
            if not found:
                found = prompt_wait_for_zip(archive_dir, instance)
                if not found:
                    continue
            selected = [found]
            confirm_selected_instances(selected)
            return selected


def inspect_dir(path):
    path_no = path.rstrip("\\")
    if not os.path.exists(path_no):
        return False, False
    if not os.path.isdir(path_no):
        raise ScriptError(f"错误：目标路径已存在但不是目录：{path}")
    try:
        with os.scandir(path_no) as entries:
            nonempty = any(True for _ in entries)
    except OSError as exc:
        raise ScriptError(f"错误：无法读取目标目录：{path}\n详情：{exc}")
    return True, nonempty


def format_cmd_for_display(cmd):
    parts = []
    for item in cmd:
        if " " in item or "&" in item or "|" in item:
            parts.append(f"\"{item}\"")
        else:
            parts.append(item)
    return " ".join(parts)


def build_parser():
    parser = StrictArgumentParser(
        prog=SCRIPT_NAME,
        add_help=False,
        description="Thousands Minigames 实例部署流水线",
    )
    parser.add_argument("--config", "-c", dest="config", metavar="FILE", default=None, help="TOML 配置文件")
    parser.add_argument("--create-config", dest="create_config", action="store_true", default=False, help="将默认配置文件写入磁盘后退出")
    parser.add_argument("--instance", "-i", dest="instance", metavar="NAME", default=None, help="目标实例名")
    parser.add_argument("--all", dest="all_instances", action="store_true", default=False, help="批量部署所有合法存档")
    parser.add_argument("--overwrite", dest="overwrite", action="store_true", default=False, help="允许必要时备份后覆盖已有目标")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", default=False, help="仅显示执行计划，不实际调用子脚本")
    parser.add_argument("--skip-world-import", dest="skip_world", action="store_true", default=False, help="跳过导入存档")
    parser.add_argument("--skip-config-clone", dest="skip_config", action="store_true", default=False, help="跳过复制配置")
    parser.add_argument("--skip-startup-script", dest="skip_startup", action="store_true", default=False, help="跳过生成启动脚本")
    parser.add_argument("--no-input", dest="no_input", action="store_true", default=False, help="强制非交互模式")
    return parser


def run(argv):
    setup_stdio()

    if help_requested(argv):
        print_help()
        return EXIT_SUCCESS, False

    if sys.version_info < (3, 11):
        eprint("错误：Instances_Deploy_Pipeline.py 需要 Python 3.11 或更高版本。")
        eprint(f"当前 Python 版本：{sys.version.split()[0]}")
        eprint("原因：脚本依赖 Python 标准库 tomllib 解析 TOML 配置。")
        eprint("")
        return EXIT_CONFIG_ERROR, False

    if tomllib is None:
        eprint("错误：无法导入 Python 标准库 tomllib 。")
        eprint("请确认 Python 版本为 3.11 或更高版本。")
        eprint("")
        return EXIT_CONFIG_ERROR, False

    for required_script in (
        IMPORTER_SCRIPT_PATH,
        CONFIG_CLONER_SCRIPT_PATH,
        STARTUP_GENERATOR_SCRIPT_PATH,
    ):
        if not os.path.isfile(required_script):
            eprint(f"错误：找不到子脚本：{required_script}")
            eprint("")
            return EXIT_CONFIG_ERROR, False

    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except ScriptError as exc:
        eprint(exc.message)
        eprint("")
        return exc.exit_code, False

    if args.all_instances and args.instance is not None:
        eprint("错误：参数冲突：--all 和 --instance 不能同时使用。")
        eprint("")
        return EXIT_CONFIG_ERROR, False

    if args.skip_world and args.skip_config and args.skip_startup:
        eprint("错误：不能同时跳过所有三个步骤。")
        eprint("")
        return EXIT_CONFIG_ERROR, False

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
            "configs_root": resolve_path(BUILTIN_CONFIG["configs_root"], "dir", None, "builtin configs_root"),
            "template_root": resolve_path(BUILTIN_CONFIG["template_root"], "dir", None, "builtin template_root"),
            "output_dir": resolve_path(BUILTIN_CONFIG["output_dir"], "dir", None, "builtin output_dir"),
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

        def get_dir(cfg_key, builtin_value):
            if cfg_key in cfg:
                return resolve_path(cfg[cfg_key], "dir", config_dir, cfg_key)
            return builtin_value

        def get_file(cfg_key, builtin_value):
            if cfg_key in cfg:
                return resolve_path(cfg[cfg_key], "file", config_dir, cfg_key)
            return builtin_value

        archive_dir = get_dir("archive_dir", builtin["archive_dir"])
        world_dir = get_dir("world_dir", builtin["world_dir"])
        configs_root = get_dir("configs_root", builtin["configs_root"])
        template_root = get_dir("template_root", builtin["template_root"])
        output_dir = get_dir("output_dir", builtin["output_dir"])
        version_map = get_file("version_map", builtin["version_map"])

        ensure_dir_if_exists(archive_dir, "压缩包目录")
        ensure_dir_if_exists(world_dir, "世界目录")
        ensure_dir_if_exists(configs_root, "实例配置根目录")
        ensure_dir_if_exists(template_root, "模板配置根目录")
        ensure_dir_if_exists(output_dir, "启动脚本输出目录")

        version_map_data = load_version_map(version_map)

        if interactive_mode:
            oprint("提示：当前为交互模式。")
            oprint("提示：也可以使用命令行参数执行，使用 --help 可查看完整参数说明：")
            oprint(f"      .\\{SCRIPT_NAME} --help")
            oprint("")
            oprint("当前环境配置：")
            oprint(f"  压缩包目录: {archive_dir}")
            oprint(f"  世界根目录: {world_dir}")
            oprint(f"  实例配置根目录: {configs_root}")
            oprint(f"  模板根目录: {template_root}")
            oprint(f"  启动脚本输出目录: {output_dir}")
            oprint(f"  版本映射: {version_map}")
            oprint("")

        selected_instances = []
        if args.all_instances:
            selected_instances = list_valid_zip_instances(archive_dir, version_map_data)
            if not selected_instances:
                raise ScriptError(f"错误：在 {archive_dir} 中未找到任何合法存档压缩包。")
        elif args.instance is not None:
            instance = clean_instance_name(args.instance)
            actual_instance = find_actual_instance(archive_dir, instance)
            if actual_instance:
                instance = actual_instance
            selected_instances = [instance]
        else:
            if not interactive_mode:
                raise ScriptError(
                    "错误：缺少目标实例。\n"
                    "请提供 --instance 、--all ，或在未提供任何参数时进入交互模式。"
                )
            selected_instances = interactive_select_instances(archive_dir, version_map_data)

        results = {
            "success": [],
            "failed": [],
            "skipped": [],
        }
        canceled = False

        for instance in selected_instances:
            oprint("")
            oprint("=" * 60)
            oprint(f"开始处理实例: {instance}")
            oprint("=" * 60)
            oprint("")
            try:
                version_code = validate_instance_name(instance, version_map_data)
                mc_version = version_map_data[version_code]
                zip_path = ntpath.join(archive_dir.rstrip("\\"), f"{instance}.zip")

                if not os.path.isfile(zip_path):
                    oprint(f"[ERROR] 找不到对应的存档压缩包：{zip_path}")
                    results["failed"].append(instance)
                    continue

                world_target = resolve_path(ntpath.join(world_dir, instance), "dir", world_dir, "world target")
                config_target = resolve_path(ntpath.join(configs_root, instance), "dir", configs_root, "config target")
                bat_path = ntpath.join(output_dir.rstrip("\\"), f"{instance}.bat")

                world_exists, world_nonempty = inspect_dir(world_target)
                config_exists, config_nonempty = inspect_dir(config_target)
                if os.path.exists(bat_path) and not os.path.isfile(bat_path):
                    raise ScriptError(f"错误：启动脚本路径已存在但不是文件：{bat_path}")
                bat_exists = os.path.isfile(bat_path)

                oprint("部署计划：")
                oprint(f"  实例名: {instance}")
                oprint(f"  版本: {mc_version}")
                oprint(f"  压缩包: {zip_path}")
                oprint(f"  世界目标: {world_target}")
                oprint(f"  配置目标: {config_target}")
                oprint(f"  启动脚本: {bat_path}")
                oprint("")

                danger = (
                    (not args.skip_world and world_nonempty)
                    or (not args.skip_config and config_nonempty)
                    or (not args.skip_startup and bat_exists)
                )
                pass_overwrite = bool(args.overwrite)

                if danger and not pass_overwrite:
                    if args.dry_run:
                        oprint("[DRY-RUN] 检测到已有目标，假设用户同意覆盖。")
                        pass_overwrite = True
                    elif no_input or not interactive_mode:
                        oprint("[ERROR] 检测到已有目标且未提供 --overwrite ，跳过该实例。")
                        results["failed"].append(instance)
                        continue
                    else:
                        oprint("检测到已有目标。")
                        oprint("继续执行将允许各步骤在必要时备份后覆盖。")
                        if not confirm("是否继续部署此实例？[y/N] ", False):
                            oprint("[INFO] 用户跳过该实例。")
                            results["skipped"].append(instance)
                            continue
                        pass_overwrite = True

                importer_cmd = [
                    sys.executable,
                    IMPORTER_SCRIPT_PATH,
                    "--no-input",
                    "--instance", instance,
                    "--archive-dir", archive_dir,
                    "--world-dir", world_dir,
                    "--version-map", version_map,
                ]
                config_cloner_cmd = [
                    sys.executable,
                    CONFIG_CLONER_SCRIPT_PATH,
                    "--no-input",
                    "--instance", instance,
                    "--template-root", template_root,
                    "--configs-root", configs_root,
                    "--worlds-root", world_dir,
                    "--version-map", version_map,
                ]
                startup_generator_cmd = [
                    sys.executable,
                    STARTUP_GENERATOR_SCRIPT_PATH,
                    "--no-input",
                    "--instance", instance,
                    "--output-dir", output_dir,
                    "--configs-root", configs_root,
                    "--worlds-root", world_dir,
                    "--version-map", version_map,
                ]

                if pass_overwrite:
                    importer_cmd.append("--overwrite")
                    config_cloner_cmd.append("--overwrite")
                    startup_generator_cmd.append("--overwrite")

                steps = [
                    (1, "导入存档", importer_cmd, args.skip_world),
                    (2, "复制配置", config_cloner_cmd, args.skip_config),
                    (3, "生成启动脚本", startup_generator_cmd, args.skip_startup),
                ]

                instance_failed = False
                for step_no, title, cmd, skipped in steps:
                    if skipped:
                        oprint(f"[STEP {step_no}/3] 跳过 {title}")
                        continue
                    if args.dry_run:
                        oprint(f"[STEP {step_no}/3] [DRY-RUN] 将执行: {title}")
                        oprint(f"  命令: {format_cmd_for_display(cmd)}")
                        continue
                    oprint(f"[STEP {step_no}/3] {title}")
                    try:
                        completed = subprocess.run(cmd)
                    except Exception as exc:
                        oprint(f"[ERROR] 无法执行 {title}\n详情：{exc}")
                        instance_failed = True
                        break
                    if completed.returncode == EXIT_SUCCESS:
                        oprint(f"[STEP {step_no}/3] {title}完成")
                    elif completed.returncode == EXIT_CANCEL:
                        oprint(f"[ERROR] {title}被取消。")
                        canceled = True
                        break
                    else:
                        oprint(f"[ERROR] {title}失败，退出码：{completed.returncode}")
                        instance_failed = True
                        break

                if canceled:
                    break

                if instance_failed:
                    results["failed"].append(instance)
                else:
                    results["success"].append(instance)
                    oprint("")
                    oprint(f"[INFO] 实例 {instance} 处理完成。")

            except UserCancel:
                canceled = True
                break
            except ScriptError as exc:
                oprint(exc.message)
                results["failed"].append(instance)
            except Exception as exc:
                oprint(f"错误：发生未预期异常。\n详情：{exc}")
                results["failed"].append(instance)

        if len(selected_instances) > 1:
            oprint("")
            oprint("=" * 60)
            oprint("部署汇总：")
            oprint(f"  成功: {len(results['success'])}")
            oprint(f"  跳过: {len(results['skipped'])}")
            oprint(f"  失败: {len(results['failed'])}")
            oprint("=" * 60)
            oprint("")

        if canceled:
            return EXIT_CANCEL, no_input
        if results["failed"]:
            return EXIT_RUNTIME_ERROR, no_input
        if results["success"]:
            return EXIT_SUCCESS, no_input
        return EXIT_CANCEL, no_input

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
