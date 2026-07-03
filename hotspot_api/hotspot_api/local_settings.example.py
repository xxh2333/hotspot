"""
本地开发配置模板
=================
使用方式：
    1. 复制此文件 → local_settings.py
    2. 填入你自己的数据库密码等信息
    3. local_settings.py 已在 .gitignore 中，不会被提交到 git

每次拉取代码后无需修改 settings.py，local_settings.py 会自动覆盖默认配置。
"""

# ── 数据库 ───────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'hotspot_db',
        'USER': 'root',
        'PASSWORD': '123456',          # ← 改成你自己的密码
        'HOST': 'localhost',
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    }
}

# ── 可选：覆盖其他配置 ───────────────────────────────────
# SECRET_KEY = '你的密钥'
# DEBUG = True
# MQTT_CONFIG = { ... }
