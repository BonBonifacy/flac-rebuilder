# FLAC Rebuilder

一个用于清理 FLAC 音频文件中非标准/冗余垃圾数据（如尾部非标准 ID3v1/ID3v2 标签等），并重新生成符合规范音频流的工具。支持**拖放（Drag & Drop）**批量处理多个文件和文件夹。

## 功能特性

- **音频流重构重建**：解码 FLAC 内部真实的 PCM 原始声音数据，重新编码并写回，物理级地过滤并丢弃原文件末尾的所有非音频垃圾字节。
- **无损音质校验**：处理前后计算并比对 PCM 的 MD5 值，确保声音数据 **100% 逐比特（bit-for-bit）完全相同**。
- **标签与封面保留**：100% 还原保留原有的元数据标签（歌名、歌手、专辑、歌词等）以及内嵌的专辑封面图片。
- **高精度定位表重建**：在重写文件时自动重新计算并写入标准的定位表（Seek Table/Seek Points），彻底解决播放进度条快进/快退响应缓慢或卡顿的问题。
- **支持拖放操作**：可以直接将多个 `.flac` 文件或整个音乐文件夹拖放到生成的 `.exe` 上运行。

## 运行环境

- Python 3.7+
- 依赖库：
  - `mutagen`
  - `soundfile` (在 Windows 下自带 `libsndfile` DLL)
  - `numpy`

## 安装与运行

### 1. 使用 `uv` 运行 (推荐)
如果您安装了 `uv`，无需单独安装依赖，直接运行：
```bash
uv run flac_rebuilder.py <file1.flac> <file2.flac> <directory_path>
```

### 2. 使用标准 Python 运行
首先安装依赖：
```bash
pip install -r requirements.txt
```
然后运行：
```bash
python flac_rebuilder.py [音频文件路径或文件夹路径...]
```

## 打包成独立 EXE

如果您希望打包成一个没有 Python 环境也能运行的独立 `.exe` 工具，可以使用 `PyInstaller` 进行编译：

```bash
pip install pyinstaller mutagen soundfile numpy
pyinstaller --onefile --console flac_rebuilder.py
```
编译成功后，生成的 `.exe` 程序位于 `dist/flac_rebuilder.exe`。

**使用方法**：直接将您的 FLAC 文件或包含音乐的文件夹拖放到 `flac_rebuilder.exe` 文件的图标（或快捷方式）上，程序会自动运行并在处理完成后保持控制台打开供您确认处理结果。

## 许可证

MIT License
