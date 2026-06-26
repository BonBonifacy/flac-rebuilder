# /// script
# dependencies = [
#     "mutagen",
#     "soundfile",
#     "numpy",
#     "PyQt6",
# ]
# ///

import os
import sys
import hashlib
import shutil
import re
import numpy as np
import soundfile as sf
from mutagen.flac import FLAC
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
                             QAbstractItemView, QHBoxLayout, QPushButton, QMessageBox,
                             QRadioButton, QFileDialog, QCheckBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QColor, QFont

# QSS 样式表 - 现代高级暗黑主题
DARK_STYLE = """
QMainWindow {
    background-color: #121212;
}
QWidget#CentralWidget {
    background-color: #121212;
}
QLabel#TitleLabel {
    color: #FFFFFF;
    font-size: 20px;
    font-weight: bold;
    padding: 10px 0px;
}
QLabel#DropArea {
    border: 2px dashed #00ADB5;
    border-radius: 12px;
    background-color: #1E1E1E;
    color: #EEEEEE;
    font-size: 15px;
    font-weight: 500;
}
QLabel#DropArea[dragged="true"] {
    border: 2px dashed #00FFD1;
    background-color: #252525;
}
QTableWidget {
    background-color: #1E1E1E;
    color: #EEEEEE;
    gridline-color: #2C2C2C;
    border: 1px solid #2C2C2C;
    border-radius: 8px;
    font-size: 12px;
}
QTableWidget::item {
    padding: 6px;
}
QHeaderView::section {
    background-color: #252525;
    color: #00ADB5;
    font-weight: bold;
    padding: 6px;
    border: 1px solid #1E1E1E;
}
QScrollBar:vertical {
    border: none;
    background: #1E1E1E;
    width: 10px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #393E46;
    min-height: 20px;
    border-radius: 5px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
}
QPushButton#ClearBtn {
    background-color: #393E46;
    color: #EEEEEE;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: bold;
}
QPushButton#ClearBtn:hover {
    background-color: #4E545C;
}
QPushButton#PrimaryBtn {
    background-color: #00ADB5;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: bold;
}
QPushButton#PrimaryBtn:hover {
    background-color: #00FFF6;
    color: #121212;
}
QPushButton#PrimaryBtn:disabled {
    background-color: #2C2C2C;
    color: #777777;
}
QRadioButton {
    color: #EEEEEE;
    font-size: 13px;
    font-weight: 500;
    spacing: 8px;
}
QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border-radius: 8px;
    border: 2px solid #393E46;
}
QRadioButton::indicator:checked {
    background-color: #00ADB5;
    border: 2px solid #00ADB5;
}
QRadioButton::indicator:hover {
    border: 2px solid #00ADB5;
}
QCheckBox {
    color: #EEEEEE;
    font-size: 13px;
    spacing: 5px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 2px solid #393E46;
    border-radius: 4px;
    background-color: #1E1E1E;
}
QCheckBox::indicator:checked {
    background-color: #00ADB5;
    border: 2px solid #00ADB5;
}
QCheckBox::indicator:hover {
    border: 2px solid #00ADB5;
}
"""

def check_flac_layout_issues(filepath):
    reasons = []
    # 1. 检测文件头是否为 ID3
    try:
        with open(filepath, 'rb') as f:
            header = f.read(4)
            if header.startswith(b'ID3'):
                reasons.append("文件头有 ID3 标签")
    except Exception as e:
        return [f"读取失败: {e}"]

    # 2. 检测文件尾垃圾标签
    try:
        file_size = os.path.getsize(filepath)
        if file_size > 128:
            with open(filepath, 'rb') as f:
                f.seek(-128, 2)
                tail_128 = f.read(128)
                if tail_128.startswith(b'TAG'):
                    reasons.append("文件尾有 ID3v1 标签")
                if b'APETAGEX' in tail_128:
                    reasons.append("文件尾有 APE 标签")
                if file_size > 10:
                    f.seek(-10, 2)
                    tail_10 = f.read(10)
                    if tail_10.startswith(b'3DI'):
                        reasons.append("文件尾有 ID3v2 脚注")
    except Exception:
        pass

    # 3. 检测是否有多个 Padding 块
    try:
        audio = FLAC(filepath)
        padding_blocks = [b for b in audio.metadata_blocks if b.code == 1]
        if len(padding_blocks) > 1:
            reasons.append("有多个 Padding 块")
    except Exception as e:
        reasons.append(f"元数据损坏: {e}")

    return reasons


