#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Instance_Configs_Cloner

用于将 Thousands Minigames 模板配置复制到目标实例配置目录。
"""

import sys
import os
import ntpath
import re
import argparse
import shutil
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

SCRIPT_NAME = "Instance_Configs_Cloner.py"
CONFIG_FILE_NAME = "Instance_Configs_Cloner.toml"
VERSION_MAP_FILE_NAME = "Version_Map.toml"
TEMPLATE_SUFFIX = "TM_Example"

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
    "template_root": os.path.join(SCRIPT_DIR, "TM_Example_Configs", "configs") + "\\",
    "configs_root": os.path.join(BASE_DIR, "configs") + "\\",
    "worlds_root": os.path.join(BASE_DIR, "worlds") + "\\",
    "version_map": DEFAULT_VERSION_MAP,
}

VERSION_MAP = {}

VERSION_CODE_RE = re.compile(r"^[0-9]{5}$")
NAME_RE = re.compile(r"^[0-9]{5}_[A-Za-z0-9_-]+$")

HELP_ARGS = {
    "-h",
    "-H",
    "-?",
    "-help",
    "--help",
}

TOML_ALLOWED_TOP_KEYS = {
    "template_root",
    "configs_root",
    "worlds_root",
    "version_map",
    "instance_name",
    "template_name",
    "interactive",
}

TOML_ALLOWED_INTERACTIVE_KEYS = {
    "show_paths",
}

HELP_TEXT = r"""
Instance_Configs_Cloner

用途：
  将 Thousands Minigames 模板配置复制到目标实例配置目录。

运行环境：
  Windows 命令行。
  需要 Python 3.11 或更高版本。

版本映射：
  默认读取脚本同目录的 _Configs\Version_Map.toml 。
  可通过 --version-map 或 TOML 字段 version_map 指定其他文件。

用法：
  .\Instance_Configs_Cloner.py
  .\Instance_Configs_Cloner.py --create-config
  .\Instance_Configs_Cloner.py --instance 10808_Bed_Wars
  .\Instance_Configs_Cloner.py --instance 10808_Bed_Wars --overwrite
  .\Instance_Configs_Cloner.py --no-input --instance 10808_Bed_Wars --overwrite

参数：
  --help, -h, -H, -?, -help
      显示帮助信息并退出。

  --create-config
      将默认配置文件写入磁盘后退出，不执行后续业务流程。
      若未提供 --config，写入默认配置文件路径。
      若提供 --config，写入指定文件路径。
      已存在的配置文件不会被覆盖。

  --config, -c
      TOML 配置文件。
      类型：文件路径。
      支持绝对路径和相对路径。
      若路径末尾带 \ 或 / ，将视为文件夹语义并报错。

  --version-map
      版本映射文件。

  --template-root, -T
      模板配置根目录。

  --configs-root
      实例配置根目录。

  --worlds-root
      世界根目录，用于交互模式下扫描实例列表。

  --instance, -i
      目标实例名。

  --template, -t
      模板名。

  --source, -s
      直接指定源目录。

  --target, -o
      直接指定目标目录。

  --overwrite
      允许备份后覆盖非空目标目录。

  --no-input
      强制非交互模式。

配置文件：
  默认配置文件：
      {脚本所在目录}\_Configs\Instance_Configs_Cloner.toml

  默认配置文件可能尚未写入磁盘。
  未写入磁盘不代表配置不存在。
  脚本会使用完整内置默认配置继续运行。

  使用 --create-config 可将默认配置文件写入磁盘。

配置优先级：
  CLI > TOML > BUILTIN_CONFIG

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


def normalize_path(raw, path_type, base_dir=None):
    if raw is None:
        return None

    if not isinstance(raw, str):
        raise ScriptError("错误：路径必须是字符串。")

    text = raw.strip()
    if not text:
        raise ScriptError("错误：路径不能为空。")

    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("\"", "'"):
        text = text[1:-1]

    text = text.replace("/", "\\")
    trailing = text.endswith("\\")

    if path_type == "file" and trailing:
        raise ScriptError(
            "错误：文件型路径末尾不得带路径分隔符。\n"
            f"输入：{raw}\n"
            "说明：末尾带 / 或反斜杠的输入必须视为文件夹语义，但该参数要求文件路径。"
        )

    if path_type not in ("file", "dir"):
        raise ScriptError(f"错误：内部路径类型不合法：{path_type}")

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


