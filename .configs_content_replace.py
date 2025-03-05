import os
from typing import Dict, List, Tuple

REPLACEMENT_RULES: Dict[str, List[Tuple[str, str]]] = {
    'server.properties': [
        ('accepts-transfers=false', 'accepts-transfers=true'),
        ('allow-flight=false', 'allow-flight=true'),
        ('allow-nether=true', 'allow-nether=false'),
        ('enable-command-block=false', 'enable-command-block=true'),
        ('enforce-secure-profile=true', 'enforce-secure-profile=false'),
        ('gamemode=0', 'gamemode=2'),
        ('gamemode=survival', 'gamemode=adventure'),
        ('max-players=20', 'max-players=100'),
        ('motd=A Minecraft Server', 'motd=Thousands Minigames'),
        ('online-mode=true', 'online-mode=false'),
        ('simulation-distance=10', 'simulation-distance=8'),
        ('spawn-protection=16', 'spawn-protection=0'),
        ('view-distance=10', 'view-distance=16')
    ],
    'bukkit.yml': [
        ('  allow-end: true', '  allow-end: false')
    ],
    'commands.yml': [
        (
            'command-block-overrides: []',
            'command-block-overrides:\\n    - "*"'
        )
    ]
}

def process_config_file(filename: str, file_type: str) -> None:
    """处理配置文件，严格多行匹配"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            original_lines = [line.rstrip('\n\r') for line in f.readlines()]
    except UnicodeDecodeError:
        print(f"警告: 文件 {filename} 解码失败，已跳过")
        return

    modified = False
    new_lines = []
    i = 0
    total_lines = len(original_lines)

    while i < total_lines:
        line = original_lines[i]
        replaced = False

        # 遍历所有替换规则
        for old, new in REPLACEMENT_RULES.get(file_type, []):
            old_lines = old.split('\\n')
            new_lines_content = new.replace('\\n', '\n').split('\n')
            
            # 检查剩余行数是否足够
            if i + len(old_lines) > total_lines:
                continue
                
            # 精确匹配多行内容
            match = True
            for j in range(len(old_lines)):
                if original_lines[i + j] != old_lines[j]:
                    match = False
                    break

            if match:
                # 添加新内容（自动处理换行符）
                new_lines.extend([nl + '\n' for nl in new_lines_content[:-1]])
                new_lines.append(new_lines_content[-1] + '\n')
                
                i += len(old_lines) - 1  # 跳过已处理行
                modified = True
                replaced = True
                break

        if not replaced:
            new_lines.append(original_lines[i] + '\n')
        
        i += 1

    if modified:
        try:
            # 统一使用LF换行符保证稳定性
            with open(filename, 'w', encoding='utf-8', newline='\n') as f:
                f.writelines([line.rstrip('\r\n') + '\n' for line in new_lines])
            print(f"成功更新: {filename}")
        except Exception as e:
            print(f"错误: 写入 {filename} 失败 - {str(e)}")

def scan_config_files():
    """扫描并处理配置文件"""
    for filename in os.listdir('.'):
        if filename.endswith('.server.properties'):
            file_type = 'server.properties'
        elif filename.endswith('.bukkit.yml'):
            file_type = 'bukkit.yml'
        elif filename.endswith('.commands.yml'):
            file_type = 'commands.yml'
        else:
            continue
        
        process_config_file(filename, file_type)

if __name__ == '__main__':
    print("=== 配置文件替换工具 ===")
    scan_config_files()
    print("=== 操作执行完毕 ===")
