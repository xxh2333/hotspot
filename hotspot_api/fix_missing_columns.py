"""
通过 Django ORM 直接执行 SQL，给 maintenance_logs 表添加缺失的列
"""
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hotspot_api.settings')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import django
django.setup()

from django.db import connection

sql_statements = [
    "ALTER TABLE maintenance_logs "
    "ADD COLUMN fault_date DATE NOT NULL DEFAULT '2026-01-01', "
    "ADD COLUMN fault_time TIME NOT NULL DEFAULT '00:00:00', "
    "ADD COLUMN branch smallint UNSIGNED NULL",

    "ALTER TABLE operation_logs "
    "ADD COLUMN branch smallint UNSIGNED NULL",
]

with connection.cursor() as cursor:
    for sql in sql_statements:
        try:
            cursor.execute(sql)
            print(f'OK: 执行成功 -> {sql[:60]}...')
        except Exception as e:
            err_str = str(e)
            if 'Duplicate column' in err_str or 'already exists' in err_str:
                print(f'SKIP: 列已存在 -> {sql[:60]}...')
            else:
                print(f'ERROR: {e}')

print('完成！')