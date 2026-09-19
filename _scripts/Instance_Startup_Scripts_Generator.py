#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Instance_Startup_Scripts_Generator

用于根据 Thousands Minigames 实例目录生成 Paper 服务端启动脚本。
"""

import sys
import os
import ntpath
import re
import argparse
import shutil
from datetime import datetime

try:
    import tomllib
except ImportError:
    tomllib = None


EXIT_SUCCESS = 0
EXIT_CANCEL = 1
EXIT_CONFIG_ERROR = 2
EXIT_RUNTIME_ERROR = 3

SCRIPT_NAME = "Instance_Startup_Scripts_Generator.py"
CONFIG_FILE_NAME = "Instance_Startup_Scripts_Generator.toml"
VERSION_MAP_FILE_NAME = "Version_Map.toml"

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
    "output_dir": os.path.join(BASE_DIR, "_startup_scripts_legacy") + "\\",
    "configs_root": os.path.join(BASE_DIR, "configs") + "\\",
    "worlds_root": os.path.join(BASE_DIR, "worlds") + "\\",
    "version_map": DEFAULT_VERSION_MAP,
    "java_runtime": ".\\runtimes\\zulu-25\\bin\\java.exe",
    "xms": "6144M",
    "xmx": "6144M",
    "backup_dir": os.path.join(BASE_DIR, "_startup_scripts_legacy", "_backups") + "\\",
}

TOML_ALLOWED_CONFIG_KEYS = {
    "output_dir",
    "configs_root",
    "worlds_root",
    "version_map",
    "java_runtime",
    "xms",
    "xmx",
    "backup_dir",
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

JVM_ARGS = [
    "--add-modules=jdk.incubator.vector",
    "-XX:+UseG1GC",
    "-XX:+ParallelRefProcEnabled",
    "-XX:MaxGCPauseMillis=200",
    "-XX:+UnlockExperimentalVMOptions",
    "-XX:+DisableExplicitGC",
    "-XX:+AlwaysPreTouch",
    "-XX:G1NewSizePercent=30",
    "-XX:G1MaxNewSizePercent=40",
    "-XX:G1HeapRegionSize=8M",
    "-XX:G1ReservePercent=20",
    "-XX:G1HeapWastePercent=5",
    "-XX:G1MixedGCCountTarget=4",
    "-XX:InitiatingHeapOccupancyPercent=15",
    "-XX:G1MixedGCLiveThresholdPercent=90",
    "-XX:G1RSetUpdatingPauseTimePercent=5",
    "-XX:SurvivorRatio=32",
    "-XX:+PerfDisableSharedMem",
    "-XX:MaxTenuringThreshold=1",
    "-Xlog:gc*:logs/gc.log:time,uptime:filecount=5,filesize=1M",
    "-Dusing.aikars.flags=https://mcflags.emc.gs",
    "-Daikars.new.flags=true",
    "-Dfile.encoding=UTF-8",
    "-DPaper.IgnoreJavaVersion=true",
]

NOGUI_MIN_VERSION = (1, 15, 2)
PAPER_SETTINGS_DIR_MIN_VERSION = (1, 19, 2)

HELP_TEXT = r"""
Instance_Startup_Scripts_Generator

用途：
  根据 Thousands Minigames 的实例目录生成 Paper 服务端启动脚本。

运行环境：
  Windows 命令行。
  需要 Python 3.11 或更高版本。

用法：
  .\Instance_Startup_Scripts_Generator.py
  .\Instance_Startup_Scripts_Generator.py --create-config
  .\Instance_Startup_Scripts_Generator.py --instance 12111_TM_Example
  .\Instance_Startup_Scripts_Generator.py --instance 12111_TM_Example --overwrite
  .\Instance_Startup_Scripts_Generator.py --no-input --instance 12111_TM_Example

