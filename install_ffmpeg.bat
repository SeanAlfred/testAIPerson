@echo off
echo ========================================
echo FFmpeg 自动安装脚本
echo ========================================
echo.

echo 检查是否已安装 FFmpeg...
ffmpeg -version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] FFmpeg 已安装!
    ffmpeg -version | findstr "ffmpeg version"
    echo.
    goto :end
)

echo [INFO] FFmpeg 未安装
echo.
echo 正在尝试使用 winget 安装...
echo.

winget install ffmpeg

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo [SUCCESS] FFmpeg 安装成功!
    echo ========================================
    echo.
    echo 重要提示:
    echo 1. 请关闭当前命令行窗口
    echo 2. 重新打开一个新的命令行窗口
    echo 3. 运行: ffmpeg -version 验证安装
    echo 4. 运行: python diagnose.py 检查系统
    echo 5. 运行: python main.py 启动服务
    echo.
) else (
    echo.
    echo ========================================
    echo [FAILED] 自动安装失败
    echo ========================================
    echo.
    echo 请手动安装 FFmpeg:
    echo.
    echo 方法 1 - 使用 winget (推荐):
    echo   winget install ffmpeg
    echo.
    echo 方法 2 - 手动安装:
    echo   1. 访问: https://www.gyan.dev/ffmpeg/builds/
    echo   2. 下载 ffmpeg-release-essentials.zip
    echo   3. 解压到 C:\ffmpeg
    echo   4. 添加 C:\ffmpeg\bin 到系统 PATH
    echo   5. 重启命令行窗口
    echo.
    echo 详细说明请查看: install_ffmpeg.md
    echo.
)

:end
echo 按任意键退出...
pause >nul