def validate_instance_name(name):
    return _validate_name(name, "实例名")


def validate_template_name(name):
    return _validate_name(name, "模板名")


def _validate_name(name, kind):
    if not isinstance(name, str):
        raise ScriptError(f"错误：{kind}必须是字符串。")

    value = name.strip()
    if not value:
        raise ScriptError(f"错误：{kind}不能为空。")

    if not value.isascii():
        raise ScriptError(
            f"错误：{kind}包含非 ASCII 字符：{value}\n"
            "仅允许 ASCII 字母、数字、下划线 _ 、连字符 - 。"
        )

    if not NAME_RE.fullmatch(value):
        raise ScriptError(
            f"错误：{kind}格式不合法：{value}\n"
            "要求：{5位版本代码}_{名称}\n"
            "名称仅允许 ASCII 字母、数字、下划线 _ 、连字符 - 。\n"
            "合法示例：10808_Bed_Wars、12111_Cool_Parkour、26012_Murder_Mystery"
        )

    code = value[:5]
    if code not in VERSION_MAP:
        raise ScriptError(
            f"错误：{kind}版本代码 {code} 不在版本映射表中。\n"
            f"名称：{value}\n"
            "请检查版本代码是否来自 Version_Map.toml 。"
        )

    return code


def get_last_segment(path):
    p = path.replace("/", "\\").rstrip("\\")
    if not p:
        return ""
    return ntpath.basename(p)


def validate_source_path(source_dir):
    name = get_last_segment(source_dir)
    if not name:
        raise ScriptError(f"错误：无法从源目录路径中提取模板名：{source_dir}")
    validate_template_name(name)
    return name


def validate_target_path(target_dir):
    name = get_last_segment(target_dir)
    if not name:
        raise ScriptError(f"错误：无法从目标目录路径中提取实例名：{target_dir}")
    validate_instance_name(name)
    return name


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
    if not child or not parent:
        return False
    return _compare_path(child).startswith(_compare_path(parent))


def escape_toml_string(value):
    return value.replace("\\", "\\\\").replace('"', '\\"')


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


def create_default_config_atomic(config_path):
    config_path = os.path.abspath(config_path)
    config_dir = os.path.dirname(config_path)

    if config_dir:
        try:
            os.makedirs(config_dir, exist_ok=True)
        except OSError as exc:
            raise RuntimeScriptError(f"错误：无法创建配置文件目录：{config_dir}\n详情：{exc}")

    template_root_rel = make_relative_dir(BUILTIN_CONFIG["template_root"], config_dir)
    configs_root_rel = make_relative_dir(BUILTIN_CONFIG["configs_root"], config_dir)
    worlds_root_rel = make_relative_dir(BUILTIN_CONFIG["worlds_root"], config_dir)
    version_map_rel = make_relative_file(BUILTIN_CONFIG["version_map"], config_dir)

    content = (
        "# Thousands Minigames\n"
        "# Instance_Configs_Cloner 配置\n"
        "# 相对路径相对于本 TOML 文件所在目录解析。\n"
        "\n"
        "# 模板配置根目录。目录路径。\n"
        f'template_root = "{escape_toml_string(template_root_rel)}"\n'
        "\n"
        "# 实例配置根目录。目录路径。\n"
        f'configs_root = "{escape_toml_string(configs_root_rel)}"\n'
        "\n"
        "# 世界根目录。目录路径。\n"
        f'worlds_root = "{escape_toml_string(worlds_root_rel)}"\n'
        "\n"
        "# 版本映射文件。文件路径。\n"
        f'version_map = "{escape_toml_string(version_map_rel)}"\n'
        "\n"
        "# 目标实例名。留空表示未设置。\n"
        'instance_name = ""\n'
        "\n"
        "# 模板名。留空表示未设置。\n"
        'template_name = ""\n'
        "\n"
        "[interactive]\n"
        "# 是否在交互模式开始时显示当前环境配置。\n"
        "show_paths = true\n"
    )

    temp_path = config_path + ".tmp"

    try:
        with open(temp_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)

        if tomllib is not None:
            with open(temp_path, "rb") as f:
                tomllib.load(f)

        if os.path.exists(config_path):
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            bp = f"{config_path}.bak.{ts}"
            n = 1
            orig = bp
            while os.path.exists(bp):
                bp = f"{orig}-{n:03d}"
                n += 1
            shutil.copy2(config_path, bp)
            oprint(f"[INFO] 已备份原配置文件: {bp}")

        os.replace(temp_path, config_path)

    except Exception as exc:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

        raise RuntimeScriptError(f"错误：无法生成或验证默认配置文件：{config_path}\n详情：{exc}")