参数：
  --help, -h, -H, -?, -help
      显示帮助信息并退出。

  --create-config
      将默认配置文件写入磁盘后退出，不执行后续业务流程。

  --config, -c
      TOML 配置文件。

  --instance, -i
      目标实例名。

  --output-dir
      启动脚本输出目录。

  --configs-root
      实例配置根目录。

  --worlds-root
      世界根目录。

  --version-map
      版本映射文件。

  --java-runtime
      Java 运行时路径，原样嵌入 .bat 。

  --xms
      JVM 初始内存。

  --xmx
      JVM 最大内存。

  --backup-dir
      启动脚本备份目录。

  --overwrite
      目标 .bat 已存在时备份后覆盖。

  --no-input
      强制非交互模式。

配置文件：
  默认配置文件：
      {脚本所在目录}\_Configs\Instance_Startup_Scripts_Generator.toml

  默认配置文件可能尚未写入磁盘。
  未写入磁盘不代表配置不存在。
  脚本会使用完整内置默认配置继续运行。

  使用 --create-config 可将默认配置文件写入磁盘。

危险操作确认：
  目标启动脚本已存在时使用 [y/N] 。
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


def normalize_embedded_runtime(raw, param_name="--java-runtime"):
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

    if text.endswith("\\"):
        raise ScriptError(
            f"参数类型冲突：{param_name} 期望文件路径，但输入以路径分隔符结尾。\n"
            f"输入：{raw}\n"
            "说明：末尾带路径分隔符的路径必须视为文件夹。"
        )

    return text


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


def make_relative_dir(target_dir, config_dir):
    target = target_dir.rstrip("\\")

    try:
        rel = os.path.relpath(target, config_dir)
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


def make_relative_file(target_file, config_dir):
    target = target_file.rstrip("\\")

    try:
        rel = os.path.relpath(target, config_dir)
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
        "# Instance_Startup_Scripts_Generator 配置",
        "# 相对路径相对于本 TOML 文件所在目录解析。",
        "",
        "# 启动脚本输出目录。目录路径。",
        f'output_dir = "{escape_toml(make_relative_dir(BUILTIN_CONFIG["output_dir"], config_dir))}"',
        "",
        "# 实例配置根目录。目录路径。",
        f'configs_root = "{escape_toml(make_relative_dir(BUILTIN_CONFIG["configs_root"], config_dir))}"',
        "",
        "# 世界根目录。目录路径。",
        f'worlds_root = "{escape_toml(make_relative_dir(BUILTIN_CONFIG["worlds_root"], config_dir))}"',
        "",
        "# 版本映射文件。文件路径。",
        f'version_map = "{escape_toml(make_relative_file(BUILTIN_CONFIG["version_map"], config_dir))}"',
        "",
        "# Java 运行时路径。原样嵌入 .bat 。",
        f'java_runtime = "{escape_toml(BUILTIN_CONFIG["java_runtime"])}"',
        "",
        "# JVM 初始内存。",
        f'xms = "{escape_toml(BUILTIN_CONFIG["xms"])}"',
        "",
        "# JVM 最大内存。",
        f'xmx = "{escape_toml(BUILTIN_CONFIG["xmx"])}"',
        "",
        "# 启动脚本备份目录。目录路径。",
        f'backup_dir = "{escape_toml(make_relative_dir(BUILTIN_CONFIG["backup_dir"], config_dir))}"',
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

    unknown_keys = sorted(set(data.keys()) - TOML_ALLOWED_CONFIG_KEYS)
    if unknown_keys:
        raise ScriptError(f"错误：TOML 配置中存在未知字段：{', '.join(unknown_keys)}\n文件：{path}")

    for key in TOML_ALLOWED_CONFIG_KEYS:
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

    if name.lower().endswith(".bat"):
        name = name[:-4]

    name = name.strip()

    if "/" in name or "\\" in name:
        raise ScriptError(f"错误：--instance 只能是实例名，不能包含路径分隔符。\n输入：{raw}")

    return name


def parse_version(version_str):
    if not isinstance(version_str, str) or not version_str.strip():
        raise ScriptError(f"错误：版本号必须是非空字符串：{version_str}")

    try:
        return tuple(int(part) for part in version_str.strip().split("."))
    except Exception:
        raise ScriptError(f"错误：无法解析版本号：{version_str}")


