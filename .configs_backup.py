import os
import shutil
from datetime import datetime

def backup_config_files():
    # 获取当前目录
    directory = os.getcwd()

    # 获取当前时间戳（精确到秒）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 遍历当前目录中的所有文件
    for filename in os.listdir(directory):
        # 检查文件是否以 .server.properties 或 .bukkit.yml 结尾
        if filename.endswith(".server.properties") or filename.endswith(".bukkit.yml"):
            # 构造备份文件名
            backup_filename = f"{filename}.{timestamp}.bak"
            original_file = os.path.join(directory, filename)
            backup_file = os.path.join(directory, backup_filename)

            # 复制文件以创建备份
            shutil.copy2(original_file, backup_file)
            print(f"备份成功: {original_file} -> {backup_file}")

if __name__ == "__main__":
    backup_config_files()
