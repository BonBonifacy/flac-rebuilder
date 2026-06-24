# /// script
# dependencies = [
#     "mutagen",
#     "soundfile",
#     "numpy",
#     "pyinstaller",
# ]
# ///

import os
import sys
import hashlib
import shutil
import soundfile as sf
from mutagen.flac import FLAC

# 解决 Windows 命令行中文乱码
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def get_pcm_md5(filepath):
    """解码 FLAC 并计算 PCM 数据 MD5"""
    data, _ = sf.read(filepath, dtype='int16')
    return hashlib.md5(data.tobytes()).hexdigest().upper()

def process_file(filepath):
    filename = os.path.basename(filepath)
    print("=" * 60)
    print(f"正在处理: {filename}")
    
    ext = os.path.splitext(filepath)[1].lower()
    if ext != '.flac':
        print("  [跳过] 本程序仅支持处理 .flac 格式文件。")
        return False
        
    temp_path = filepath + ".tmp"
    backup_path = filepath + ".bak"
    
    try:
        # 1. 备份原文件 (以防万一)
        shutil.copy2(filepath, backup_path)
        
        # 2. 读取原始元数据与封面
        original_audio = FLAC(filepath)
        original_tags = dict(original_audio.tags)
        original_pictures = list(original_audio.pictures)
        
        # 3. 计算处理前真实 PCM MD5
        pcm_md5_before = get_pcm_md5(filepath)
        print(f"  - 处理前 PCM MD5: {pcm_md5_before}")
        
        # 4. 用 soundfile 重新编码音频流，剔除尾部垃圾
        data, samplerate = sf.read(filepath, dtype='int16')
        sf.write(temp_path, data, samplerate, format='FLAC')
        
        # 5. 还原元数据和封面
        new_audio = FLAC(temp_path)
        new_audio.tags.clear()
        for k, v in original_tags.items():
            new_audio.tags[k] = v
        for pic in original_pictures:
            new_audio.add_picture(pic)
        new_audio.save()
        
        # 6. 计算并校验处理后 PCM MD5
        pcm_md5_after = get_pcm_md5(temp_path)
        print(f"  - 处理后 PCM MD5: {pcm_md5_after}")
        
        if pcm_md5_before != pcm_md5_after:
            raise ValueError(f"PCM MD5 发生改变！原: {pcm_md5_before}, 新: {pcm_md5_after}")
            
        # 7. 替换原文件并清理备份
        shutil.move(temp_path, filepath)
        if os.path.exists(backup_path):
            os.remove(backup_path)
        
        print("  - [状态] 修复成功！(有效标签已保留，垃圾已剥离，音质无损)")
        return True
        
    except Exception as e:
        print(f"  - [错误] 修复失败: {e}")
        # 发生异常，自动还原备份
        if os.path.exists(backup_path):
            shutil.move(backup_path, filepath)
            print("  - 已自动恢复原始文件。")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False

def main():
    print("=" * 60)
    print("        FLAC 音频流重构与垃圾标签清理工具 (Drag & Drop)")
    print("=" * 60)
    
    # 拖入的文件会以命令行参数 sys.argv 形式传入
    file_list = sys.argv[1:]
    
    if not file_list:
        print("\n[提示] 使用方法：")
        print("  请直接将一个或多个 FLAC 文件拖放到此程序的图标（或快捷方式）上运行。")
        print("\n按回车键退出...")
        input()
        return

    print(f"共检测到 {len(file_list)} 个拖入的文件，开始处理...\n")
    
    success_count = 0
    fail_count = 0
    
    for filepath in file_list:
        filepath = filepath.strip('"').strip("'")
        if os.path.isdir(filepath):
            # 如果拖入的是目录，则递归处理目录下的 flac 文件
            for root, _, files in os.walk(filepath):
                for file in files:
                    if file.lower().endswith('.flac'):
                        if process_file(os.path.join(root, file)):
                            success_count += 1
                        else:
                            fail_count += 1
        else:
            if process_file(filepath):
                success_count += 1
            else:
                fail_count += 1
                
    print("\n" + "=" * 60)
    print(f"处理完毕！成功: {success_count} 个文件，失败: {fail_count} 个文件。")
    print("=" * 60)
    print("\n按回车键退出...")
    input()

if __name__ == "__main__":
    main()
