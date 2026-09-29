# utils/minio_utils.py

import json
import logging

from minio import Minio

from processor.import_processor.import_config import get_config
from processor.import_processor.base import setup_logging

setup_logging()

_config = get_config()

try:
    # 1. 创建客户端连接对象
    minio_client = Minio(
        endpoint=_config.minio_endpoint,
        access_key=_config.minio_access_key,
        secret_key=_config.minio_secret_key,
        # 是否强制启用 HTTPS 加密链接，False：http；True：https
        secure=_config.minio_secure,
    )

    # 2. 判断 bucket 是否存在，不存在则创建
    found = minio_client.bucket_exists(_config.minio_bucket)
    if not found:
        minio_client.make_bucket(_config.minio_bucket)

    # 3. 定义当前 bucket 的访问权限（公开读，允许匿名 GET）
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": "*"},
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{_config.minio_bucket}/*",
            },
        ],
    }
    # 4. 设置当前 bucket 的访问权限
    minio_client.set_bucket_policy(_config.minio_bucket, json.dumps(policy))

except Exception as e:
    logging.error(f"MinIO连接失败，错误原因：{e}")

def get_minio_client():
    """获取 MinIO 客户端单例"""
    return minio_client

if __name__ == '__main__':
    get_minio_client()