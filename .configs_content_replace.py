import os

# 硬编码替换规则（保持原有格式，包括空格）
REPLACEMENT_RULES = {
    # server.properties的替换规则
    'server.properties': [
        # 旧内容 -> 新内容（严格保持格式）
        # 注意！最后一个括号后面不要带逗号！
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
    
    # bukkit.yml的替换规则（特别注意前导空格）
    'bukkit.yml': [
        ('  allow-end: true', '  allow-end: false')
    ]
}

def process_config_file(filename, file_type):
    """处理单个配置文件"""
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        original_line = line.rstrip('\n')  # 保留原有换行符
        replaced = False
        
        # 遍历该文件类型的所有替换规则
        for (old_line, new_line) in REPLACEMENT_RULES.get(file_type, []):
            if original_line == old_line:
                # 保持原有换行符状态
                new_line_with_eol = new_line + ('\n' if line.endswith('\n') else '')
                new_lines.append(new_line_with_eol)
                replaced = True
                break
        
        if not replaced:
            new_lines.append(line)

    # 写回文件（保留原有编码和换行符）
    with open(filename, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

def main():
    # 遍历当前目录
    for filename in os.listdir('.'):
        # 识别文件类型
        if filename.endswith('.server.properties'):
            file_type = 'server.properties'
        elif filename.endswith('.bukkit.yml'):
            file_type = 'bukkit.yml'
        else:
            continue

        # 执行替换操作
        process_config_file(filename, file_type)

if __name__ == '__main__':
    main()
