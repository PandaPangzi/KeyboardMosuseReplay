# KeyboardRecord — 键鼠录制与回放工具

基于 Python + PyQt6 实现的桌面级键鼠录制/回放工具，支持脚本管理、手动编辑事件、多脚本选择与回放，适用于自动化测试、重复操作批量执行等场景。

---

## 功能一览

| 功能 | 说明 |
|------|------|
| **全局热键录制** | `Shift+Alt+R` 开始/停止录制（后台全局监听，无需窗口焦点） |
| **全局热键回放** | `Shift+Alt+S` 开始/停止回放 |
| **启动倒计时** | 录制/回放均支持倒计时延迟，屏幕顶部悬浮倒计时提示 |
| **鼠标轨迹录制** | 可选，开启后记录连续移动轨迹，录制开始时自动将鼠标移至屏幕中心 |
| **脚本管理** | 保存、加载、删除、重命名；所有脚本持久化为 JSON 文件 |
| **脚本编辑** | 内置事件表格编辑器，可手动增删改每一条事件 |
| **新建空脚本** | 无需录制即可直接创建空脚本并进入编辑模式 |
| **手动添加事件** | 编辑模式下可通过 UI 面板添加鼠标点击、滚轮、键盘、鼠标轨迹等事件 |
| **回放选项** | 可配置速度倍率（0.1×～10×）、循环次数（支持无限循环）、启动延迟（0～30 秒） |
| **进度条** | 回放时实时显示事件进度 |
| **运行日志** | 内置日志面板，stdout 自动重定向显示 |
| **窗口尺寸预设** | 状态栏内置 3 档窗口尺寸，一键切换居中 |

---

## 快速上手

### 环境要求

- Python 3.10+
- Windows（需要 `ctypes.windll` DPI API；热键监听使用 `pynput`）

### 安装依赖

```bash
pip install -r requirements.txt
```

依赖列表：

```
pynput>=1.7.6
pyautogui>=0.9.54
PyQt6>=6.6.0
```

### 启动

**双击 `run.bat`**（自动使用项目 `.venv` 虚拟环境），或：

```bash
python main.py
```

---

## 使用说明

### 录制脚本

1. 在主界面点击 **⏺ 开始录制**，或按全局热键 `Shift+Alt+R`。
2. 若"启动延迟 > 0 秒"，屏幕顶部会显示倒计时悬浮提示，倒计时结束后自动开始录制。
3. 执行需要录制的键鼠操作。
4. 再次按 `Shift+Alt+R` 或点击 **⏹ 停止录制**，弹窗输入脚本名称后保存。

> 勾选"录制鼠标轨迹"后，鼠标移动路径也会被记录；录制开始时鼠标会自动移到屏幕中心作为起点。

### 回放脚本

1. 在脚本列表中选中目标脚本（支持多选，多选后会弹出选择对话框）。
2. 调整"回放选项"面板中的速度、循环次数、启动延迟。
3. 点击 **▶ 回放**，或按全局热键 `Shift+Alt+S`。
4. 倒计时结束后自动开始回放；回放中可点击 **⏹ 停止回放** 或再次按 `Shift+Alt+S` 中断。

### 新建/编辑脚本

1. 点击脚本列表左下角 **✚ 新建脚本**，输入名称后直接进入编辑模式。
2. 或在列表中选中现有脚本，点击 **编辑脚本** 进入编辑模式。
3. 编辑模式下可在事件表格中增、删、改每一行事件，也可通过右侧"手动添加事件"面板向脚本追加操作。
4. 点击 **保存** 完成编辑，点击 **取消** 放弃修改。

### 右键菜单（脚本列表）

在脚本列表中右键单击可进行：删除脚本、重命名脚本等快速操作。

---

## 脚本 JSON 格式

每个脚本保存为 `scripts/` 目录下的 `.json` 文件，格式示例：

```json
{
  "name": "示例脚本",
  "created_at": "2026-05-26T12:00:00",
  "screen_width": 1920,
  "screen_height": 1080,
  "events": [
    {"type":"key_down","timestamp":0.0,"key":"a"},
    {"type":"key_up","timestamp":85.0,"key":"a"},
    {"type":"mouse_move","timestamp":120.0,"x":960,"y":540},
    {"type":"mouse_down","timestamp":300.0,"x":960,"y":540,"button":"left"},
    {"type":"mouse_up","timestamp":380.0,"x":960,"y":540,"button":"left"}
  ]
}
```

- `timestamp`：相对录制起点的毫秒时间戳。
- `events` 数组中每个事件占一行（紧凑格式），方便 Git diff 查看变更。

---

## 模块结构

```
KeyboardRecord/
├── main.py                     # 程序入口，启动 Qt 应用
├── config.py                   # 全局配置（热键、采样间隔、回放默认值、UI 尺寸）
├── settings.py                 # 用户偏好持久化（settings.json 读写）
├── run.bat                     # Windows 一键启动脚本
├── requirements.txt            # pip 依赖声明
├── scripts/                    # 脚本存储目录（JSON 文件）
│
├── core/                       # 核心业务逻辑（无 UI 依赖）
│   ├── event_model.py          # 数据模型：Event / EventType / MouseButton / Script
│   ├── recorder.py             # 录制引擎（pynput 全局监听，节流采样，轨迹中心化）
│   ├── playback.py             # 回放引擎（速度倍率、循环、延迟、精确时序）
│   └── hotkey_manager.py       # 全局热键管理（frozenset 组合键，修饰键归一化）
│
├── storage/
│   └── script_manager.py       # 脚本 JSON 序列化/反序列化，目录扫描与缓存
│
└── ui/                         # PyQt6 界面层
    ├── main_window.py          # 主窗口：整合所有面板，状态机，信号路由，倒计时提示
    ├── script_list_panel.py    # 脚本列表面板（双栈页：预览↔编辑，多选，右键菜单）
    ├── playback_options_panel.py  # 回放参数面板（速度、循环、启动延迟）
    └── manual_mouse_panel.py   # 手动事件面板（编辑模式专用，含悬浮轨迹录制提示）
```