def load_toml_file(path):
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

    unknown_top_keys = sorted(set(data.keys()) - TOML_ALLOWED_TOP_KEYS)
    if unknown_top_keys:
        raise ScriptError(f"错误：TOML 中存在未知顶层字段：{', '.join(unknown_top_keys)}\n文件：{path}")

    base_dir = os.path.dirname(os.path.abspath(path))
    if not base_dir.endswith("\\"):
        base_dir += "\\"

    result = {"interactive": {}}

    for key in ("template_root", "configs_root", "worlds_root"):
        if key in data:
            value = data[key]
            if not isinstance(value, str):
                raise ScriptError(f"错误：TOML 字段 {key} 必须是字符串目录路径。\n文件：{path}")
            result[key] = normalize_path(value, "dir", base_dir)

    if "version_map" in data:
        value = data["version_map"]
        if not isinstance(value, str):
            raise ScriptError(f"错误：TOML 字段 version_map 必须是字符串文件路径。\n文件：{path}")
        if not value.strip():
            raise ScriptError(f"错误：TOML 字段 version_map 不能为空。\n文件：{path}")
        result["version_map"] = normalize_path(value, "file", base_dir)

    for key in ("instance_name", "template_name"):
        if key in data:
            value = data[key]
            if not isinstance(value, str):
                raise ScriptError(f"错误：TOML 字段 {key} 必须是字符串。\n文件：{path}")
            result[key] = value.strip()

    if "interactive" in data:
        inter_data = data["interactive"]

        if not isinstance(inter_data, dict):
            raise ScriptError(f"错误：TOML 中的 [interactive] 必须是键值表。\n文件：{path}")

        unknown_inter_keys = sorted(set(inter_data.keys()) - TOML_ALLOWED_INTERACTIVE_KEYS)
        if unknown_inter_keys:
            raise ScriptError(f"错误：TOML [interactive] 中存在未知字段：{', '.join(unknown_inter_keys)}\n文件：{path}")

        if "show_paths" in inter_data:
            value = inter_data["show_paths"]
            if not isinstance(value, bool):
                raise ScriptError(f"错误：TOML [interactive] 字段 show_paths 必须是布尔值 true 或 false 。\n文件：{path}")
            result["interactive"]["show_paths"] = value

    return result, set(data.keys())


def build_builtin_config():
    return {
        "template_root": normalize_path(BUILTIN_CONFIG["template_root"], "dir", SCRIPT_DIR),
        "configs_root": normalize_path(BUILTIN_CONFIG["configs_root"], "dir", SCRIPT_DIR),
        "worlds_root": normalize_path(BUILTIN_CONFIG["worlds_root"], "dir", SCRIPT_DIR),
        "version_map": normalize_path(BUILTIN_CONFIG["version_map"], "file", SCRIPT_DIR),
    }


def build_parser():
    parser = StrictArgumentParser(
        prog=SCRIPT_NAME,
        add_help=False,
        description="Thousands Minigames 实例配置复制工具",
    )

    parser.add_argument("--config", "-c", dest="config", metavar="FILE", default=None, help="TOML 配置文件")
    parser.add_argument("--create-config", dest="create_config", action="store_true", default=False, help="将默认配置文件写入磁盘后退出")
    parser.add_argument("--version-map", dest="version_map", metavar="FILE", default=None, help="版本映射文件")
    parser.add_argument("--template-root", "-T", dest="template_root", metavar="DIR", default=None, help="模板配置根目录")
    parser.add_argument("--configs-root", dest="configs_root", metavar="DIR", default=None, help="实例配置根目录")
    parser.add_argument("--worlds-root", dest="worlds_root", metavar="DIR", default=None, help="世界根目录")
    parser.add_argument("--instance", "-i", dest="instance", metavar="NAME", default=None, help="目标实例名")
    parser.add_argument("--template", "-t", dest="template", metavar="NAME", default=None, help="模板名")
    parser.add_argument("--source", "-s", dest="source", metavar="DIR", default=None, help="直接指定源目录")
    parser.add_argument("--target", "-o", dest="target", metavar="DIR", default=None, help="直接指定目标目录")
    parser.add_argument("--overwrite", dest="overwrite", action="store_true", default=False, help="允许备份后覆盖非空目标目录")
    parser.add_argument("--no-input", dest="no_input", action="store_true", default=False, help="强制非交互模式")

    return parser


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