def write_size_warning_log(filename, pcm_md5_before, size_before, size_after):
    """当文件体积发生显著变化或变动超过 2MB 时，写出警告日志"""
    import datetime
    if getattr(sys, 'frozen', False):
        log_dir = os.path.dirname(sys.executable)
    else:
        log_dir = os.path.dirname(os.path.abspath(__file__)) if __file__ else "."
    log_path = os.path.join(log_dir, "flac_size_warnings.log")
    time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    diff_mb = abs(size_before - size_after) / (1024 * 1024)
    ratio = size_after / size_before if size_before > 0 else 1.0
    
    log_line = (
        f"[{time_str}] 警告: 文件体积发生显著变化！\n"
        f"  - 歌名: {filename}\n"
        f"  - 处理前 PCM MD5: {pcm_md5_before}\n"
        f"  - 处理前大小: {size_before/1024/1024:.2f} MB\n"
        f"  - 处理后大小: {size_after/1024/1024:.2f} MB\n"
        f"  - 变化差值: {diff_mb:.2f} MB (变化率: {ratio:.1%})\n"
        f"{'=' * 50}\n"
    )
    
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception as e:
        print(f"写入警告日志失败: {e}")


class RebuildThread(QThread):
    # 定义信号：(标识key, 状态, 校验码1, 校验码2, 对比结果/错误说明)
    file_processed = pyqtSignal(str, str, str, str, str)
    finished_all = pyqtSignal(int, int)
    confirm_request = pyqtSignal(str, int, int)

    def __init__(self, paths, mode="rebuild"):
        super().__init__()
        self.paths = paths
        self.mode = mode
        self.confirm_result = None

    def run(self):
        flac_files = []
        if self.mode == "log_process":
            # paths 是 [{"path": ..., "foobar_md5": ...}]
            flac_files = self.paths
        else:
            for item in self.paths:
                path = item["path"]
                if os.path.isdir(path):
                    for root, _, files in os.walk(path):
                        for file in files:
                            if file.lower().endswith('.flac'):
                                flac_files.append({"path": os.path.join(root, file), "foobar_md5": ""})
                else:
                    if path.lower().endswith('.flac'):
                        flac_files.append({"path": path, "foobar_md5": ""})

        success_count = 0
        fail_count = 0

        for item in flac_files:
            filepath = item["path"]
            foobar_md5 = item.get("foobar_md5", "")
            filename = os.path.basename(filepath)
            ui_key = filepath  # 用绝对路径作为识别 UI 行的唯一标识

            # 智能重构检测
            is_smart_skip = False
            if self.mode == "smart_rebuild":
                issues = check_flac_layout_issues(filepath)
                if not issues:
                    is_smart_skip = True

            if self.mode == "hash_only" or is_smart_skip:
                self.file_processed.emit(ui_key, "计算中..." if self.mode == "hash_only" else "无需优化...", "-", "-", "")
                try:
                    info = sf.info(filepath)
                    original_subtype = info.subtype
                    original_samplerate = info.samplerate
                    read_dtype = 'int32' if original_subtype in ['PCM_24', 'PCM_32'] else 'int16'
                    
                    data, samplerate = sf.read(filepath, dtype=read_dtype)
                    if original_subtype == 'PCM_24':
                        flat_data = (data >> 8).flatten()
                        arr_u8 = np.frombuffer(flat_data.tobytes(), dtype=np.uint8).reshape(-1, 4)
                        pcm_bytes = arr_u8[:, :3].tobytes()
                    else:
                        pcm_bytes = data.tobytes()
                    pcm_md5 = hashlib.md5(pcm_bytes).hexdigest().upper()
                    
                    success_count += 1
                    status_text = "已计算" if self.mode == "hash_only" else "无需优化"
                    self.file_processed.emit(ui_key, status_text, pcm_md5, f"{original_samplerate}Hz / {original_subtype}", "")
                except Exception as e:
                    fail_count += 1
                    self.file_processed.emit(ui_key, "失败", "-", "-", str(e))
            else:
                self.file_processed.emit(ui_key, "处理中...", "-", "-", "")
                temp_path = filepath + ".tmp"
                backup_path = filepath + ".bak"
                
                try:
                    # 1. 备份
                    shutil.copy2(filepath, backup_path)
                    
                    # 2. 读取原始元数据与封面
                    audio = FLAC(filepath)
                    tags = dict(audio.tags)
                    pics = list(audio.pictures)
                    
                    # 3. 计算处理前真实 PCM MD5
                    info = sf.info(filepath)
                    original_subtype = info.subtype
                    original_samplerate = info.samplerate
                    read_dtype = 'int32' if original_subtype in ['PCM_24', 'PCM_32'] else 'int16'
                    
                    data, samplerate = sf.read(filepath, dtype=read_dtype)
                    if original_subtype == 'PCM_24':
                        flat_data = (data >> 8).flatten()
                        arr_u8 = np.frombuffer(flat_data.tobytes(), dtype=np.uint8).reshape(-1, 4)
                        pcm_bytes = arr_u8[:, :3].tobytes()
                    else:
                        pcm_bytes = data.tobytes()
                    pcm_md5_before = hashlib.md5(pcm_bytes).hexdigest().upper()
                    
                    # 4. 重新编码流
                    
                    # 调试测试钩子：故意修改特定测试文件的 PCM 数据以验证 MD5 校验及自动回滚机制
                    if "trigger_md5_error" in filename.lower():
                        data = data.copy()
                        data[0] += 1
                        
                    sf.write(temp_path, data, samplerate, format='FLAC', subtype=original_subtype)
                    
                    # 5. 还原元数据与封面
                    new_audio = FLAC(temp_path)
                    new_audio.tags.clear()
                    for k, v in tags.items():
                        new_audio.tags[k] = v
                    for pic in pics:
                        new_audio.add_picture(pic)
                        
                    # 保留原文件中的定位表 (SEEKTABLE) 及其他有用元数据块 (如 APPLICATION, CUESHEET 等)
                    extra_blocks = [b for b in audio.metadata_blocks if b.code not in (0, 1, 4, 6)]
                    for block in extra_blocks:
                        if not any(b.code == block.code for b in new_audio.metadata_blocks):
                            new_audio.metadata_blocks.append(block)
                            
                    new_audio.save(padding=lambda info: 0)
                    
                    # 5.5 检测文件大小变动是否异常 (比例偏离 25% 以上或绝对大小变化超过 2MB)
                    size_before = os.path.getsize(filepath)
                    size_after = os.path.getsize(temp_path)
                    ratio = size_after / size_before if size_before > 0 else 1.0
                    diff_bytes = abs(size_before - size_after)
                    warning_msg = ""
                    if ratio < 0.75 or ratio > 1.25 or diff_bytes > 2 * 1024 * 1024:
                        write_size_warning_log(filename, pcm_md5_before, size_before, size_after)
                        warning_msg = f"[⚠️警告] 体积变化 {(size_after - size_before)/1024/1024:+.2f} MB，已记录日志"
                    
                    # 5.6 检测文件大小变动是否超过 10MB，如果是，发射信号请求确认并阻塞等待
                    if diff_bytes > 10 * 1024 * 1024:
                        self.confirm_result = None
                        self.confirm_request.emit(filepath, size_before, size_after)
                        while self.confirm_result is None:
                            self.msleep(100)
                        
                        user_approved = self.confirm_result
                        self.confirm_result = None  # 复位
                        if not user_approved:
                            raise ValueError(f"大小变化超过 10MB，用户已取消应用此更改 (变动量: {diff_bytes/1024/1024:.2f}MB)。")
                    
                    # 6. 计算处理后 pcm md5
                    new_data, _ = sf.read(temp_path, dtype=read_dtype)
                    if original_subtype == 'PCM_24':
                        flat_new = (new_data >> 8).flatten()
                        arr_u8_new = np.frombuffer(flat_new.tobytes(), dtype=np.uint8).reshape(-1, 4)
                        new_pcm_bytes = arr_u8_new[:, :3].tobytes()
                    else:
                        new_pcm_bytes = new_data.tobytes()
                    pcm_md5_after = hashlib.md5(new_pcm_bytes).hexdigest().upper()
                    
                    if pcm_md5_before != pcm_md5_after:
                        raise ValueError(f"PCM MD5 改变！原: {pcm_md5_before}, 新: {pcm_md5_after}")
                    
                    # 7. 替换原文件
                    shutil.move(temp_path, filepath)
                    if os.path.exists(backup_path):
                        os.remove(backup_path)
                    
                    comparison = ""
                    if self.mode == "log_process" and foobar_md5:
                        if pcm_md5_before == foobar_md5:
                            comparison = "匹配"
                        else:
                            comparison = "不匹配"
                            
                    success_count += 1
                    detail_msg = warning_msg
                    if self.mode == "log_process":
                        detail_msg = f"{comparison}; {warning_msg}".strip("; ")
                        self.file_processed.emit(ui_key, "修复成功", pcm_md5_before, foobar_md5, detail_msg)
                    else:
                        self.file_processed.emit(ui_key, "修复成功", pcm_md5_before, pcm_md5_after, detail_msg)
                    
                except Exception as e:
                    fail_count += 1
                    # 恢复备份
                    if os.path.exists(backup_path):
                        shutil.move(backup_path, filepath)
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    self.file_processed.emit(ui_key, "失败", "-", "-", str(e))
        self.finished_all.emit(success_count, fail_count)

