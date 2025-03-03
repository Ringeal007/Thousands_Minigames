@echo off
chcp 65001

set ReleasesFile=releases.json

if not exist "%ReleasesFile%" (
    echo releases.json 文件未找到，请确保文件存在。
    pause
    exit /b
)

set Count=0
set Versions=

for /f "tokens=1,2 delims=:" %%A in ('type "%ReleasesFile%" ^| find ":"') do (
    set /a Count+=1
    set VersionKey[!Count!]=%%A
    set VersionValue[!Count!]=%%B
    echo !Count!: %%B
)

set /p Choice=请输入数字选择版本： 

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

set VersionPrefix=!VersionValue[%Choice%]!

set ServerJar=spigot-%VersionPrefix%.jar
set BukkitConfig=1.%VersionPrefix%_Example.bukkit.yml
set CommandConfig=1.%VersionPrefix%_Example.command.yml
set ServerProperties=1.%VersionPrefix%_Example.server.properties
set SpigotConfig=1.%VersionPrefix%_Example.spigot.yml

if not exist "%ServerJar%" (
    echo 服务器文件 %ServerJar% 未找到，请检查文件是否存在。
    pause
    exit /b
)

cd ..\
".\runtimes\zulu-21\bin\java.exe" -Xms6144M -Xmx6144M -XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=200 -XX:+UnlockExperimentalVMOptions -XX:+DisableExplicitGC -XX:+AlwaysPreTouch -XX:G1HeapWastePercent=5 -XX:G1MixedGCCountTarget=4 -XX:InitiatingHeapOccupancyPercent=15 -XX:G1MixedGCLiveThresholdPercent=90 -XX:G1RSetUpdatingPauseTimePercent=5 -XX:SurvivorRatio=32 -XX:+PerfDisableSharedMem -XX:MaxTenuringThreshold=1 -Dusing.aikars.flags=https://mcflags.emc.gs -Daikars.new.flags=true -XX:G1NewSizePercent=30 -XX:G1MaxNewSizePercent=40 -XX:G1HeapRegionSize=8M -XX:G1ReservePercent=20 -Dfile.encoding=UTF-8 -jar ".\%ServerJar%" --world-dir worlds --plugins plugins --bukkit-settings %BukkitConfig% --commands-settings %CommandConfig% --config %ServerProperties% --spigot-settings %SpigotConfig% --level-name 1.%VersionPrefix%.Example