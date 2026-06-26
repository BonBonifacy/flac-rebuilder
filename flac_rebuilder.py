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
import numpy as np
import soundfile as sf
from mutagen.flac import FLAC

# 解决 Windows 命令行中文乱码
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def write_size_warning_log(filename, pcm_md5_before, size_before, size_after):
    """当文件体积发生显著变化或变动超过 2MB 时，写出警告日志"""
    import datetime
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

def get_pcm_md5(filepath, subtype=None):
    """解码 FLAC 并计算与 foobar2000 一致的 PCM 数据 MD5"""
    if subtype is None:
        try:
            subtype = sf.info(filepath).subtype
        except Exception:
            subtype = 'PCM_16'
            
    dtype = 'int32' if subtype in ['PCM_24', 'PCM_32'] else 'int16'
    data, _ = sf.read(filepath, dtype=dtype)
    
    if subtype == 'PCM_24':
        # 24-bit 需右移并剔除每个 int32 的最高字节，还原为紧凑的 3 字节小端字节流
        flat_data = (data >> 8).flatten()
        arr_u8 = np.frombuffer(flat_data.tobytes(), dtype=np.uint8).reshape(-1, 4)
        raw_bytes = arr_u8[:, :3].tobytes()
    else:
        raw_bytes = data.tobytes()
        
    return hashlib.md5(raw_bytes).hexdigest().upper()

def process_file(filepath, mode="rebuild"):
    filename = os.path.basename(filepath)
    print("=" * 60)
    
    ext = os.path.splitext(filepath)[1].lower()
    if ext != '.flac':
        print(f"正在处理: {filename}")
        print("  [跳过] 本程序仅支持处理 .flac 格式文件。")
        return False
        
    if mode == "hash_only":
        print(f"正在计算 PCM MD5: {filename}")
        try:
            info = sf.info(filepath)
            original_subtype = info.subtype
            original_samplerate = info.samplerate
            pcm_md5 = get_pcm_md5(filepath, original_subtype)
            print(f"  - 真实 PCM MD5: {pcm_md5}")
            print(f"  - 采样率/位深: {original_samplerate}Hz / {original_subtype}")
            return True
        except Exception as e:
            print(f"  - [错误] 计算失败: {e}")
            return False
            
    print(f"正在处理: {filename}")
        
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
        info = sf.info(filepath)
        original_subtype = info.subtype
        original_samplerate = info.samplerate
        
        pcm_md5_before = get_pcm_md5(filepath, original_subtype)
        print(f"  - 处理前 PCM MD5: {pcm_md5_before}")
        
        # 4. 用 soundfile 重新编码音频流，剔除尾部垃圾
        read_dtype = 'int32' if original_subtype in ['PCM_24', 'PCM_32'] else 'int16'
        data, samplerate = sf.read(filepath, dtype=read_dtype)
        sf.write(temp_path, data, samplerate, format='FLAC', subtype=original_subtype)
        
        # 5. 还原元数据和封面
        new_audio = FLAC(temp_path)
        new_audio.tags.clear()
        for k, v in original_tags.items():
            new_audio.tags[k] = v
        for pic in original_pictures:
            new_audio.add_picture(pic)
        new_audio.save()
        
        # 5.5 检测文件大小变动是否异常 (比例偏离 25% 以上或绝对大小变化超过 2MB)
        size_before = os.path.getsize(filepath)
        size_after = os.path.getsize(temp_path)
        ratio = size_after / size_before if size_before > 0 else 1.0
        diff_bytes = abs(size_before - size_after)
        if ratio < 0.75 or ratio > 1.25 or diff_bytes > 2 * 1024 * 1024:
            write_size_warning_log(filename, pcm_md5_before, size_before, size_after)
            print(f"  [⚠️ 警告] 检测到文件体积发生显著变化 (原: {size_before/1024/1024:.2f}MB, 新: {size_after/1024/1024:.2f}MB)，已写入警告日志。")
        # 6. 计算并校验处理后 PCM MD5
        pcm_md5_after = get_pcm_md5(temp_path, original_subtype)
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

    # 检测是否包含 --only-hash 参数
    mode = "rebuild"
    cleaned_file_list = []
    for item in file_list:
        val = item.strip('"').strip("'")
        if val in ["--only-hash", "--hash-only"]:
            mode = "hash_only"
        else:
            cleaned_file_list.append(item)
            
    file_list = cleaned_file_list

    if mode == "rebuild":
        print("请选择工作模式：")
        print(" [1] 重写清理音频流并优化定位表 (写入文件，默认)")
        print(" [2] 仅计算音频真实 PCM MD5 校验码 (只读测试，不修改文件)")
        choice = input("请输入选项数字 [1/2] (默认 1): ").strip()
        if choice == "2":
            mode = "hash_only"

    if mode == "hash_only":
        print("\n--- 当前运行于 [仅计算真实 PCM MD5 (只读模式)] ---")
    else:
        print("\n--- 当前运行于 [重构音频流与清理标签 (写入模式)] ---")

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
                        if process_file(os.path.join(root, file), mode):
                            success_count += 1
                        else:
                            fail_count += 1
        else:
            if process_file(filepath, mode):
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
