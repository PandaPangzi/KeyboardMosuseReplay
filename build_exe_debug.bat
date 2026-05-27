@echo off
setlocal

cd /d "%~dp0"
chcp 65001 >nul

echo ======================================
echo KMReasy 调试打包脚本（带控制台）
echo ======================================

if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
    echo [信息] 使用虚拟环境: .venv\Scripts\python.exe
) else (
    where py >nul 2>nul
    if errorlevel 1 (
        set "PY_CMD=python"
        echo [信息] 使用系统 Python: python
    ) else (
        set "PY_CMD=py -3"
        echo [信息] 使用 Python 启动器: py -3
    )
)

echo.
echo [1/5] 检查/修复 pip...
call %PY_CMD% -m ensurepip --upgrade
if errorlevel 1 goto :error

echo.
echo [2/5] 升级 pip...
call %PY_CMD% -m pip install --upgrade pip
if errorlevel 1 goto :error

echo.
echo [3/5] 安装项目依赖...
call %PY_CMD% -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo [4/5] 安装/更新 PyInstaller...
call %PY_CMD% -m pip install --upgrade pyinstaller
if errorlevel 1 goto :error

echo.
echo [5/5] 开始打包（调试模式，带控制台）...
call %PY_CMD% -m PyInstaller --noconfirm --clean --console --name KMReasy_debug --collect-all pynput --collect-all pyautogui --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 main.py
if errorlevel 1 goto :error

echo.
echo ======================================
echo 打包成功！
echo EXE 路径: dist\KMReasy_debug\KMReasy_debug.exe
echo ======================================

if exist "dist\KMReasy_debug" start "" explorer "%cd%\dist\KMReasy_debug"
pause
exit /b 0

:error
echo.
echo ======================================
echo 打包失败，请查看上方报错信息。
echo ======================================
pause
exit /b 1
