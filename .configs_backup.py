import os
import shutil
from datetime import datetime

def backup_config_files():
    """备份关键配置文件
    
    自动备份当前目录中以下类型的配置文件：
    - .server.properties
    - .bukkit.yml
    - .command.yml
    备份文件命名格式：原文件名.年月日_时分秒.bak
    """
    
    # 获取脚本运行的当前工作目录
    working_directory = os.getcwd()
    
    # 生成精确到秒的时间戳（用于保证备份唯一性）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 遍历目录中的所有条目
    for entry in os.listdir(working_directory):
        # 筛选需要备份的配置文件（同时验证是否为文件）
        if os.path.isfile(entry) and (
            entry.endswith(".server.properties") or  # Minecraft 服务端配置
            entry.endswith(".bukkit.yml") or         # CraftBukkit 插件配置
            entry.endswith(".command.yml")           # 自定义命令配置
        ):
            # 构建备份文件名（保留原扩展名）
            backup_name = f"{entry}.{timestamp}.bak"
            
            # 完整的原始文件路径
            source_path = os.path.join(working_directory, entry)
            # 完整的备份文件路径
            backup_path = os.path.join(working_directory, backup_name)
            
            # 执行带元数据拷贝（保留文件属性）
            shutil.copy2(source_path, backup_path)
            
            # 输出操作日志
            print(f"[OK] 配置文件已备份 | 源文件: {entry} | 备份存储为: {backup_name}")

if __name__ == "__main__":
    backup_config_files()