def list_instances(worlds_root, version_map):
    worlds_no = worlds_root.rstrip("\\")

    if not os.path.isdir(worlds_no):
        return []

    try:
        entries = os.scandir(worlds_no)
    except OSError as exc:
        raise ScriptError(f"错误：无法读取世界目录：{worlds_root}\n详情：{exc}")

    names = []

    with entries:
        for entry in entries:
            if entry.name.startswith("_"):
                continue

            if not entry.is_dir(follow_symlinks=False):
                continue

            try:
                validate_instance_name(entry.name, version_map)
                names.append(entry.name)
            except ScriptError:
                continue

    return sorted(names)


def interactive_select(worlds_root, version_map):
    while True:
        instances = list_instances(worlds_root, version_map)

        if instances:
            oprint("")
            oprint("=== 可选择的实例列表 ===")
            for idx, name in enumerate(instances, 1):
                oprint(f"{idx}. {name}")

            oprint("")
            oprint("可用操作：输入序号选择，或直接输入实例名。")
            oprint("可用控制：输入 r 重新搜索，输入 c 取消。")
            oprint("")

            prompt = "请输入序号或实例名: "
        else:
            oprint("")
            oprint(f"[WARN] 在 {worlds_root} 中未找到任何合法实例目录。")
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

            if low.endswith(".bat"):
                raw = raw[:-4]

            if raw.isdigit() and instances:
                idx = int(raw)

                if 1 <= idx <= len(instances):
                    return instances[idx - 1]

                oprint(f"[WARN] 序号超出范围 (1-{len(instances)}) 。")
                continue

            instance = raw

            try:
                validate_instance_name(instance, version_map)
            except ScriptError as exc:
                oprint(exc.message)
                oprint("")
                continue

            if instance in instances:
                return instance

            oprint("")
            oprint(f"[WARN] 未在 {worlds_root} 中找到实例目录：{instance}")
            oprint("       将继续使用该实例名生成启动脚本。")
            oprint("")

            return instance


def confirm_overwrite(target_path):
    oprint("")
    oprint(f"[WARNING] 目标启动脚本已存在: \"{target_path}\"")
    oprint("继续执行将备份现有文件并覆盖。")

    try:
        answer = input("是否继续？[y/N] ").strip().lower()
    except EOFError:
        return False

    return answer in ("y", "yes")


def backup_bat(src, backup_dir):
    backup_dir_no = backup_dir.rstrip("\\")

    try:
        os.makedirs(backup_dir_no, exist_ok=True)
    except OSError as exc:
        raise RuntimeScriptError(f"错误：无法创建备份目录：{backup_dir}\n详情：{exc}")

    fn = os.path.basename(src)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = os.path.join(backup_dir_no, f"{fn}.bak.{timestamp}")

    counter = 1
    original_backup_path = backup_path

    while os.path.exists(backup_path):
        backup_path = f"{original_backup_path}-{counter:03d}"
        counter += 1

    try:
        shutil.copy2(src, backup_path)
    except Exception as exc:
        raise RuntimeScriptError(f"错误：备份启动脚本失败。\n原文件：{src}\n备份文件：{backup_path}\n详情：{exc}")

    return backup_path


def generate_bat(instance_name, mc_version, java_runtime, xms, xmx):
    vt = parse_version(mc_version)
    paper_jar = f"paper-{mc_version}.jar"

    lines = []
    lines.append("@echo off")
    lines.append("chcp 65001 >nul")
    lines.append('cd /d "%~dp0.."')
    lines.append(f"title {instance_name}")
    lines.append(f'if not exist ".\\configs\\{instance_name}\\" mkdir ".\\configs\\{instance_name}\\"')

    p = []
    p.append(f'"{java_runtime}"')
    p.append(f"-Xms{xms}")
    p.append(f"-Xmx{xmx}")
    p.extend(JVM_ARGS)
    p.append(f'-jar ".\\{paper_jar}"')

    if vt >= NOGUI_MIN_VERSION:
        p.append("--nogui")

    p.append("--world-dir worlds")
    p.append("--plugins plugins")
    p.append(f"--config configs\\{instance_name}\\server.properties")
    p.append(f"--commands-settings configs\\{instance_name}\\commands.yml")
    p.append(f"--bukkit-settings configs\\{instance_name}\\bukkit.yml")
    p.append(f"--spigot-settings configs\\{instance_name}\\spigot.yml")

    if vt >= PAPER_SETTINGS_DIR_MIN_VERSION:
        p.append(f"--paper-settings-directory configs\\{instance_name}\\")
    else:
        p.append(f"--paper-settings configs\\{instance_name}\\paper.yml")

    p.append(f"--level-name {instance_name}")

    lines.append(" ".join(p))
    lines.append("pause")

    return "\r\n".join(lines) + "\r\n"


