REM K-1.5模型屡次出错，本段注释为DeepSeek-R1大模型生成。
REM Script By ZeMeng

:: 关闭命令回显，使脚本执行时不显示命令本身
@echo off
:: 将控制台编码设置为UTF-8，防止中文乱码
chcp 65001

:: 定义版本信息文件名称
set ReleasesFile=releases.json

:: 检查版本文件是否存在
if not exist "%ReleasesFile%" (
    echo releases.json 文件未找到，请确保文件存在。
    pause       :: 暂停等待用户确认
    exit /b     :: 退出批处理脚本
)

:: 初始化版本计数器
set Count=0
:: 初始化版本列表变量
set Versions=

:: 解析版本文件内容
for /f "tokens=1,2 delims=:" %%A in (
    'type "%ReleasesFile%" ^| find ":"'  :: 读取文件并过滤包含冒号的行
) do (
    set /a Count+=1  :: 计数器自增
    
    :: 将版本信息存入数组
    set VersionKey[!Count!]=%%A    :: 存储冒号前的键（使用延迟变量扩展）
    set VersionValue[!Count!]=%%B  :: 存储冒号后的值
    
    :: 显示带编号的版本选项
    echo !Count!: %%B
)

:: 获取用户输入
set /p Choice=请输入数字选择版本： 

:: 验证输入有效性
if %Choice% lss 1 (
    echo 无效的选择，请输入一个正整数。
    pause
    exit /b
)

if %Choice% gtr %Count% (
    echo 无效的选择，最大版本号为 %Count%。
    pause
    exit /b
)

:: 根据选择设置版本前缀
set VersionPrefix=!VersionValue[%Choice%]!

:: 构建配置文件和服务器jar名称
set ServerJar=spigot-%VersionPrefix%.jar                 :: 核心服务端文件
set BukkitConfig=1.%VersionPrefix%_Example.bukkit.yml     :: Bukkit配置文件
set CommandConfig=1.%VersionPrefix%_Example.command.yml   :: 命令配置文件
set ServerProperties=1.%VersionPrefix%_Example.server.properties  :: 服务器属性文件
set SpigotConfig=1.%VersionPrefix%_Example.spigot.yml     :: Spigot配置文件

:: 检查核心服务端文件是否存在
if not exist "%ServerJar%" (
    echo 服务器文件 %ServerJar% 未找到，请检查文件是否存在。
    pause
    exit /b
)

:: 返回上级目录
cd ..\

:: 启动Java服务端（带详细JVM参数配置）
".\runtimes\zulu-25\bin\java.exe" ^
-Xms6144M -Xmx6144M        :: 初始/最大堆内存设为6GB ^
-XX:+UseG1GC               :: 启用G1垃圾回收器 ^
-XX:+ParallelRefProcEnabled ^
-XX:MaxGCPauseMillis=200   :: 目标最大GC暂停时间200ms ^
-XX:+UnlockExperimentalVMOptions ^
-XX:+DisableExplicitGC     :: 禁止显式调用GC ^
-XX:+AlwaysPreTouch        :: 启动时预接触内存页 ^
-XX:G1HeapWastePercent=5   :: G1堆浪费百分比阈值 ^
-XX:G1MixedGCCountTarget=4 :: 混合GC的目标次数 ^
-XX:InitiatingHeapOccupancyPercent=15  :: 触发并发GC周期的堆占用率 ^
-XX:G1MixedGCLiveThresholdPercent=90   :: 存活对象占比阈值 ^
-XX:G1RSetUpdatingPauseTimePercent=5 ^
-XX:SurvivorRatio=32       :: Eden与Survivor区比例 ^
-XX:+PerfDisableSharedMem  :: 禁用性能数据共享内存 ^
-XX:MaxTenuringThreshold=1 :: 对象晋升老年代的年龄阈值 ^
-Dusing.aikars.flags=https://mcflags.emc.gs ^  :: Aikar's JVM参数标志
-Daikars.new.flags=true    :: 使用新版优化标志 ^
-XX:G1NewSizePercent=30    :: G1新生代初始占比 ^
-XX:G1MaxNewSizePercent=40 :: G1新生代最大占比 ^
-XX:G1HeapRegionSize=8M    :: G1区域大小 ^
-XX:G1ReservePercent=20    :: G1保留内存百分比 ^
-Dfile.encoding=UTF-8      :: 强制使用UTF-8编码 ^
-jar ".\%ServerJar%" ^     :: 指定要运行的JAR文件
--world-dir worlds         :: 自定义世界保存目录 ^
--plugins plugins          :: 插件目录 ^
--bukkit-settings %BukkitConfig% ^  :: Bukkit配置路径
--commands-settings %CommandConfig% ^  :: 命令配置路径
--config %ServerProperties% ^  :: 服务器属性文件路径
--spigot-settings %SpigotConfig% ^  :: Spigot配置路径
--level-name 1.%VersionPrefix%.Example  :: 默认世界名称

:: 脚本执行完毕自动退出