def list_world_instances(worlds_root):
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
                validate_instance_name(entry.name)
                names.append(entry.name)
            except ScriptError:
                continue

    return sorted(names)


def interactive_select_instance(worlds_root):
    while True:
        instances = list_world_instances(worlds_root)

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

            if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("\"", "'"):
                raw = raw[1:-1]

            if raw.isdigit() and instances:
                idx = int(raw)

                if 1 <= idx <= len(instances):
                    return instances[idx - 1]

                oprint(f"[WARN] 序号超出范围 (1-{len(instances)}) 。")
                continue

            instance = raw

            try:
                validate_instance_name(instance)
            except ScriptError as exc:
                oprint(exc.message)
                oprint("")
                continue

            if instance in instances:
                return instance

            oprint("")
            oprint(f"[WARN] 未在 {worlds_root} 中找到实例目录：{instance}")
            oprint("       将继续使用该实例名。")
            oprint("")

            return instance


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


def authorize_nonempty_target(target_dir, overwrite, no_input, interactive_mode):
    if overwrite:
        return

    if no_input:
        raise ScriptError(
            "错误：目标目录已存在且非空。\n"
            f"路径：{target_dir}\n"
            "非交互模式下必须提供 --overwrite 才允许覆盖。"
        )

    if not interactive_mode:
        raise ScriptError(
            "错误：目标目录已存在且非空。\n"
            f"路径：{target_dir}\n"
            "如需覆盖，请使用 --overwrite 。"
        )

    oprint("")
    oprint("目标目录已存在且非空：")
    oprint(target_dir)
    oprint("")
    oprint("即将备份后覆盖该目录。")

    if not confirm("是否继续？[y/N] ", False):
        raise UserCancel()


def resolve_target(target_dir, instance_name, configs_root):
    if target_dir is not None:
        final_instance = validate_target_path(target_dir)
        return final_instance, target_dir

    if not instance_name:
        raise ScriptError(
            "错误：缺少目标实例。\n"
            "请提供 --instance 、--target ，或在 TOML 中配置 instance_name 。\n"
            "也可以在不提供任何参数时进入交互模式。"
        )

    validate_instance_name(instance_name)

    if not configs_root:
        raise ScriptError("错误：缺少实例配置根目录。")

    configs_root_no = configs_root.rstrip("\\")
    if os.path.exists(configs_root_no) and not os.path.isdir(configs_root_no):
        raise ScriptError(f"错误：实例配置根目录存在但不是目录：{configs_root}")

    target = normalize_path(ntpath.join(configs_root, instance_name), "dir", configs_root)

    return instance_name, target


def resolve_source(source_dir, template_name, template_root, final_instance):
    if source_dir is not None:
        final_template = validate_source_path(source_dir)
        return final_template, source_dir, False

    auto_used = False

    if not template_name:
        template_name = final_instance[:5] + "_" + TEMPLATE_SUFFIX
        auto_used = True
        oprint(f"提示：未指定模板，已根据实例名自动推导使用模板：{template_name}")
        oprint("")

    validate_template_name(template_name)

    if not template_root:
        raise ScriptError("错误：缺少模板配置根目录。")

    template_root_no = template_root.rstrip("\\")
    if os.path.exists(template_root_no) and not os.path.isdir(template_root_no):
        raise ScriptError(f"错误：模板配置根目录存在但不是目录：{template_root}")

    source = normalize_path(ntpath.join(template_root, template_name), "dir", template_root)

    return template_name, source, auto_used


def validate_version_consistency(template_name, instance_name):
    if template_name[:5] != instance_name[:5]:
        raise ScriptError(
            "错误：模板版本代码与实例版本代码不一致。\n"
            f"模板：{template_name}\n"
            f"实例：{instance_name}"
        )