def build_parser():
    parser = StrictArgumentParser(
        prog=SCRIPT_NAME,
        add_help=False,
        description="Thousands Minigames 实例启动脚本生成工具",
    )

    parser.add_argument("--config", "-c", dest="config", metavar="FILE", default=None, help="TOML 配置文件")
    parser.add_argument("--create-config", dest="create_config", action="store_true", default=False, help="将默认配置文件写入磁盘后退出")
    parser.add_argument("--instance", "-i", dest="instance", metavar="NAME", default=None, help="目标实例名")
    parser.add_argument("--output-dir", dest="output_dir", metavar="DIR", default=None, help="启动脚本输出目录")
    parser.add_argument("--configs-root", dest="configs_root", metavar="DIR", default=None, help="实例配置根目录")
    parser.add_argument("--worlds-root", dest="worlds_root", metavar="DIR", default=None, help="世界根目录")
    parser.add_argument("--version-map", dest="version_map", metavar="FILE", default=None, help="版本映射文件")
    parser.add_argument("--java-runtime", dest="java_runtime", metavar="PATH", default=None, help="Java 运行时路径")
    parser.add_argument("--xms", dest="xms", metavar="SIZE", default=None, help="JVM 初始内存")
    parser.add_argument("--xmx", dest="xmx", metavar="SIZE", default=None, help="JVM 最大内存")
    parser.add_argument("--backup-dir", dest="backup_dir", metavar="DIR", default=None, help="启动脚本备份目录")
    parser.add_argument("--overwrite", dest="overwrite", action="store_true", default=False, help="目标已存在时备份后覆盖")
    parser.add_argument("--no-input", dest="no_input", action="store_true", default=False, help="强制非交互模式")

    return parser


