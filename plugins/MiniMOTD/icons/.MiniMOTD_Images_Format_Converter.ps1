# 调试模式开关（设置为$true显示详细信息）
$DebugMode = $true

function Debug-Output {
    param([string]$message)
    if ($DebugMode) { Write-Host "[DEBUG] $(Get-Date -Format 'HH:mm:ss.fff') $message" -ForegroundColor Cyan }
}

Debug-Output "脚本启动，当前工作目录：$((Get-Location).Path)"

# 支持的扩展名列表（不区分大小写）
$validExtensions = @('*.jpg','*.jpeg','*.png','*.gif','*.bmp','*.tiff','*.webp')

try {
    # 获取文件列表（包含所有子目录如需处理子目录请添加 -Recurse）
    $files = Get-ChildItem -Path .\* -Include $validExtensions -ErrorAction Stop
    Debug-Output "找到 $($files.Count) 个待处理文件"
    
    # 检查FFmpeg可用性
    $ffmpegTest = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if (-not $ffmpegTest) {
        throw "FFmpeg未找到，请确认已安装并添加至环境变量"
    }
    
    foreach ($file in $files) {
        Debug-Output "--------------------------------------------------"
        Debug-Output "开始处理文件：$($file.FullName)"
        
        # 原始文件名验证
        if (-not $file.Exists) {
            Debug-Output "文件不存在，跳过处理"
            continue
        }

        # 文件名转换逻辑
        $originalBase = $file.BaseName
        $newBaseName = $originalBase -replace '\.', '_'
        $outputFileName = "${newBaseName}__MiniMOTD.png"
        Debug-Output "文件名转换：[$originalBase] → [$newBaseName] → [$outputFileName]"

        # FFmpeg参数构建
        $ffmpegArgs = @(
            '-hide_banner',
            '-loglevel', 'error',        # 改为'debug'获取详细日志
            '-stats',
            '-i', "`"$($file.FullName)`"",
            '-vf', "scale=64:64:force_original_aspect_ratio=decrease,pad=64:64:-1:-1:color=black",
            '-y',
            "`"$outputFileName`""
        )

        # 执行转换
        Debug-Output "执行命令：ffmpeg $($ffmpegArgs -join ' ')"
        $process = Start-Process ffmpeg -ArgumentList $ffmpegArgs -NoNewWindow -PassThru -Wait
        
        # 结果检查
        if ($process.ExitCode -ne 0) {
            Write-Warning "转换失败：$($file.Name) → ExitCode $($process.ExitCode)"
        } elseif (Test-Path $outputFileName) {
            Debug-Output "转换成功，生成文件大小：$((Get-Item $outputFileName).Length) bytes"
        } else {
            Write-Warning "未知错误：输出文件未生成"
        }
    }
}
catch {
    Write-Error "脚本异常：$_"
    if ($_.Exception -match 'NoMatch') {
        Write-Host "提示：当前目录未找到支持的图片文件（支持的扩展名：$($validExtensions -join ', '))" -ForegroundColor Yellow
    }
}