class DropArea(QLabel):
    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DropArea")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("【 将无损 FLAC 文件或文件夹拖放到此处 】")
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("dragged", "true")
            self.style().unpolish(self)
            self.style().polish(self)

    def dragLeaveEvent(self, event):
        self.setProperty("dragged", "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, event: QDropEvent):
        self.setProperty("dragged", "false")
        self.style().unpolish(self)
        self.style().polish(self)
        
        urls = event.mimeData().urls()
        paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
        if paths:
            self.files_dropped.emit(paths)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FLAC 音频流重构与垃圾标签清理工具")
        self.resize(1000, 700)
        self.setStyleSheet(DARK_STYLE)
        
        self.log_mode = False
        self.log_items = []
        
        central_widget = QWidget()
        central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)
        
        title_layout = QHBoxLayout()
        title_label = QLabel("FLAC 无损重写与定位表优化工具")
        title_label.setObjectName("TitleLabel")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        self.clear_btn = QPushButton("清空列表")
        self.clear_btn.setObjectName("ClearBtn")
        self.clear_btn.clicked.connect(self.clear_table)
        title_layout.addWidget(self.clear_btn)
        
        layout.addLayout(title_layout)

        # 模式选择布局
        mode_layout = QHBoxLayout()
        mode_label = QLabel("工作模式：")
        mode_label.setStyleSheet("color: #00ADB5; font-weight: bold; font-size: 13px;")
        
        self.rebuild_radio = QRadioButton("重构清理音频 (优化定位表、写入文件)")
        self.rebuild_radio.setChecked(True)
        self.smart_radio = QRadioButton("智能重构 (仅在需要优化布局时重构并校验，否则仅校验)")
        self.hash_radio = QRadioButton("仅计算真实 PCM MD5 (只读测试、不修改文件)")
        
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.rebuild_radio)
        mode_layout.addWidget(self.smart_radio)
        mode_layout.addWidget(self.hash_radio)
        mode_layout.addStretch()
        
        layout.addLayout(mode_layout)
        
        self.rebuild_radio.toggled.connect(self.on_mode_changed)
        self.smart_radio.toggled.connect(self.on_mode_changed)

        # 操作工具栏布局
        action_layout = QHBoxLayout()
        self.btn_import_log = QPushButton("导入 Foobar 日志")
        self.btn_import_log.clicked.connect(self.import_foobar_log)
        
        self.btn_select_warning = QPushButton("仅选警告项")
        self.btn_select_warning.clicked.connect(self.select_warning_items)
        self.btn_select_warning.setEnabled(False)
        
        self.btn_select_all = QPushButton("全选")
        self.btn_select_all.clicked.connect(lambda: self.set_all_checked(True))
        self.btn_select_all.setEnabled(False)
        
        self.btn_deselect_all = QPushButton("全不选")
        self.btn_deselect_all.clicked.connect(lambda: self.set_all_checked(False))
        self.btn_deselect_all.setEnabled(False)
        
        self.btn_rebuild_selected = QPushButton("批量重构选中项")
        self.btn_rebuild_selected.setObjectName("PrimaryBtn")
        self.btn_rebuild_selected.clicked.connect(self.rebuild_selected_items)
        self.btn_rebuild_selected.setEnabled(False)
        
        action_layout.addWidget(self.btn_import_log)
        action_layout.addWidget(self.btn_select_warning)
        action_layout.addWidget(self.btn_select_all)
        action_layout.addWidget(self.btn_deselect_all)
        action_layout.addStretch()
        action_layout.addWidget(self.btn_rebuild_selected)
        
        layout.addLayout(action_layout)
        
        self.drop_area = DropArea()
        self.drop_area.setFixedHeight(120)
        self.drop_area.files_dropped.connect(self.on_files_dropped)
        layout.addWidget(self.drop_area)
        
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "选择", "音乐文件名", "问题/警告", "处理前 PCM MD5", "处理后 PCM MD5", "校验对比", "处理状态"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 220)
        self.table.setColumnWidth(2, 160)
        self.table.setColumnWidth(3, 200)
        self.table.setColumnWidth(4, 200)
        self.table.setColumnWidth(5, 80)
        self.table.setColumnWidth(6, 90)
        
        layout.addWidget(self.table)
        
        self.thread = None
        self.file_row_map = {}

    def on_mode_changed(self):
        if self.log_mode:
            self.table.setHorizontalHeaderLabels([
                "选择", "音乐文件名", "警告类型", "Foobar 标注 MD5", "计算 PCM MD5", "校验对比", "处理状态"
            ])
        else:
            if self.rebuild_radio.isChecked() or self.smart_radio.isChecked():
                self.table.setHorizontalHeaderLabels([
                    "选择", "音乐文件名", "问题/警告", "处理前 PCM MD5", "处理后 PCM MD5", "校验对比", "处理状态"
                ])
                self.btn_rebuild_selected.setText("批量重构选中项" if self.rebuild_radio.isChecked() else "智能重构选中项")
            else:
                self.table.setHorizontalHeaderLabels([
                    "选择", "音乐文件名", "问题/警告", "真实 PCM MD5", "采样率/位深", "校验对比", "处理状态"
                ])
                self.btn_rebuild_selected.setText("批量计算选中项")

    def clear_table(self):
        self.table.setRowCount(0)
        self.file_row_map.clear()
        self.log_mode = False
        self.log_items = []
        
        self.on_mode_changed()
        self.drop_area.setText("【 将无损 FLAC 文件或文件夹拖放到此处 】")
        self.btn_select_warning.setEnabled(False)
        self.btn_select_all.setEnabled(False)
        self.btn_deselect_all.setEnabled(False)
        self.btn_rebuild_selected.setEnabled(False)
        self.rebuild_radio.setEnabled(True)
        self.smart_radio.setEnabled(True)
        self.hash_radio.setEnabled(True)

    def import_foobar_log(self):
        if self.thread and self.thread.isRunning():
            QMessageBox.warning(self, "警告", "当前有任务正在运行中，请等待其处理完成！")
            return
            
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入 Foobar2000 检测日志", "", "Text Files (*.txt *.log);;All Files (*)"
        )
        if not file_path:
            return
            
        self.log_items = parse_foobar_log(file_path)
        if not self.log_items:
            QMessageBox.warning(self, "警告", "未能从日志中解析出有效的歌曲项目，请检查文件格式。")
            return
            
        self.log_mode = True
        self.table.setRowCount(0)
        self.file_row_map.clear()
        
        self.on_mode_changed()
        
        for item in self.log_items:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            self.file_row_map[item["path"]] = row
            
            chk_box = QCheckBox()
            has_warning = bool(item["warning"])
            chk_box.setChecked(has_warning)
            
            widget = QWidget()
            h_layout = QHBoxLayout(widget)
            h_layout.addWidget(chk_box)
            h_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            h_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 0, widget)
            
            self.table.setItem(row, 1, QTableWidgetItem(os.path.basename(item["path"])))
            
            warning_text = item["warning"] if item["warning"] else "无找到问题"
            warning_item = QTableWidgetItem(warning_text)
            if item["warning"]:
                warning_item.setForeground(QColor("#FFE17D"))
            else:
                warning_item.setForeground(QColor("#777777"))
            self.table.setItem(row, 2, warning_item)
            
            foobar_md5_item = QTableWidgetItem(item["foobar_md5"] if item["foobar_md5"] else "-")
            foobar_md5_item.setForeground(QColor("#CCCCCC"))
            self.table.setItem(row, 3, foobar_md5_item)
            
            self.table.setItem(row, 4, QTableWidgetItem("-"))
            self.table.setItem(row, 5, QTableWidgetItem("-"))
            self.table.setItem(row, 6, QTableWidgetItem("未处理"))
            
        self.drop_area.setText("【 日志已加载：请使用下方按钮进行处理，或清空列表切换回拖放模式 】")
        self.btn_select_warning.setEnabled(True)
        self.btn_select_all.setEnabled(True)
        self.btn_deselect_all.setEnabled(True)
        self.btn_rebuild_selected.setEnabled(True)
        self.rebuild_radio.setEnabled(False)
        self.smart_radio.setEnabled(False)
        self.hash_radio.setEnabled(False)
        
        warning_count = sum(1 for x in self.log_items if x['warning'])
        QMessageBox.information(
            self, "导入成功", 
            f"成功从日志中导入了 {len(self.log_items)} 首歌曲。\n其中有警告的歌曲共计 {warning_count} 首，已自动勾选。"
        )

    def set_all_checked(self, checked):
        for row in range(self.table.rowCount()):
            cell_widget = self.table.cellWidget(row, 0)
            if cell_widget:
                chk = cell_widget.layout().itemAt(0).widget()
                chk.setChecked(checked)
                
    def select_warning_items(self):
        for row in range(self.table.rowCount()):
            warning_text = self.table.item(row, 2).text()
            cell_widget = self.table.cellWidget(row, 0)
            if cell_widget:
                chk = cell_widget.layout().itemAt(0).widget()
                chk.setChecked(warning_text != "无找到问题")

    def rebuild_selected_items(self):
        if self.thread and self.thread.isRunning():
            QMessageBox.warning(self, "警告", "当前有任务正在运行中，请等待其处理完成！")
            return
            
        selected_paths = []
        
        if self.log_mode:
            mode = "log_process"
            for row in range(self.table.rowCount()):
                cell_widget = self.table.cellWidget(row, 0)
                if cell_widget:
                    chk = cell_widget.layout().itemAt(0).widget()
                    if chk.isChecked():
                        path = self.log_items[row]["path"]
                        foobar_md5 = self.log_items[row]["foobar_md5"]
                        selected_paths.append({"path": path, "foobar_md5": foobar_md5})
        else:
            if self.rebuild_radio.isChecked():
                mode = "rebuild"
            elif self.smart_radio.isChecked():
                mode = "smart_rebuild"
            else:
                mode = "hash_only"
            # 建立行号到路径的映射
            row_to_path = {v: k for k, v in self.file_row_map.items()}
            for row in range(self.table.rowCount()):
                cell_widget = self.table.cellWidget(row, 0)
                if cell_widget:
                    chk = cell_widget.layout().itemAt(0).widget()
                    if chk.isChecked():
                        filepath = row_to_path.get(row)
                        if filepath:
                            selected_paths.append({"path": filepath, "foobar_md5": ""})
                            
        if not selected_paths:
            QMessageBox.warning(self, "警告", "请先选择需要处理的文件！")
            return
            
        if mode == "hash_only":
            self.drop_area.setText("正在计算音频 MD5 校验码，请稍候...")
        elif mode == "smart_rebuild":
            self.drop_area.setText("正在智能检测并重构音频布局，请稍候...")
        else:
            self.drop_area.setText("正在执行重构清理中，请稍候...")
            
        self.drop_area.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self.btn_import_log.setEnabled(False)
        self.btn_select_warning.setEnabled(False)
        self.btn_select_all.setEnabled(False)
        self.btn_deselect_all.setEnabled(False)
        self.btn_rebuild_selected.setEnabled(False)
        self.rebuild_radio.setEnabled(False)
        self.smart_radio.setEnabled(False)
        self.hash_radio.setEnabled(False)
        
        self.thread = RebuildThread(selected_paths, mode)
        self.thread.file_processed.connect(self.update_file_status)
        self.thread.finished_all.connect(self.on_finished_all)
        self.thread.confirm_request.connect(self.handle_confirm_request)
        self.thread.start()

    def on_files_dropped(self, paths):
        if self.log_mode:
            QMessageBox.warning(self, "警告", "当前处于 Foobar 日志模式，请先点击“清空列表”恢复常规拖放处理模式！")
            return
            
        if self.thread and self.thread.isRunning():
            QMessageBox.warning(self, "警告", "当前有任务正在运行中，请等待其处理完成！")
            return
            
        flac_files = []
        for path in paths:
            if os.path.isdir(path):
                for root, _, files in os.walk(path):
                    for file in files:
                        if file.lower().endswith('.flac'):
                            flac_files.append(os.path.join(root, file))
            else:
                if path.lower().endswith('.flac'):
                    flac_files.append(path)
                    
        if not flac_files:
            QMessageBox.warning(self, "提示", "未能在拖入路径中找到任何 .flac 无损音频！")
            return
            
        for filepath in flac_files:
            if filepath in self.file_row_map:
                continue
                
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.file_row_map[filepath] = row
            
            chk_box = QCheckBox()
            
            widget = QWidget()
            h_layout = QHBoxLayout(widget)
            h_layout.addWidget(chk_box)
            h_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            h_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 0, widget)
            
            self.table.setItem(row, 1, QTableWidgetItem(os.path.basename(filepath)))
            
            # 自动检测是否需要优化布局，并在界面上实时呈现
            issues = check_flac_layout_issues(filepath)
            if issues:
                warning_text = "; ".join(issues)
                warning_item = QTableWidgetItem(warning_text)
                warning_item.setForeground(QColor("#FFE17D")) # 黄色警告
                chk_box.setChecked(True) # 有警告项默认勾选
            else:
                warning_item = QTableWidgetItem("布局优秀")
                warning_item.setForeground(QColor("#00FFD1")) # 亮绿色表示完美
                chk_box.setChecked(False) # 正常项默认不勾选，节省处理资源
            self.table.setItem(row, 2, warning_item)
            
            self.table.setItem(row, 3, QTableWidgetItem("-"))
            self.table.setItem(row, 4, QTableWidgetItem("-"))
            self.table.setItem(row, 5, QTableWidgetItem("-"))
            self.table.setItem(row, 6, QTableWidgetItem("未处理"))
            
        self.btn_select_all.setEnabled(True)
        self.btn_deselect_all.setEnabled(True)
        self.btn_rebuild_selected.setEnabled(True)

    def handle_confirm_request(self, filepath, size_before, size_after):
        diff_mb = abs(size_before - size_after) / (1024 * 1024)
        filename = os.path.basename(filepath)
        reply = QMessageBox.question(
            self, "文件大小变动警告",
            f"音频文件 '{filename}' 重构后大小变动了 {diff_mb:.2f} MB。\n"
            f"  - 处理前大小: {size_before/1024/1024:.2f} MB\n"
            f"  - 处理后大小: {size_after/1024/1024:.2f} MB\n\n"
            f"是否确认应用此更改并覆盖原文件？\n(选择‘否’将撤销修改并回滚)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if self.thread:
            self.thread.confirm_result = (reply == QMessageBox.StandardButton.Yes)

    def update_file_status(self, filename, status, pcm_before, pcm_after, error_msg):
        # 这里的 filename 即文件绝对路径 ui_key
        if filename not in self.file_row_map:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.file_row_map[filename] = row
            
            chk_box = QCheckBox()
            chk_box.setChecked(True)
            widget = QWidget()
            h_layout = QHBoxLayout(widget)
            h_layout.addWidget(chk_box)
            h_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            h_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 0, widget)
            
            self.table.setItem(row, 1, QTableWidgetItem(os.path.basename(filename)))
            self.table.setItem(row, 2, QTableWidgetItem("常规拖入"))
            self.table.setItem(row, 3, QTableWidgetItem("-"))
            self.table.setItem(row, 4, QTableWidgetItem("-"))
            self.table.setItem(row, 5, QTableWidgetItem("-"))
            self.table.setItem(row, 6, QTableWidgetItem("未处理"))
            
        row = self.file_row_map[filename]
        
        if self.log_mode:
            # 4: 计算 PCM MD5 (存放我们算出来的 pcm_before)
            # 5: 校验对比 (存放 error_msg)
            # 6: 处理状态 (存放 status)
            self.table.setItem(row, 4, QTableWidgetItem(pcm_before))
            
            comp_item = QTableWidgetItem(error_msg)
            if "不匹配" in error_msg:
                comp_item.setForeground(QColor("#FF4C4C"))
            else:
                comp_item.setForeground(QColor("#00FFD1"))
            self.table.setItem(row, 5, comp_item)
            
            self.table.setItem(row, 6, QTableWidgetItem(status))
        else:
            if self.rebuild_radio.isChecked():
                mode = "rebuild"
            elif self.smart_radio.isChecked():
                mode = "smart_rebuild"
            else:
                mode = "hash_only"
                
            if mode in ["rebuild", "smart_rebuild"]:
                if status == "无需优化":
                    self.table.setItem(row, 3, QTableWidgetItem(pcm_before))
                    self.table.setItem(row, 4, QTableWidgetItem(pcm_before))
                    comp_item = QTableWidgetItem("一致")
                    comp_item.setForeground(QColor("#00FFD1"))
                    self.table.setItem(row, 5, comp_item)
                else:
                    # 3: 原 PCM MD5 (pcm_before)
                    # 4: 新 PCM MD5 (pcm_after)
                    # 5: 校验对比
                    self.table.setItem(row, 3, QTableWidgetItem(pcm_before))
                    self.table.setItem(row, 4, QTableWidgetItem(pcm_after))
                    
                    comp_text = "一致" if "成功" in status or status == "无需优化" else "有变动"
                    comp_item = QTableWidgetItem(comp_text)
                    if "成功" in status or status == "无需优化":
                        comp_item.setForeground(QColor("#00FFD1"))
                    else:
                        comp_item.setForeground(QColor("#FF4C4C"))
                    self.table.setItem(row, 5, comp_item)
            else:
                # 3: 真实 PCM MD5 (pcm_before)
                # 4: 采样率/位深 (pcm_after)
                # 5: 校验对比
                self.table.setItem(row, 3, QTableWidgetItem(pcm_before))
                self.table.setItem(row, 4, QTableWidgetItem(pcm_after))
                self.table.setItem(row, 5, QTableWidgetItem("-"))
                
            self.table.setItem(row, 6, QTableWidgetItem(status))

        row = self.file_row_map[filename]
        status_item = self.table.item(row, 6)
        if "成功" in status or "已计算" in status:
            status_item.setForeground(QColor("#00FFD1"))
        elif "失败" in status:
            status_item.setForeground(QColor("#FF4C4C"))
            self.table.item(row, 5).setForeground(QColor("#FF4C4C"))
        elif "处理中" in status or "计算中" in status:
            status_item.setForeground(QColor("#FFE17D"))

    def on_finished_all(self, success, fail):
        self.drop_area.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.btn_import_log.setEnabled(True)
        
        self.btn_select_all.setEnabled(True)
        self.btn_deselect_all.setEnabled(True)
        self.btn_rebuild_selected.setEnabled(True)
        
        if self.log_mode:
            self.btn_select_warning.setEnabled(True)
            self.drop_area.setText("【 日志已加载：请使用下方按钮进行处理，或清空列表切换回拖放模式 】")
        else:
            self.rebuild_radio.setEnabled(True)
            self.smart_radio.setEnabled(True)
            self.hash_radio.setEnabled(True)
            self.drop_area.setText("【 将无损 FLAC 文件或文件夹拖放到此处 】")
            
        QMessageBox.information(self, "提示", f"任务处理完毕！\n成功: {success} 首\n失败: {fail} 首")

def parse_foobar_log(log_path):
    items = []
    try:
        with open(log_path, "r", encoding="utf-8-sig") as f:
            content = f.read()
    except Exception:
        try:
            with open(log_path, "r", encoding="gbk") as f:
                content = f.read()
        except Exception:
            return []
            
    blocks = content.split("\n\n")
    for block in blocks:
        if not block.strip():
            continue
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue
            
        path = ""
        foobar_md5 = ""
        warnings = []
        for line in lines:
            if line.startswith("项目:"):
                m = re.match(r'项目:\s*"(.*)"', line)
                if m:
                    path = m.group(1)
                else:
                    path = line.replace("项目:", "").strip()
            elif line.startswith("MD5:"):
                foobar_md5 = line.replace("MD5:", "").strip().upper()
            elif line.startswith("CRC32:") or "无找到问题" in line:
                continue
            else:
                warnings.append(line)
        
        if path:
            warning_text = "; ".join(warnings) if warnings else ""
            items.append({
                "path": path,
                "foobar_md5": foobar_md5,
                "warning": warning_text
            })
    return items


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    
    if len(sys.argv) > 1:
        paths = sys.argv[1:]
        window.on_files_dropped(paths)
        
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
