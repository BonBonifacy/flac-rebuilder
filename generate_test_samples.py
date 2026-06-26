# /// script
# dependencies = [
#     "soundfile",
#     "mutagen",
#     "numpy",
# ]
# ///

import os
import numpy as np
import soundfile as sf
from mutagen.flac import FLAC, SeekTable

def main():
    output_dir = "test_samples"
    os.makedirs(output_dir, exist_ok=True)
    
    # 生成 1 秒正弦波音频数据 (44.1kHz, 16bit)
    sr = 44100
    t = np.linspace(0, 1.0, sr, endpoint=False)
    data = 0.5 * np.sin(2 * np.pi * 440.0 * t)  # 440Hz A音
    
    # 解决 Windows 命令行中文乱码
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    # 1. 生成完美无损、布局正确的 FLAC 文件
    good_path = os.path.join(output_dir, "good_file.flac")
    sf.write(good_path, data, sr, format='FLAC', subtype='PCM_16')
    audio = FLAC(good_path)
    audio.metadata_blocks.append(SeekTable(b""))
    audio.save()
    print(f"[OK] 已生成完美布局样本: {good_path}")
    
    # 2. 生成缺失定位表 (Seek Table) 的 FLAC 文件
    missing_seek_path = os.path.join(output_dir, "missing_seektable.flac")
    sf.write(missing_seek_path, data, sr, format='FLAC', subtype='PCM_16')
    # sf.write 默认不生成 SeekTable，因此它确实缺失定位表，不用额外剔除
    print(f"[OK] 已生成缺失定位表样本: {missing_seek_path}")
    
    # 3. 生成尾部有 ID3v1 垃圾的 FLAC 文件
    garbage_path = os.path.join(output_dir, "trailing_garbage.flac")
    sf.write(garbage_path, data, sr, format='FLAC', subtype='PCM_16')
    # 写入一些元数据、Padding 并加入 SeekTable 保证其本身含有定位表
    audio = FLAC(garbage_path)
    audio.tags["TITLE"] = "Test Title"
    audio.metadata_blocks.append(SeekTable(b""))
    audio.save(padding=lambda info: 8192)
    # 追加 128 字节的 ID3v1 垃圾数据到末尾
    with open(garbage_path, "ab") as f:
        f.write(b"TAG" + b"A" * 125)
    # 4. 生成专门用于触发 MD5 校验错误的测试 FLAC 文件
    trigger_error_path = os.path.join(output_dir, "trigger_md5_error.flac")
    sf.write(trigger_error_path, data, sr, format='FLAC', subtype='PCM_16')
    audio = FLAC(trigger_error_path)
    audio.metadata_blocks.append(SeekTable(b""))
    audio.save()
    print(f"[OK] 已生成触发 MD5 校验错误样本: {trigger_error_path}")
    
    print("\n所有测试样本已生成完毕！可将 'test_samples' 文件夹拖入 GUI 程序中进行智能重构或仅计算测试。")

if __name__ == "__main__":
    main()