def validate_copy_safety(source_dir, target_dir, template_root):
    if same_path(source_dir, target_dir):
        raise ScriptError(f"错误：源目录和目标目录不能相同。\n源目录：{source_dir}\n目标目录：{target_dir}")

    if is_within(target_dir, source_dir):
        raise ScriptError(f"错误：目标目录不得位于源目录内部。\n源目录：{source_dir}\n目标目录：{target_dir}")

    if is_within(source_dir, target_dir):
        raise ScriptError(f"错误：源目录不得位于目标目录内部。\n源目录：{source_dir}\n目标目录：{target_dir}")

    if template_root and is_within(target_dir, template_root):
        raise ScriptError(f"错误：目标目录不得位于模板根目录内部。\n模板根目录：{template_root}\n目标目录：{target_dir}")


def ensure_source_exists(source_dir, auto_used, template_name):
    source_no = source_dir.rstrip("\\")

    if os.path.isdir(source_no):
        return

    if os.path.exists(source_no):
        raise ScriptError(f"错误：源路径存在但不是目录：{source_dir}")

    if auto_used:
        raise ScriptError(
            "错误：自动推导的模板目录不存在。\n"
            f"推导模板名：{template_name}\n"
            f"预期路径：{source_dir}\n"
            "请使用 --template 或 --source 显式指定有效模板。"
        )

    raise ScriptError(f"错误：源目录不存在：{source_dir}")


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
                os.remove(entry.path)


def copy_contents(source_dir, target_dir):
    source_no = source_dir.rstrip("\\")
    target_no = target_dir.rstrip("\\")

    try:
        entries = os.listdir(source_no)
    except OSError as exc:
        raise RuntimeScriptError(f"错误：无法读取源目录：{source_dir}\n详情：{exc}")

    try:
        os.makedirs(target_no, exist_ok=True)
    except OSError as exc:
        raise RuntimeScriptError(f"错误：无法创建目标目录：{target_dir}\n详情：{exc}")

    for name in entries:
        src = ntpath.join(source_no, name)
        dst = ntpath.join(target_no, name)

        try:
            if os.path.isdir(src):
                shutil.copytree(src, dst, symlinks=False, dirs_exist_ok=False)
            else:
                shutil.copy2(src, dst)
        except Exception as exc:
            raise RuntimeScriptError(f"错误：复制失败。\n源：{src}\n目标：{dst}\n详情：{exc}")


def create_backup(target_dir, instance_name, configs_root, source_dir, template_root):
    backup_root = normalize_path(ntpath.join(configs_root, "backups"), "dir", configs_root)

    if is_within(backup_root, source_dir):
        raise RuntimeScriptError(f"错误：备份目录不得位于源目录内部。\n备份根目录：{backup_root}")

    if is_within(backup_root, target_dir):
        raise RuntimeScriptError(f"错误：备份目录不得位于目标目录内部。\n备份根目录：{backup_root}")

    if template_root and is_within(backup_root, template_root):
        raise RuntimeScriptError(f"错误：备份目录不得位于模板根目录内部。\n备份根目录：{backup_root}")

    candidate_name = instance_name

    if os.path.exists(ntpath.join(backup_root, candidate_name)):
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base_name = f"{instance_name}.bak.{timestamp}"
        candidate_name = base_name
        counter = 1

        while os.path.exists(ntpath.join(backup_root, candidate_name)):
            candidate_name = f"{base_name}-{counter:03d}"
            counter += 1

    backup_path = normalize_path(ntpath.join(backup_root, candidate_name), "dir", backup_root)

    if same_path(backup_path, target_dir):
        raise RuntimeScriptError(f"错误：备份目录与目标目录相同。\n备份目录：{backup_path}\n目标目录：{target_dir}")

    if is_within(backup_path, target_dir):
        raise RuntimeScriptError(f"错误：备份目录不得位于目标目录内部。\n备份目录：{backup_path}\n目标目录：{target_dir}")

    if is_within(target_dir, backup_path):
        raise RuntimeScriptError(f"错误：目标目录不得位于备份目录内部。\n备份目录：{backup_path}\n目标目录：{target_dir}")

    if is_within(backup_path, source_dir):
        raise RuntimeScriptError(f"错误：备份目录不得位于源目录内部。\n备份目录：{backup_path}")

    if template_root and is_within(backup_path, template_root):
        raise RuntimeScriptError(f"错误：备份目录不得位于模板根目录内部。\n备份目录：{backup_path}")

    oprint("")
    oprint(f"[INFO] 目标目录非空，正在备份到：{backup_path}")
    oprint("")

    try:
        os.makedirs(backup_root, exist_ok=True)
    except OSError as exc:
        raise RuntimeScriptError(f"错误：无法创建备份根目录：{backup_root}\n详情：{exc}")

    try:
        shutil.move(target_dir.rstrip("\\"), backup_path.rstrip("\\"))
    except Exception as exc:
        raise RuntimeScriptError(f"错误：备份目标目录失败。\n目标目录：{target_dir}\n备份目录：{backup_path}\n详情：{exc}")

    return backup_path


