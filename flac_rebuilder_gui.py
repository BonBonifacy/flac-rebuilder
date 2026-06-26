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
import numpy as np
import soundfile as sf
from mutagen.flac import FLAC
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
                             QAbstractItemView, QHBoxLayout, QPushButton, QMessageBox,
                             QRadioButton)
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
"""

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
    # 定义信号：(文件名, 状态, 处理前MD5, 处理后MD5, 错误说明)
    file_processed = pyqtSignal(str, str, str, str, str)
    finished_all = pyqtSignal(int, int)

    def __init__(self, paths, mode="rebuild"):
        super().__init__()
        self.paths = paths
        self.mode = mode

    def run(self):
        flac_files = []
        for path in self.paths:
            if os.path.isdir(path):
                for root, _, files in os.walk(path):
                    for file in files:
                        if file.lower().endswith('.flac'):
                            flac_files.append(os.path.join(root, file))
            else:
                if path.lower().endswith('.flac'):
                    flac_files.append(path)

        success_count = 0
        fail_count = 0

        for filepath in flac_files:
            filename = os.path.basename(filepath)
            
            if self.mode == "hash_only":
                self.file_processed.emit(filename, "计算中...", "-", "-", "")
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
                    self.file_processed.emit(filename, "已计算", pcm_md5, f"{original_samplerate}Hz / {original_subtype}", "")
                except Exception as e:
                    fail_count += 1
                    self.file_processed.emit(filename, "失败", "-", "-", str(e))
            else:
                self.file_processed.emit(filename, "处理中...", "-", "-", "")
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
                    sf.write(temp_path, data, samplerate, format='FLAC', subtype=original_subtype)
                    
                    # 5. 还原元数据与封面
                    new_audio = FLAC(temp_path)
                    new_audio.tags.clear()
                    for k, v in tags.items():
                        new_audio.tags[k] = v
                    for pic in pics:
                        new_audio.add_picture(pic)
                    # 写入 0 填充以最小化体积，且由于 mutagen 写入，标签天然位于文件头部（优化布局完成）
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
                    
                    success_count += 1
                    self.file_processed.emit(filename, "修复成功", pcm_md5_before, pcm_md5_after, warning_msg)
                    
                except Exception as e:
                    fail_count += 1
                    # 恢复备份
                    if os.path.exists(backup_path):
                        shutil.move(backup_path, filepath)
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    self.file_processed.emit(filename, "失败", "-", "-", str(e))

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
        self.resize(900, 650)
        self.setStyleSheet(DARK_STYLE)
        
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
        self.hash_radio = QRadioButton("仅计算真实 PCM MD5 (只读测试、不修改文件)")
        
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.rebuild_radio)
        mode_layout.addWidget(self.hash_radio)
        mode_layout.addStretch()
        
        layout.addLayout(mode_layout)
        
        self.rebuild_radio.toggled.connect(self.on_mode_changed)
        
        self.drop_area = DropArea()
        self.drop_area.setFixedHeight(120)
        self.drop_area.files_dropped.connect(self.on_files_dropped)
        layout.addWidget(self.drop_area)
        
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["音乐文件名", "状态", "处理前 PCM MD5", "处理后 PCM MD5", "详情/失败原因"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        self.table.setColumnWidth(0, 240)
        self.table.setColumnWidth(1, 90)
        self.table.setColumnWidth(2, 210)
        self.table.setColumnWidth(3, 210)
        
        layout.addWidget(self.table)
        
        self.thread = None
        self.file_row_map = {}

    def on_mode_changed(self):
        if self.rebuild_radio.isChecked():
            self.table.setHorizontalHeaderLabels(["音乐文件名", "状态", "处理前 PCM MD5", "处理后 PCM MD5", "详情/失败原因"])
        else:
            self.table.setHorizontalHeaderLabels(["音乐文件名", "状态", "真实 PCM MD5", "采样率/位深", "详情/失败原因"])

    def clear_table(self):
        self.table.setRowCount(0)
        self.file_row_map.clear()

    def on_files_dropped(self, paths):
        if self.thread and self.thread.isRunning():
            QMessageBox.warning(self, "警告", "当前有任务正在运行中，请等待其处理完成！")
            return
            
        mode = "rebuild" if self.rebuild_radio.isChecked() else "hash_only"
        
        if mode == "hash_only":
            self.drop_area.setText("正在计算音频 MD5 校验码，请稍候...")
        else:
            self.drop_area.setText("正在执行重构清理中，请稍候...")
            
        self.drop_area.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self.rebuild_radio.setEnabled(False)
        self.hash_radio.setEnabled(False)
        
        self.thread = RebuildThread(paths, mode)
        self.thread.file_processed.connect(self.update_file_status)
        self.thread.finished_all.connect(self.on_finished_all)
        self.thread.start()

    def update_file_status(self, filename, status, pcm_before, pcm_after, error_msg):
        if filename not in self.file_row_map:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.file_row_map[filename] = row
            
            self.table.setItem(row, 0, QTableWidgetItem(filename))
            self.table.setItem(row, 1, QTableWidgetItem(status))
            self.table.setItem(row, 2, QTableWidgetItem(pcm_before))
            self.table.setItem(row, 3, QTableWidgetItem(pcm_after))
            self.table.setItem(row, 4, QTableWidgetItem(error_msg))
        else:
            row = self.file_row_map[filename]
            self.table.item(row, 1).setText(status)
            self.table.item(row, 2).setText(pcm_before)
            self.table.item(row, 3).setText(pcm_after)
            self.table.item(row, 4).setText(error_msg)

        status_item = self.table.item(row, 1)
        if "成功" in status or "已计算" in status:
            status_item.setForeground(QColor("#00FFD1"))
        elif "失败" in status:
            status_item.setForeground(QColor("#FF4C4C"))
            self.table.item(row, 4).setForeground(QColor("#FF4C4C"))
        elif "处理中" in status or "计算中" in status:
            status_item.setForeground(QColor("#FFE17D"))

    def on_finished_all(self, success, fail):
        self.drop_area.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.rebuild_radio.setEnabled(True)
        self.hash_radio.setEnabled(True)
        self.drop_area.setText("【 将无损 FLAC 文件或文件夹拖放到此处 】")
        QMessageBox.information(self, "提示", f"任务处理完毕！\n成功: {success} 首\n失败: {fail} 首")

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
