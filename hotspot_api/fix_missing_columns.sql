-- 给 maintenance_logs 表添加缺失的列
ALTER TABLE maintenance_logs
ADD COLUMN fault_date DATE NOT NULL DEFAULT '2026-01-01',
ADD COLUMN fault_time TIME NOT NULL DEFAULT '00:00:00',
ADD COLUMN branch smallint UNSIGNED NULL;

-- 给 operation_logs 表添加缺失的列（如果有）
ALTER TABLE operation_logs
ADD COLUMN branch smallint UNSIGNED NULL;