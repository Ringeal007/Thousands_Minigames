# Thousands_Minigames

## 项目概述
本工具提供了一套轻量级解决方案，通过冷加载机制实现Minecraft服务器的快速地图切换。适用于需要频繁更换游戏地图进行不同玩法体验的联机场景，支持Spigot服务端及衍生核心。

## 核心功能
- 🚀 **一键式版本切换**：通过交互式菜单选择目标版本
- 🔄 **配置预加载**：自动匹配版本对应的配置文件
- 📦 **资源隔离管理**：支持多版本配置文件共存
- 🛠 **内存优化配置**：内置Aikar's Flags优化参数
- 🖥 **UTF-8编码支持**：确保中文环境兼容性

## 系统要求
- Windows 10/11 64位
- Java Runtime Environment 21+
- 8GB+ 物理内存
- 至少10GB可用存储空间

## 使用说明

### 准备工作
1. 创建版本配置文件 `releases.json`：
```json
{
  "1": "20.1",
  "2": "19.4"
}
```

2. 按规范放置服务器文件：
```
spigot-20.1.jar
1.20.1_Example.bukkit.yml
1.20.1_Example.command.yml
1.20.1_Example.server.properties
1.20.1_Example.spigot.yml
```

### 启动流程
1. 双击运行启动脚本
2. 查看可用版本列表
3. 输入对应版本编号
4. 等待服务器初始化完成

## 注意事项
1. 版本号需严格遵循 `X.X` 格式
2. 首次启动前需确认Java路径正确（`runtimes/zulu-21`）
3. 内存设置建议根据物理内存调整（默认6GB）
4. 切换地图时会完全重启服务器进程
5. 推荐使用SSD存储以获得最佳加载速度

## 高级参数
可通过修改启动命令中的下列参数自定义运行环境：
- `--world-dir`：地图存储目录
- `--plugins`：插件目录
- `--level-name`：默认加载的世界名称