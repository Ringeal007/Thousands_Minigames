#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minecraft 配置文件批量替换工具
用于批量修改 Minecraft 服务器配置文件的默认设置
默认路径：脚本所在目录的上一级目录中的 config 文件夹

作者: AI Assistant
日期: 2025-01-06
"""

import os
import sys
import argparse
from pathlib import Path

# =============================================================================
# 配置区域 - 可以根据需要修改
# =============================================================================

# 定义替换规则
# 格式: '文件名': {'原内容': '新内容'}
REPLACE_RULES = {
    'bukkit.yml': {
        'allow-end: true': 'allow-end: false'
    },
    'commands.yml': {
        'command-block-overrides: []': "command-block-overrides: ['*']"
    },
    'server.properties': {
        'accepts-transfers=false': 'accepts-transfers=true',
        'allow-flight=false': 'allow-flight=true',
        'allow-nether=true': 'allow-nether=false',
        'enable-command-block=false': 'enable-command-block=true',
        'enforce-secure-profile=true': 'enforce-secure-profile=false',
        'gamemode=0': 'gamemode=2',
        'gamemode=survival': 'gamemode=adventure',
        'max-players=20': 'max-players=100',
        "motd=A Minecraft Server": "motd=Thousands Minigames",
        'online-mode=true': 'online-mode=false',
        'simulation-distance=10': 'simulation-distance=8',
        'spawn-protection=16': 'spawn-protection=0',
        'view-distance=10': 'view-distance=16'
    },
    'paper-global.yml': {
        'enable-nether: true': 'enable-nether: false'
    }
}

# 目标目录配置
CONFIG_DIR_NAME = "config"  # 配置文件夹名称

# =============================================================================
# 核心功能区域
# =============================================================================

def replace_in_file(file_path, replacements):
    """
    在文件中执行替换，保持缩进和格式不变
    
    参数:
        file_path: Path对象，指向要处理的文件
        replacements: dict，包含要替换的内容 {原内容: 新内容}
    
    返回:
        bool: 是否进行了修改
    """
    if not file_path.exists():
        print(f"  文件不存在: {file_path}")
        return False
    
    try:
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        modified = False
        # 执行替换
        for old_text, new_text in replacements.items():
            if old_text in content:
                content = content.replace(old_text, new_text)
                modified = True
                print(f"  ✓ 替换: {old_text} -> {new_text}")
        
        # 保存修改后的内容
        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  ✓ 已更新: {file_path.name}")
            return True
        else:
            print(f"  - 未找到需要替换的内容: {file_path.name}")
            return False
            
    except Exception as e:
        print(f"  ✗ 错误处理 {file_path}: {e}")
        return False

def process_config_files(base_dir):
    """
    处理所有配置文件
    
    参数:
        base_dir: str，配置文件的根目录路径
    """
    base_path = Path(base_dir)
    
    if not base_path.exists():
        print(f"✗ 错误: 目录 {base_dir} 不存在")
        return
    
    total_files = 0
    modified_files = 0
    
    # 遍历所有Example目录
    for example_dir in base_path.iterdir():
        if example_dir.is_dir() and example_dir.name.endswith('_Example'):
            print(f"\n📁 处理目录: {example_dir.name}")
            
            for config_file, replacements in REPLACE_RULES.items():
                file_path = example_dir / config_file
                if file_path.exists():
                    total_files += 1
                    print(f"\n  📄 处理文件: {config_file}")
                    if replace_in_file(file_path, replacements):
                        modified_files += 1
                else:
                    print(f"  ⏭  跳过不存在的文件: {config_file}")
    
    # 输出统计信息
    print(f"\n{'='*60}")
    print(f"🎉 处理完成!")
    print(f"📊 总计处理文件: {total_files}")
    print(f"✅ 成功修改文件: {modified_files}")
    print(f"{'='*60}")

# =============================================================================
# 主程序入口
# =============================================================================

def main():
    """主程序入口"""
    print("🚀 Minecraft 配置文件批量替换工具")
    print("="*60)
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description='Minecraft 配置文件批量替换工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用示例:
  %(prog)s                           # 使用默认路径 ../config/
  %(prog)s --config-dir /path/to/config  # 使用指定的配置目录
  %(prog)s -c /path/to/config        # 使用指定的配置目录（简写）
  %(prog)s --default-path            # 显式使用默认路径（与无参数效果相同）
        '''
    )
    
    parser.add_argument(
        '-c', '--config-dir',
        type=str,
        help='指定配置文件目录的路径（如果不指定，则默认使用 ../config/）',
        metavar='路径'
    )
    
    parser.add_argument(
        '--default-path',
        action='store_true',
        help='显式使用默认路径 ../config/（与无参数效果相同）'
    )
    
    args = parser.parse_args()
    
    # 确定配置目录
    config_dir = None
    
    if args.config_dir:
        # 使用指定的配置目录
        config_dir = Path(args.config_dir).resolve()
        if not config_dir.exists():
            print(f"❌ 错误: 指定的配置目录不存在: {config_dir}")
            return
        if not config_dir.is_dir():
            print(f"❌ 错误: 指定的路径不是一个目录: {config_dir}")
            return
        print(f"📂 使用指定的配置目录: {config_dir}")
        
    elif args.default_path:
        # 使用默认路径 ../config
        script_dir = Path(__file__).parent
        config_dir = (script_dir / ".." / CONFIG_DIR_NAME).resolve()
        if not config_dir.exists():
            print(f"❌ 错误: 默认路径不存在: {config_dir}")
            print(f"   请确保 {CONFIG_DIR_NAME} 目录存在于脚本的上级目录")
            return
        print(f"📂 使用默认配置目录: {config_dir}")
        
    else:
        # 新的默认行为：直接使用 ..\config\
        script_dir = Path(__file__).parent
        config_dir = (script_dir / ".." / CONFIG_DIR_NAME).resolve()
        if not config_dir.exists():
            print(f"❌ 错误: 默认配置目录不存在: {config_dir}")
            print(f"   请确保 {CONFIG_DIR_NAME} 目录存在于脚本的上级目录")
            print(f"   或使用参数指定配置目录:")
            print(f"     python {Path(__file__).name} --config-dir /path/to/config")
            return
        print(f"📂 使用默认配置目录: {config_dir}")
    
    print(f"{'='*60}\n")
    
    # 开始处理
    process_config_files(config_dir)
    
    print("\n💡 提示: 可以修改 REPLACE_RULES 变量来添加更多替换规则")
    print(f"   或使用参数: python {Path(__file__).name} -h 查看帮助")

if __name__ == "__main__":
    main()
    input("\n✅ 脚本执行完成！按回车键退出...")
