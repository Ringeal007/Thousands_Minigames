REM 为了方便，本段注释使用AI K-1.5模型添加，可能会有部分错误
REM Script By ZeMeng


@echo off
REM 关闭命令回显，使脚本执行过程更简洁
chcp 65001
REM 设置控制台编码为UTF-8，确保中文显示正常

set ReleasesFile=releases.json
REM 定义版本配置文件名为releases.json

REM 检查releases.json文件是否存在
if not exist "%ReleasesFile%" (
    echo releases.json 文件未找到，请确保文件存在。
    pause
    exit /b
)

REM 显示可选的Minecraft版本列表
echo 请选择要启动的 Minecraft 版本：
REM 使用jq解析JSON文件，提取所有键值对
for /f "tokens=1,2 delims=:" %%A in ('jq -r "keys[]" "%ReleasesFile%"') do (
    echo %%A: %%B
)

REM 接收用户输入的选择
set /p Choice=请输入数字选择版本： 

REM 验证用户输入是否有效
jq -r --arg Choice "%Choice%" '.[$Choice] // empty' "%ReleasesFile%" >nul 2>&1
if %errorlevel% neq 0 (
    echo 无效的选择，请重新运行脚本。
    pause
    exit /b
)

REM 获取选定版本的前缀名
for /f "delims=" %%A in ('jq -r --arg Choice "%Choice%" '.[$Choice]' "%ReleasesFile%"') do set VersionPrefix=%%A

REM 根据版本前缀构建文件名
set ServerJar=spigot-%VersionPrefix%.jar
set BukkitConfig=1.%VersionPrefix%_Example.bukkit.yml
set CommandConfig=1.%VersionPrefix%_Example.command.yml
set ServerProperties=1.%VersionPrefix%_Example.server.properties
set SpigotConfig=1.%VersionPrefix%_Example.spigot.yml

REM 检查服务端核心文件是否存在
if not exist "%ServerJar%" (
    echo 服务器文件 %ServerJar% 未找到，请检查文件是否存在。
    pause
    exit /b
)

REM 启动Minecraft服务器（使用优化后的JVM参数）
".\runtimes\zulu-25\bin\java.exe" ^
-Xms6144M -Xmx6144M ^  REM 初始/最大堆内存设置为6GB
-XX:+UseG1GC ^         REM 使用G1垃圾回收器
-XX:+ParallelRefProcEnabled ^
-XX:MaxGCPauseMillis=200 ^
-XX:+UnlockExperimentalVMOptions ^
-XX:+DisableExplicitGC ^
-XX:+AlwaysPreTouch ^
-XX:G1HeapWastePercent=5 ^
-XX:G1MixedGCCountTarget=4 ^
-XX:InitiatingHeapOccupancyPercent=15 ^
-XX:G1MixedGCLiveThresholdPercent=90 ^
-XX:G1RSetUpdatingPauseTimePercent=5 ^
-XX:SurvivorRatio=32 ^
-XX:+PerfDisableSharedMem ^
-XX:MaxTenuringThreshold=1 ^
-Dusing.aikars.flags=https://mcflags.emc.gs ^  REM Aikar推荐的JVM参数
-Daikars.new.flags=true ^
-XX:G1NewSizePercent=30 ^
-XX:G1MaxNewSizePercent=40 ^
-XX:G1HeapRegionSize=8M ^
-XX:G1ReservePercent=20 ^
-Dfile.encoding=UTF-8 ^  REM 强制使用UTF-8编码
-jar ".\%ServerJar%" ^  REM 指定服务端核心文件
--world-dir worlds ^     REM 自定义世界保存目录
--plugins plugins ^      REM 插件目录
--bukkit-settings %BukkitConfig% ^
--commands-settings %CommandConfig% ^
--config %ServerProperties% ^
--spigot-settings %SpigotConfig% ^
--level-name 1.%VersionPrefix%.Example  REM 世界名称

pause