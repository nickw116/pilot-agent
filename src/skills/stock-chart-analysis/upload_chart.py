#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上传图表到腾讯云 COS。

Usage:
    python upload_chart.py /tmp/stock_charts/chanlun_sh000001.png
    python upload_chart.py /tmp/stock_charts/dow_sh000001.png
"""

import argparse
import os
import sys


def parse_args():
    parser = argparse.ArgumentParser(description="Upload chart PNG to COS")
    parser.add_argument("file_path", type=str, help="本地 PNG 文件路径")
    parser.add_argument("--content-type", type=str, default="image/png", help="MIME 类型")
    return parser.parse_args()


def load_env(env_paths):
    """按顺序从候选 .env 文件加载环境变量（先找到的优先）。"""
    if isinstance(env_paths, str):
        env_paths = [env_paths]
    loaded = False
    for env_path in env_paths:
        if not os.path.isfile(env_path):
            continue
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and val:
                    os.environ.setdefault(key, val)
        loaded = True
        print(f"[upload] Loaded env: {env_path}")
        return
    if not loaded:
        print(f"[upload] 警告: 未找到任何 .env 文件，候选: {env_paths}")


# 候选 .env 路径（按优先级）
ENV_CANDIDATES = [
    "/home/ubuntu/pilot-agent/.env",
    os.path.expanduser("~/.openclaw/workspace/h5-chat/.env"),
    "/root/h5-chat/.env",
]

# 候选 bridge 目录（含 cos_util.py）
BRIDGE_CANDIDATES = [
    "/home/ubuntu/.openclaw/workspace/h5-chat/bridge",
    "/root/h5-chat/bridge",
]


def main():
    args = parse_args()

    if not os.path.isfile(args.file_path):
        print(f"[upload] 错误: 文件不存在: {args.file_path}")
        sys.exit(1)

    # 1. 加载 COS 凭证
    load_env(ENV_CANDIDATES)

    # 2. 将 bridge 目录加入路径以导入 cos_util
    bridge_dir = next((d for d in BRIDGE_CANDIDATES if os.path.isfile(os.path.join(d, "cos_util.py"))), None)
    if bridge_dir is None:
        print(f"[upload] 错误: 未找到 cos_util.py，候选: {BRIDGE_CANDIDATES}")
        sys.exit(1)
    if bridge_dir not in sys.path:
        sys.path.insert(0, bridge_dir)
    print(f"[upload] bridge_dir: {bridge_dir}")

    try:
        from cos_util import upload_file
    except ImportError as e:
        print(f"[upload] 错误: 无法导入 cos_util: {e}")
        print(f"[upload] 请确保 {bridge_dir}/cos_util.py 存在")
        sys.exit(1)

    # 3. 读取文件并上传
    filename = os.path.basename(args.file_path)
    with open(args.file_path, "rb") as f:
        file_data = f.read()

    try:
        url = upload_file(file_data, filename, content_type=args.content_type)
        print(f"[upload] 上传成功: {url}")
        print(f"COS_URL:{url}")
        return url
    except Exception as e:
        print(f"[upload] 上传失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
