@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
title 12111_TM_Example
if not exist ".\configs\12111_TM_Example\" mkdir ".\configs\12111_TM_Example\"
".\runtimes\zulu-25\bin\java.exe" -Xms6144M -Xmx6144M --add-modules=jdk.incubator.vector -XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=200 -XX:+UnlockExperimentalVMOptions -XX:+DisableExplicitGC -XX:+AlwaysPreTouch -XX:G1NewSizePercent=30 -XX:G1MaxNewSizePercent=40 -XX:G1HeapRegionSize=8M -XX:G1ReservePercent=20 -XX:G1HeapWastePercent=5 -XX:G1MixedGCCountTarget=4 -XX:InitiatingHeapOccupancyPercent=15 -XX:G1MixedGCLiveThresholdPercent=90 -XX:G1RSetUpdatingPauseTimePercent=5 -XX:SurvivorRatio=32 -XX:+PerfDisableSharedMem -XX:MaxTenuringThreshold=1 -Xlog:gc*:logs/gc.log:time,uptime:filecount=5,filesize=1M -Dusing.aikars.flags=https://mcflags.emc.gs -Daikars.new.flags=true -Dfile.encoding=UTF-8 -DPaper.IgnoreJavaVersion=true -jar ".\paper-1.21.11.jar" --nogui --world-dir worlds --plugins plugins --config configs\12111_TM_Example\server.properties --commands-settings configs\12111_TM_Example\commands.yml --bukkit-settings configs\12111_TM_Example\bukkit.yml --spigot-settings configs\12111_TM_Example\spigot.yml --paper-settings-directory configs\12111_TM_Example\ --level-name 12111_TM_Example
pause
