chcp 65001
cd ..\
".\runtimes\zulu-21\bin\java.exe" -Xms6144M -Xmx6144M -XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=200 -XX:+UnlockExperimentalVMOptions -XX:+DisableExplicitGC -XX:+AlwaysPreTouch -XX:G1HeapWastePercent=5 -XX:G1MixedGCCountTarget=4 -XX:InitiatingHeapOccupancyPercent=15 -XX:G1MixedGCLiveThresholdPercent=90 -XX:G1RSetUpdatingPauseTimePercent=5 -XX:SurvivorRatio=32 -XX:+PerfDisableSharedMem -XX:MaxTenuringThreshold=1 -Dusing.aikars.flags=https://mcflags.emc.gs -Daikars.new.flags=true -XX:G1NewSizePercent=30 -XX:G1MaxNewSizePercent=40 -XX:G1HeapRegionSize=8M -XX:G1ReservePercent=20 -Dfile.encoding=UTF-8 -jar ".\spigot-1.12.2.jar" --world-dir worlds --plugins plugins --bukkit-settings 1.12.2_Example.bukkit.yml --commands-settings 1.12.2_Example.commands.yml --config 1.12.2_Example.server.properties --spigot-settings 1.12.2_Example.spigot.yml --level-name 1.12.2_Example