### 各模块详解

#### `config.py`
集中管理所有可调参数，修改此文件即可全局生效：
- `RECORD_HOTKEY` / `PLAY_HOTKEY`：frozenset 多键组合，当前为 `Shift+Alt+R` / `Shift+Alt+S`。
- `MOUSE_MOVE_INTERVAL_MS`：鼠标移动采样间隔（默认 20ms），数值越大文件越小。
- `DEFAULT_START_DELAY_SEC`：默认启动延迟秒数。
- `UI_SIZES`：窗口尺寸预设列表。

#### `core/event_model.py`
用 `@dataclass` 描述单条事件 `Event` 和脚本容器 `Script`：
- `Event`：包含 `type`、`timestamp`（ms）、键盘字段（`key`、`scan_code`）、鼠标字段（`x`、`y`、`button`、`dx`、`dy`）。
- `Script`：事件列表 + 元数据（名称、创建时间、录制分辨率）。

#### `core/recorder.py`
封装 pynput 键鼠监听：
- 支持鼠标移动节流（`MOUSE_MOVE_INTERVAL_MS`）。
- `start(record_mouse_move, center_mouse)`：开始录制，可选录制轨迹并将鼠标移至屏幕中心。
- `stop(trim_key)`：停止录制并修剪末尾的热键按键事件，返回 `Script`。

#### `core/playback.py`
在独立线程中按时间戳精确还原事件：
- 使用 pynput `Controller` 模拟键盘/鼠标。
- 支持速度倍率（`sleep` 时间按比例缩放）。
- 支持无限循环（`loop_count=0`）。
- 回调钩子：`on_event`（每事件）、`on_loop_done`（每轮）、`on_finish`（全部完成）。

#### `core/hotkey_manager.py`
后台守护线程监听全局组合键：
- `_MODIFIER_NORMALIZE`：将 `shift_l`/`shift_r`、`alt_l`/`alt_r` 等统一归一化。
- `_raw_key_name`：对字母键统一 `.lower()`，解决 Shift 按住时大写字母不匹配的问题。
- 通过 `frozenset.issubset(pressed)` 检测组合键触发，防止长按连续触发。

#### `storage/script_manager.py`
管理 `scripts/` 目录：
- `list()`：扫描目录返回所有脚本元数据。
- `save(script)`：序列化为 JSON，events 每行一个对象。
- `load_by_path(path)`：从文件反序列化为 `Script`。
- `delete(path)` / `rename(path, new_name)`：文件级操作。

#### `ui/main_window.py`
主窗口兼顾状态机与信号路由：
- `_Signals`（QObject 子类）：跨线程信号桥，后台线程通过 `emit` 安全更新 UI。
- `_LogStream`：将 `sys.stdout` 重定向到 UI 日志面板。
- 倒计时逻辑：`_countdown_start → _tick_countdown → _finish_countdown`，用 `QTimer.singleShot` 在主线程逐秒更新悬浮提示。
- 录制/回放分离为入口（含倒计时）和执行（`_do_start_record` / `_do_start_play`）。

#### `ui/script_list_panel.py`
脚本列表的核心 UI：
- 上半部分：脚本表格（多选 `ExtendedSelection`，右键上下文菜单）。
- 下半部分：`QStackedWidget` 双页切换：
  - 页 0（预览页）：事件 HTML 表格预览 + "编辑脚本"按钮。
  - 页 1（编辑页）：可编辑的事件表格 + 保存/取消/插入/删除行按钮。
- `sig_edit_started(add_event_cb)` / `sig_edit_finished()`：通知主窗口切换编辑模式。

#### `ui/manual_mouse_panel.py`
仅在编辑模式下启用的手动事件面板：
- 提供按钮快速插入：鼠标左/右/中键点击、双击、滚轮、键盘按键。
- **录制鼠标轨迹**：两阶段左键采集——点击起点 → 点击终点，期间屏幕顶部显示 `_FloatHint` 悬浮提示引导操作。
- `_FloatHint`：无边框半透明悬浮窗，屏幕顶部居中，同时被主窗口复用作倒计时提示。

#### `ui/playback_options_panel.py`
简单的表单面板，提供三个属性：
- `speed`：速度倍率（0.1～10.0）。
- `loop_count`：循环次数（0 = 无限）。
- `start_delay`：启动延迟秒数（0～30）。

---

## 热键速查

| 热键 | 功能 |
|------|------|
| `Shift + Alt + R` | 开始录制 / 停止录制 |
| `Shift + Alt + S` | 开始回放 / 停止回放 |

> 热键为全局监听，程序运行时在任意窗口均有效。
> 组合键定义在 `config.py` 的 `RECORD_HOTKEY` / `PLAY_HOTKEY` 中，修改后重启生效。

---

## 注意事项

- 录制会捕获**所有**键鼠事件（包括密码输入等敏感操作），请注意使用场景。
- 回放会直接控制系统鼠标和键盘，回放期间请勿手动操作，避免干扰。
- 若回放脚本包含坐标依赖（鼠标点击位置），请在与录制时**相同分辨率**的环境下回放。
- 长时间录制且开启鼠标轨迹时会产生大量事件，建议根据需求调整 `MOUSE_MOVE_INTERVAL_MS`。