def run(argv):
    setup_stdio()

    if help_requested(argv):
        print_help()
        return EXIT_SUCCESS, False

    if sys.version_info < (3, 11):
        eprint("错误：Instance_Startup_Scripts_Generator.py 需要 Python 3.11 或更高版本。")
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
            "output_dir": resolve_path(BUILTIN_CONFIG["output_dir"], "dir", None, "builtin output_dir"),
            "configs_root": resolve_path(BUILTIN_CONFIG["configs_root"], "dir", None, "builtin configs_root"),
            "worlds_root": resolve_path(BUILTIN_CONFIG["worlds_root"], "dir", None, "builtin worlds_root"),
            "version_map": resolve_path(BUILTIN_CONFIG["version_map"], "file", None, "builtin version_map"),
            "backup_dir": resolve_path(BUILTIN_CONFIG["backup_dir"], "dir", None, "builtin backup_dir"),
            "java_runtime": BUILTIN_CONFIG["java_runtime"],
            "xms": BUILTIN_CONFIG["xms"],
            "xmx": BUILTIN_CONFIG["xmx"],
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

        config_dir = os.path.dirname(os.path.abspath(config_file)) if config_file else CONFIG_DIR
        if not config_dir.endswith("\\"):
            config_dir += "\\"

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

        output_dir = resolve_dir(args.output_dir, "output_dir", builtin["output_dir"], "--output-dir")
        configs_root = resolve_dir(args.configs_root, "configs_root", builtin["configs_root"], "--configs-root")
        worlds_root = resolve_dir(args.worlds_root, "worlds_root", builtin["worlds_root"], "--worlds-root")
        version_map = resolve_file(args.version_map, "version_map", builtin["version_map"], "--version-map")
        backup_dir = resolve_dir(args.backup_dir, "backup_dir", builtin["backup_dir"], "--backup-dir")

        java_runtime_raw = args.java_runtime
        if java_runtime_raw is None:
            java_runtime_raw = cfg.get("java_runtime", builtin["java_runtime"])

        java_runtime = normalize_embedded_runtime(java_runtime_raw, "--java-runtime / java_runtime")

        xms_raw = args.xms
        if xms_raw is None:
            xms_raw = cfg.get("xms", builtin["xms"])

        xmx_raw = args.xmx
        if xmx_raw is None:
            xmx_raw = cfg.get("xmx", builtin["xmx"])

        xms = str(xms_raw).strip()
        xmx = str(xmx_raw).strip()

        if not xms:
            raise ScriptError("错误：xms 不能为空。")

        if not xmx:
            raise ScriptError("错误：xmx 不能为空。")

        ensure_dir_if_exists(output_dir, "启动脚本输出目录")
        ensure_dir_if_exists(configs_root, "实例配置根目录")
        ensure_dir_if_exists(worlds_root, "世界目录")
        ensure_dir_if_exists(backup_dir, "启动脚本备份目录")

        version_map_data = load_version_map(version_map)

        if interactive_mode:
            oprint("提示：当前为交互模式。")
            oprint("提示：也可以使用命令行参数执行，使用 --help 可查看完整参数说明：")
            oprint(f"      .\\{SCRIPT_NAME} --help")
            oprint("")

            oprint("当前环境配置：")
            oprint(f"  启动脚本输出目录: {output_dir}")
            oprint(f"  实例配置根目录: {configs_root}")
            oprint(f"  世界根目录: {worlds_root}")
            oprint(f"  版本映射: {version_map}")
            oprint("")

        instance = clean_instance_name(args.instance) if args.instance else None

        if not instance:
            if not interactive_mode:
                raise ScriptError(
                    "错误：缺少目标实例。\n"
                    "请提供 --instance ，或在未提供任何参数时进入交互模式。"
                )

            instance = interactive_select(worlds_root, version_map_data)

        version_code = validate_instance_name(instance, version_map_data)
        mc_version = version_map_data[version_code]

        bat_content = generate_bat(instance, mc_version, java_runtime, xms, xmx)

        output_dir_no = output_dir.rstrip("\\")

        try:
            os.makedirs(output_dir_no, exist_ok=True)
        except OSError as exc:
            raise RuntimeScriptError(f"错误：无法创建启动脚本输出目录：{output_dir}\n详情：{exc}")

        bat_path = os.path.join(output_dir_no, f"{instance}.bat")

        if os.path.exists(bat_path) and not os.path.isfile(bat_path):
            raise ScriptError(f"错误：目标启动脚本路径已存在但不是文件：{bat_path}")

        backup_path = None

        if os.path.exists(bat_path):
            if not args.overwrite:
                if not interactive_mode:
                    raise ScriptError(
                        "错误：目标启动脚本已存在且未提供 --overwrite 。\n"
                        f"路径：{bat_path}\n"
                        "非交互模式下必须提供 --overwrite 才允许覆盖。"
                    )

                if not confirm_overwrite(bat_path):
                    raise UserCancel()

            backup_path = backup_bat(bat_path, backup_dir)
            oprint(f"[INFO] 已备份原启动脚本: \"{backup_path}\"")

        try:
            with open(bat_path, "w", encoding="utf-8", newline="") as f:
                f.write(bat_content)
        except Exception as exc:
            if backup_path is not None:
                try:
                    if os.path.exists(bat_path):
                        os.remove(bat_path)
                except OSError:
                    pass

                try:
                    shutil.copy2(backup_path, bat_path)
                except Exception:
                    raise RuntimeScriptError(f"错误：写入启动脚本失败且恢复备份失败。\n备份保留：{backup_path}")

                raise RuntimeScriptError(f"错误：写入启动脚本失败，已恢复原启动脚本。\n详情：{exc}")

            try:
                if os.path.exists(bat_path):
                    os.remove(bat_path)
            except OSError:
                pass

            raise RuntimeScriptError(f"错误：写入启动脚本失败。\n详情：{exc}")

        oprint("")
        oprint(f"[INFO] 已生成启动脚本: \"{bat_path}\"")
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