def perform_copy(source_dir, target_dir, instance_name, target_existed, target_nonempty, configs_root, template_root):
    backup_path = None

    try:
        if target_existed and target_nonempty:
            backup_path = create_backup(target_dir, instance_name, configs_root, source_dir, template_root)

        copy_contents(source_dir, target_dir)

    except Exception as exc:
        if backup_path is not None:
            try:
                if os.path.exists(target_dir.rstrip("\\")):
                    remove_path(target_dir)
            except Exception:
                raise RuntimeScriptError(f"错误：复制失败后清理未完成目标目录失败。\n备份保留：{backup_path}")

            try:
                shutil.move(backup_path.rstrip("\\"), target_dir.rstrip("\\"))
            except Exception:
                raise RuntimeScriptError(f"错误：复制失败且恢复备份失败。\n备份保留：{backup_path}")

            raise RuntimeScriptError(f"错误：复制失败，已恢复原目标目录。\n原错误：{exc}")

        try:
            if not target_existed:
                if os.path.exists(target_dir.rstrip("\\")):
                    remove_path(target_dir)
            else:
                if not target_nonempty:
                    clear_directory(target_dir)
        except Exception:
            pass

        if isinstance(exc, ScriptError):
            raise

        raise RuntimeScriptError(f"错误：复制失败。\n详情：{exc}")

    oprint("")
    oprint("[INFO] 复制完成。")
    oprint(f"源目录: {source_dir}")
    oprint(f"目标目录: {target_dir}")
    oprint("")


