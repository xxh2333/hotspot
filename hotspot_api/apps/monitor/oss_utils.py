"""
OSS 工具模块
提供阿里云 OSS 上传功能，供 MQTT 数据处理器使用。
"""
import logging
from io import BytesIO

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('monitor.oss')


def upload_bytes_to_oss(file_bytes: bytes, object_key: str) -> str:
    """
    上传字节数据到阿里云 OSS。

    Args:
        file_bytes: 文件字节数据
        object_key: OSS 对象键，如 'alarm_images/raspberrypi-01/2026-07-06/xxx.jpg'

    Returns:
        str: 上传成功的 OSS object key；失败时返回空字符串
    """
    oss_config = getattr(settings, 'OSS_CONFIG', None)
    if not oss_config or not oss_config.get('ACCESS_KEY_ID'):
        logger.warning('OSS_CONFIG 未配置，跳过 OSS 上传')
        return ''

    try:
        import oss2
        auth = oss2.Auth(oss_config['ACCESS_KEY_ID'], oss_config['ACCESS_KEY_SECRET'])
        bucket = oss2.Bucket(auth, oss_config['ENDPOINT'], oss_config['BUCKET_NAME'])
        result = bucket.put_object(object_key, BytesIO(file_bytes))
        if result.status == 200:
            logger.info(f'OSS 上传成功: {object_key}')
            return object_key
        else:
            logger.error(f'OSS 上传失败，状态码: {result.status}')
            return ''
    except ImportError:
        logger.error('oss2 SDK 未安装，无法上传到 OSS')
        return ''
    except Exception as e:
        logger.error(f'OSS 上传异常: {e}')
        return ''


def generate_oss_key(device_id: str, ts, suffix: str = '.jpg') -> str:
    """
    生成 OSS 对象键。

    格式: alarm_images/{device_id}/{YYYY-MM-DD}/{timestamp_str}_{device_id}{suffix}

    Args:
        device_id: 设备 ID
        ts: datetime 对象
        suffix: 文件名后缀，默认为 '.jpg'

    Returns:
        str: OSS 对象键
    """
    local_ts = timezone.localtime(ts)
    date_str = local_ts.strftime('%Y-%m-%d')
    time_str = local_ts.strftime('%Y%m%d_%H%M%S')
    return f'alarm_images/{device_id}/{date_str}/{time_str}_{device_id}{suffix}'


def save_image_locally(file_bytes: bytes, relative_path: str) -> str:
    """
    保存图片到本地 MEDIA_ROOT。

    Args:
        file_bytes: 文件字节数据
        relative_path: 相对于 MEDIA_ROOT 的路径

    Returns:
        str: 保存成功的相对 URL 路径（如 '/media/alarm_images/...'）；失败时返回空字符串
    """
    import os

    media_root = getattr(settings, 'MEDIA_ROOT', None)
    if not media_root:
        logger.warning('MEDIA_ROOT 未配置，跳过本地存储')
        return ''

    try:
        save_path = os.path.join(media_root, relative_path)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, 'wb') as f:
            f.write(file_bytes)
        return f'/media/{relative_path}'
    except Exception as e:
        logger.error(f'本地存储失败: {e}')
        return ''
