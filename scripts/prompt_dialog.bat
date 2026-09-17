@echo off
rem =====================================================================
rem prompt_dialog.bat —— 自学案前置配置对话框启动器（可复用，与具体章节无关）
rem
rem 用法（在目标工程根目录下执行）：
rem   <skill目录>\scripts\prompt_dialog.bat [--project DIR] [--title T]
rem                                         [--dialogue true^|false] [--cli]
rem
rem 说明：
rem   * 本脚本按自身所在位置定位 prompt_dialog.py，可在任何工程中复用，
rem     不依赖调用者所处目录的特定结构；
rem   * 工程目录未显式指定时，由 prompt_dialog.py 自动探测当前目录下的
rem     self\config.yaml 或 config.yaml 并绑定；
rem   * 优先使用 PATH 中的 python，缺失时回退到 py 启动器。
rem =====================================================================
chcp 65001 >nul
set "SCRIPT=%~dp0prompt_dialog.py"
where python >nul 2>nul
if %errorlevel%==0 goto havepython
py -3 "%SCRIPT%" %*
exit /b %errorlevel%
:havepython
python "%SCRIPT%" %*
exit /b %errorlevel%