def run(argv):
    setup_stdio()

    if help_requested(argv):
        print_help()
        return EXIT_SUCCESS, False

    if sys.version_info < (3, 11):
        eprint("错误：Instance_Configs_Cloner.py 需要 Python 3.11 或更高版本。")
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
                target_config = normalize_path(args.config, "file", os.getcwd())
            else:
                target_config = DEFAULT_CONFIG_PATH

            if os.path.exists(target_config):
                if not os.path.isfile(target_config):
                    raise ScriptError(f"错误：配置文件路径存在但不是文件：{target_config}")

                oprint(f"[INFO] 配置文件已存在，未写入磁盘: {target_config}")
            else:
                create_default_config_atomic(target_config)
                oprint(f"[INFO] 已将默认配置写入磁盘: {target_config}")

            return EXIT_SUCCESS, no_input

        if args.source is not None and (args.template_root is not None or args.template is not None):
            raise ScriptError("参数冲突：使用 --source 时，禁止同时使用 --template-root 和 --template 。")

        if args.target is not None and (args.configs_root is not None or args.instance is not None):
            raise ScriptError("参数冲突：使用 --target 时，禁止同时使用 --configs-root 和 --instance 。")

        builtin = build_builtin_config()

        if args.config is not None:
            config_file = normalize_path(args.config, "file", os.getcwd())

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

        toml_config = {}

        if config_file is not None:
            toml_config, _ = load_toml_file(config_file)

        if args.version_map is not None:
            version_map_path = normalize_path(args.version_map, "file", os.getcwd())
        elif toml_config.get("version_map"):
            version_map_path = toml_config["version_map"]
        else:
            version_map_path = builtin["version_map"]

        global VERSION_MAP
        VERSION_MAP = load_version_map(version_map_path)

        top_instance_raw = toml_config.get("instance_name", "")
        top_template_raw = toml_config.get("template_name", "")

        if top_instance_raw:
            validate_instance_name(top_instance_raw)

        if top_template_raw:
            validate_template_name(top_template_raw)

        interactive_config = toml_config.get("interactive", {})

        if args.template_root is not None:
            template_root = normalize_path(args.template_root, "dir", os.getcwd())
        else:
            template_root = toml_config.get("template_root", builtin["template_root"])

        if args.configs_root is not None:
            configs_root = normalize_path(args.configs_root, "dir", os.getcwd())
        else:
            configs_root = toml_config.get("configs_root", builtin["configs_root"])

        if args.worlds_root is not None:
            worlds_root = normalize_path(args.worlds_root, "dir", os.getcwd())
        else:
            worlds_root = toml_config.get("worlds_root", builtin["worlds_root"])

        worlds_root_no = worlds_root.rstrip("\\")
        if os.path.exists(worlds_root_no) and not os.path.isdir(worlds_root_no):
            raise ScriptError(f"错误：世界根目录存在但不是目录：{worlds_root}")

        instance_name = None

        if args.instance is not None:
            instance_name = args.instance.strip()
            if not instance_name:
                raise ScriptError("错误：--instance 不能为空。")
            validate_instance_name(instance_name)
        elif top_instance_raw:
            instance_name = top_instance_raw

        template_name = None

        if args.template is not None:
            template_name = args.template.strip()
            if not template_name:
                raise ScriptError("错误：--template 不能为空。")
            validate_template_name(template_name)
        elif top_template_raw:
            template_name = top_template_raw

        source_dir = None
        if args.source is not None:
            source_dir = normalize_path(args.source, "dir", os.getcwd())

        target_dir = None
        if args.target is not None:
            target_dir = normalize_path(args.target, "dir", os.getcwd())

        if interactive_mode:
            oprint("提示：当前为交互模式。")
            oprint("提示：也可以使用命令行参数执行，使用 --help 可查看完整参数说明：")
            oprint(f"      .\\{SCRIPT_NAME} --help")
            oprint("")

            if interactive_config.get("show_paths", True):
                oprint("当前环境配置：")
                oprint(f"  模板根目录: {template_root}")
                oprint(f"  实例根目录: {configs_root}")
                oprint(f"  世界根目录: {worlds_root}")
                oprint(f"  版本映射: {version_map_path}")
                oprint("")

            if instance_name:
                oprint(f"提示：使用配置文件中的实例名：{instance_name}")
                oprint("")
            else:
                while True:
                    chosen_instance = interactive_select_instance(worlds_root)

                    if template_name and chosen_instance[:5] != template_name[:5]:
                        oprint(
                            "错误：输入的实例版本代码与配置中的模板版本代码不一致。\n"
                            f"实例：{chosen_instance}\n"
                            f"模板：{template_name}\n"
                            "请重新选择实例。"
                        )
                        oprint("")
                        continue

                    instance_name = chosen_instance
                    break

            if template_name:
                oprint(f"提示：使用配置文件中的模板名：{template_name}")
                oprint("")
            else:
                template_name = instance_name[:5] + "_" + TEMPLATE_SUFFIX
                oprint(f"提示：未指定模板，已根据实例名自动推导使用模板：{template_name}")
                oprint("")

            final_instance, target_dir = resolve_target(None, instance_name, configs_root)
            final_template, source_dir, _ = resolve_source(None, template_name, template_root, final_instance)

            validate_version_consistency(final_template, final_instance)
            validate_copy_safety(source_dir, target_dir, template_root)
            ensure_source_exists(source_dir, False, final_template)

            target_existed, target_nonempty = inspect_target(target_dir)

            oprint("")
            oprint("即将执行：")
            oprint(f"源目录: {source_dir}")
            oprint(f"目标目录: {target_dir}")
            oprint("")

            if not (target_existed and target_nonempty):
                if not confirm("是否继续？[Y/n] ", True):
                    raise UserCancel()

            if target_existed and target_nonempty:
                authorize_nonempty_target(target_dir, args.overwrite, no_input, interactive_mode)

        else:
            final_instance, target_dir = resolve_target(target_dir, instance_name, configs_root)
            final_template, source_dir, auto_used = resolve_source(source_dir, template_name, template_root, final_instance)

            validate_version_consistency(final_template, final_instance)
            validate_copy_safety(source_dir, target_dir, template_root)
            ensure_source_exists(source_dir, auto_used, final_template)

            target_existed, target_nonempty = inspect_target(target_dir)

            if target_existed and target_nonempty:
                authorize_nonempty_target(target_dir, args.overwrite, no_input, interactive_mode)

        perform_copy(source_dir, target_dir, final_instance, target_existed, target_nonempty, configs_root, template_root)

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
