# FLAC Rebuilder

一个用于清理 FLAC 音频文件中非标准/冗余垃圾数据（如尾部非标准 ID3v1/ID3v2 标签等），并重新生成符合规范音频流的工具。支持**命令行批处理**与**现代图形界面（GUI）拖放**操作。

## 功能特性

- **音频流重构重建**：解码 FLAC 内部真实的 PCM 原始声音数据，重新编码并写回，物理级地过滤并丢弃原文件末尾的所有非音频垃圾字节。
- **无损音质校验**：处理前后计算并比对 PCM 的 MD5 值，确保声音数据 **100% 逐比特（bit-for-bit）完全相同**。
- **标签与封面保留**：100% 还原保留原有的元数据标签（歌名、歌手、专辑、歌词等）以及内嵌的专辑封面图片。
- **高精度定位表重建**：在重写文件时自动重新计算并写入标准的定位表（Seek Table/Seek Points），彻底解决播放进度条快进/快退响应缓慢或卡顿的问题。
- **现代 GUI 界面**：支持拖放（Drag & Drop）多个文件和文件夹到窗口中，异步处理任务，界面流畅不卡死。

## 运行环境

- Python 3.7+
- 依赖库：
  - `mutagen`
  - `soundfile` (在 Windows 下自带 `libsndfile` DLL)
  - `numpy`
  - `PyQt6` (仅 GUI 版本需要)

## 安装与运行

### 1. 使用 `uv` 运行 (推荐)
如果您安装了 `uv`，无需手动安装依赖即可运行：

*   **运行命令行版本**：
    ```bash
    uv run flac_rebuilder.py <file1.flac> <file2.flac> <directory_path>
    ```
*   **运行图形界面版本**：
    ```bash
    uv run flac_rebuilder_gui.py
    ```

### 2. 使用标准 Python 运行
首先安装依赖：
```bash
pip install -r requirements.txt
```
然后运行对应的脚本：
```bash
# 运行命令行版
python flac_rebuilder.py [音频文件/文件夹路径...]

# 运行图形界面版
python flac_rebuilder_gui.py
```

## 打包成独立 EXE

项目内置了 `build.bat` 打包脚本。如果您的 Windows 环境上装有 `uv`，直接双击运行 `build.bat` 即可自动编译生成独立可执行程序。

或者，您也可以使用标准 PyInstaller 进行手动打包：

*   **打包命令行版**：
    ```bash
    pyinstaller --onefile --console flac_rebuilder.py
    ```
*   **打包图形界面版**：
    ```bash
    pyinstaller --onefile --noconsole flac_rebuilder_gui.py
    ```

编译完成后，生成的可执行程序位于 `dist/` 目录下。

## 许可证

MIT License
