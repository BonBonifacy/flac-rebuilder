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
            for path in self.paths:
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

            if self.mode == "hash_only":
                self.file_processed.emit(ui_key, "计算中...", "-", "-", "")
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
                    self.file_processed.emit(ui_key, "已计算", pcm_md5, f"{original_samplerate}Hz / {original_subtype}", "")
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
                    sf.write(temp_path, data, samplerate, format='FLAC', subtype=original_subtype)
                    
                    # 5. 还原元数据与封面
                    new_audio = FLAC(temp_path)
                    new_audio.tags.clear()
                    for k, v in tags.items():
                        new_audio.tags[k] = v
                    for pic in pics:
                        new_audio.add_picture(pic)
                    new_audio.save(padding=lambda info: 0)
                    
                    # 5.5 检测文件大小变动是否异常
                    size_before = os.path.getsize(filepath)
                    size_after = os.path.getsize(temp_path)
                    if size_before > 0:
                        ratio = size_after / size_before
                        if ratio < 0.75 or ratio > 1.15:
                            raise ValueError(
                                f"文件体积异常变化！处理后大小为原文件的 {ratio:.1%} "
                                f"(原: {size_before/1024/1024:.2f}MB, 新: {size_after/1024/1024:.2f}MB)"
                            )
                    
                    # 5.6 检测文件大小变动是否超过 10MB，如果是，发射信号请求确认并阻塞等待
                    diff_bytes = abs(size_before - size_after)
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
                    if self.mode == "log_process":
                        self.file_processed.emit(ui_key, "修复成功", pcm_md5_before, foobar_md5, comparison)
                    else:
                        self.file_processed.emit(ui_key, "修复成功", pcm_md5_before, pcm_md5_after, "")
                    
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
        self.hash_radio = QRadioButton("仅计算真实 PCM MD5 (只读测试、不修改文件)")
        
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.rebuild_radio)
        mode_layout.addWidget(self.hash_radio)
        mode_layout.addStretch()
        
        layout.addLayout(mode_layout)
        
        self.rebuild_radio.toggled.connect(self.on_mode_changed)

        # 日志操作栏布局
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
        if self.log_mode:
            return
        if self.rebuild_radio.isChecked():
            self.table.setHorizontalHeaderLabels(["音乐文件名", "状态", "处理前 PCM MD5", "处理后 PCM MD5", "详情/失败原因"])
        else:
            self.table.setHorizontalHeaderLabels(["音乐文件名", "状态", "真实 PCM MD5", "采样率/位深", "详情/失败原因"])

    def clear_table(self):
        self.table.setRowCount(0)
        self.file_row_map.clear()
        self.log_mode = False
        self.log_items = []
        
        # 恢复常规模式下的表格列头
        self.table.setColumnCount(5)
        self.on_mode_changed()
        self.table.setColumnWidth(0, 240)
        self.table.setColumnWidth(1, 90)
        self.table.setColumnWidth(2, 210)
        self.table.setColumnWidth(3, 210)
        
        self.drop_area.setText("【 将无损 FLAC 文件或文件夹拖放到此处 】")
        self.btn_select_warning.setEnabled(False)
        self.btn_select_all.setEnabled(False)
        self.btn_deselect_all.setEnabled(False)
        self.btn_rebuild_selected.setEnabled(False)
        self.rebuild_radio.setEnabled(True)
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
        
        # 切换表格为日志处理展示的 7 列
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "选择", "音乐文件名", "警告类型", "Foobar 标注 MD5", "计算 PCM MD5", "校验对比", "处理状态"
        ])
        
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 220)
        self.table.setColumnWidth(2, 160)
        self.table.setColumnWidth(3, 200)
        self.table.setColumnWidth(4, 200)
        self.table.setColumnWidth(5, 80)
        self.table.setColumnWidth(6, 90)
        
        for item in self.log_items:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # 使用文件绝对路径作为 file_row_map 的 key
            self.file_row_map[item["path"]] = row
            
            # 1. 选择 CheckBox
            chk_box = QCheckBox()
            # 默认勾选有警告项
            has_warning = bool(item["warning"])
            chk_box.setChecked(has_warning)
            
            widget = QWidget()
            h_layout = QHBoxLayout(widget)
            h_layout.addWidget(chk_box)
            h_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            h_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 0, widget)
            
            # 2. 音乐文件名
            self.table.setItem(row, 1, QTableWidgetItem(os.path.basename(item["path"])))
            
            # 3. 警告类型
            warning_text = item["warning"] if item["warning"] else "无找到问题"
            warning_item = QTableWidgetItem(warning_text)
            if item["warning"]:
                warning_item.setForeground(QColor("#FFE17D"))
            else:
                warning_item.setForeground(QColor("#777777"))
            self.table.setItem(row, 2, warning_item)
            
            # 4. Foobar MD5
            foobar_md5_item = QTableWidgetItem(item["foobar_md5"] if item["foobar_md5"] else "-")
            foobar_md5_item.setForeground(QColor("#CCCCCC"))
            self.table.setItem(row, 3, foobar_md5_item)
            
            # 5. 计算 PCM MD5
            self.table.setItem(row, 4, QTableWidgetItem("-"))
            
            # 6. 校验对比
            self.table.setItem(row, 5, QTableWidgetItem("-"))
            
            # 7. 处理状态
            self.table.setItem(row, 6, QTableWidgetItem("未处理"))
            
        self.drop_area.setText("【 日志已加载：请使用下方按钮进行处理，或清空列表切换回拖放模式 】")
        self.btn_select_warning.setEnabled(True)
        self.btn_select_all.setEnabled(True)
        self.btn_deselect_all.setEnabled(True)
        self.btn_rebuild_selected.setEnabled(True)
        self.rebuild_radio.setEnabled(False)
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
        for row in range(self.table.rowCount()):
            cell_widget = self.table.cellWidget(row, 0)
            if cell_widget:
                chk = cell_widget.layout().itemAt(0).widget()
                if chk.isChecked():
                    path = self.log_items[row]["path"]
                    foobar_md5 = self.log_items[row]["foobar_md5"]
                    selected_paths.append({"path": path, "foobar_md5": foobar_md5})
                    
        if not selected_paths:
            QMessageBox.warning(self, "警告", "请先选择需要重构的文件！")
            return
            
        self.drop_area.setText("正在执行勾选项目重构校验中，请稍候...")
        self.drop_area.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self.btn_import_log.setEnabled(False)
        self.btn_select_warning.setEnabled(False)
        self.btn_select_all.setEnabled(False)
        self.btn_deselect_all.setEnabled(False)
        self.btn_rebuild_selected.setEnabled(False)
        
        self.thread = RebuildThread(selected_paths, "log_process")
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
        self.thread.confirm_request.connect(self.handle_confirm_request)
        self.thread.start()

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
            
            if self.log_mode:
                self.table.setItem(row, 1, QTableWidgetItem(os.path.basename(filename)))
                self.table.setItem(row, 6, QTableWidgetItem(status))
            else:
                self.table.setItem(row, 0, QTableWidgetItem(os.path.basename(filename)))
                self.table.setItem(row, 1, QTableWidgetItem(status))
                self.table.setItem(row, 2, QTableWidgetItem(pcm_before))
                self.table.setItem(row, 3, QTableWidgetItem(pcm_after))
                self.table.setItem(row, 4, QTableWidgetItem(error_msg))
        else:
            row = self.file_row_map[filename]
            if self.log_mode:
                # 0: 选择 (CellWidget)
                # 1: 音乐文件名
                # 2: 警告类型 (已填)
                # 3: Foobar 标注 MD5 (已填)
                # 4: 计算 PCM MD5 (更新为计算出的 pcm_before)
                # 5: 校验对比 (更新为对比结果 error_msg)
                # 6: 处理状态 (更新为状态 status)
                self.table.setItem(row, 4, QTableWidgetItem(pcm_before))
                
                comp_item = QTableWidgetItem(error_msg)
                if "不匹配" in error_msg:
                    comp_item.setForeground(QColor("#FF4C4C"))
                else:
                    comp_item.setForeground(QColor("#00FFD1"))
                self.table.setItem(row, 5, comp_item)
                
                self.table.setItem(row, 6, QTableWidgetItem(status))
            else:
                self.table.item(row, 1).setText(status)
                self.table.item(row, 2).setText(pcm_before)
                self.table.item(row, 3).setText(pcm_after)
                self.table.item(row, 4).setText(error_msg)

        row = self.file_row_map[filename]
        status_item = self.table.item(row, 6 if self.log_mode else 1)
        if "成功" in status or "已计算" in status:
            status_item.setForeground(QColor("#00FFD1"))
        elif "失败" in status:
            status_item.setForeground(QColor("#FF4C4C"))
            self.table.item(row, 4 if not self.log_mode else 5).setForeground(QColor("#FF4C4C"))
        elif "处理中" in status or "计算中" in status:
            status_item.setForeground(QColor("#FFE17D"))

    def on_finished_all(self, success, fail):
        self.drop_area.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.btn_import_log.setEnabled(True)
        
        if self.log_mode:
            self.btn_select_warning.setEnabled(True)
            self.btn_select_all.setEnabled(True)
            self.btn_deselect_all.setEnabled(True)
            self.btn_rebuild_selected.setEnabled(True)
            self.drop_area.setText("【 日志已加载：请使用下方按钮进行处理，或清空列表切换回拖放模式 】")
        else:
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
