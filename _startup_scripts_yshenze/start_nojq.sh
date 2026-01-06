#!/bin/bash
# start script ported to bash by LateDream

set +x
export LANG=zh_CN.UTF-8

JavaPath="java"
ReleasesFile="releases.json"

if [ ! -f "$ReleasesFile" ]; then
    echo "releases.json 文件未找到，请确保文件存在。"
    read -p "Press any key to continue..." -n1 -s
    exit 1
fi

Count=0
declare -A VersionKey
declare -A VersionValue

while IFS=: read -r key value; do
    Count=$((Count + 1))
	value=$(echo $value | tr -d '" ,')
    VersionKey[$Count]="$key"
    VersionValue[$Count]="$value"
    echo "$Count: $value"
done < <(grep ":" "$ReleasesFile")

read -p "请输入数字选择版本：" Choice

if [ "$Choice" -lt 1 ]; then
    echo "无效的选择，请输入一个正整数。"
    read -p "Press any key to continue..." -n1 -s
    exit 1
fi

if [ "$Choice" -gt "$Count" ]; then
    echo "无效的选择，最大版本号为 $Count。"
    read -p "Press any key to continue..." -n1 -s
    exit 1
fi

VersionPrefix=${VersionValue[$Choice]}

ServerJar="spigot-$VersionPrefix.jar"                 # 核心服务端文件
BukkitConfig="1.${VersionPrefix}_Example.bukkit.yml"     # Bukkit配置文件
CommandConfig="1.${VersionPrefix}_Example.command.yml"   # 命令配置文件
ServerProperties="1.${VersionPrefix}_Example.server.properties"  # 服务器属性文件
SpigotConfig="1.${VersionPrefix}_Example.spigot.yml"     # Spigot配置文件

if [ ! -f "$ServerJar" ]; then
    echo "服务器文件 $ServerJar 未找到，请检查文件是否存在。"
    read -p "Press any key to continue..." -n1 -s
    exit 1
fi

cd ..

$JavaPath \
-Xms6144M -Xmx6144M        `# 初始/最大堆内存设为6GB` \
-XX:+UseG1GC               `# 启用G1垃圾回收器` \
-XX:+ParallelRefProcEnabled \
-XX:MaxGCPauseMillis=200   `# 目标最大GC暂停时间200ms` \
-XX:+UnlockExperimentalVMOptions \
-XX:+DisableExplicitGC     `# 禁止显式调用GC` \
-XX:+AlwaysPreTouch        `# 启动时预接触内存页` \
-XX:G1HeapWastePercent=5   `# G1堆浪费百分比阈值` \
-XX:G1MixedGCCountTarget=4 `# 混合GC的目标次数` \
-XX:InitiatingHeapOccupancyPercent=15  `# 触发并发GC周期的堆占用率` \
-XX:G1MixedGCLiveThresholdPercent=90   `# 存活对象占比阈值` \
-XX:G1RSetUpdatingPauseTimePercent=5 \
-XX:SurvivorRatio=32       `# Eden与Survivor区比例` \
-XX:+PerfDisableSharedMem  `# 禁用性能数据共享内存` \
-XX:MaxTenuringThreshold=1 `# 对象晋升老年代的年龄阈值` \
-Dusing.aikars.flags=https://mcflags.emc.gs  `# Aikar's JVM参数标志` \
-Daikars.new.flags=true    `# 使用新版优化标志` \
-XX:G1NewSizePercent=30    `# G1新生代初始占比` \
-XX:G1MaxNewSizePercent=40 `# G1新生代最大占比` \
-XX:G1HeapRegionSize=8M    `# G1区域大小` \
-XX:G1ReservePercent=20    `# G1保留内存百分比` \
-Dfile.encoding=UTF-8      `# 强制使用UTF-8编码` \
-jar "./$ServerJar"        `# 指定要运行的JAR文件` \
--world-dir worlds         `# 自定义世界保存目录` \
--plugins plugins          `# 插件目录` \
--bukkit-settings "$BukkitConfig"   `# Bukkit配置路径` \
--commands-settings "$CommandConfig"   `# 命令配置路径` \
--config "$ServerProperties"   `# 服务器属性文件路径` \
--spigot-settings "$SpigotConfig"   `# Spigot配置路径` \
--level-name "1.${VersionPrefix}.Example"  # 默认世界名称
