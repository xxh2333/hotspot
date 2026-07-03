光伏热斑智能检测系统 —— 接口总文档（五模块汇总）
文档版本信息
项目	内容
文档版本	V2.0（汇总版）
编制日期	2026年7月2日
涉及模块	用户认证、实时监控面板、趋势图表、设备历史记录、系统日志
技术栈	Django REST Framework + MySQL 8.0 + MQTT + SSE + JWT
原始文档	四个模块独立接口文档的汇总整合 + 新增用户认证模块
目录
模块零：用户认证
模块一：实时监控面板
模块二：趋势图表
模块三：设备历史记录
模块四：系统日志管理
附录：跨模块差异与统一建议
模块零：用户认证
新增模块 | 编制日期：2026年7月2日

设计说明
本系统采用 JWT（JSON Web Token） 认证方案：

前端通过登录接口换取 Token，后续所有请求在 Header 中携带 Authorization: Bearer <token>
不提供注册接口，账号由管理员直接在数据库中管理（通过 Django 内置 auth_user 表或手动 SQL）
角色分为两类：管理员（is_staff=True，拥有全部权限）和运维人员（is_staff=False，权限受限）
1. 接口总览
序号	接口名称	方法	路径	认证	说明
1	用户登录	POST	/api/auth/login	无需认证	提交用户名密码，换取 JWT Token
2	获取当前用户信息	GET	/api/auth/me	需要认证	返回当前登录用户的身份信息
3	修改密码	POST	/api/auth/change-password	需要认证	已登录用户修改自己的密码
2. 通用规范
2.1 基础信息
项目	说明
Base URL	/api/auth
认证方式	JWT Token（Header: Authorization: Bearer <token>）
Token 有效期	Access Token 2 小时，Refresh Token 7 天
数据格式	JSON
字符编码	UTF-8
2.2 统一响应格式
{
    "code": 0,
    "msg": "success",
    "data": {},
    "success": true,
    "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
2.3 角色与权限对照表
角色	数据库标识	权限范围
管理员	is_staff = True	查看全部数据、导出全部日志、修改阈值、管理账号
运维人员	is_staff = False	查看监控数据、操作断路器、录入维修记录、仅看自己的操作日志
各模块具体权限拦截见各模块接口说明。

3. 接口详细说明
3.1 用户登录
接口路径：POST /api/auth/login

功能描述：验证用户名和密码，成功则返回 JWT Token（Access Token + Refresh Token）。后续所有需要认证的接口均需携带 Access Token。

请求体（application/json）：

参数名	类型	必填	说明
username	string	✅ 是	用户名
password	string	✅ 是	密码（明文传输，建议生产环境启用 HTTPS）
请求示例：

{
    "username": "admin",
    "password": "admin123"
}
响应示例：

{
    "code": 0,
    "msg": "登录成功",
    "data": {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "expires_in": 7200,
        "user": {
            "id": 1,
            "username": "admin",
            "role": "admin",
            "role_display": "管理员"
        }
    },
    "success": true,
    "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
返回字段说明：

字段	类型	说明
access_token	string	JWT 访问令牌，后续请求放入 Header
refresh_token	string	JWT 刷新令牌，用于换取新的 Access Token
expires_in	int	Access Token 有效时长（秒），默认 7200（2小时）
user.id	int	用户ID
user.username	string	用户名
user.role	string	角色标识：admin（管理员）/ operator（运维人员）
user.role_display	string	角色中文名称
错误码：

错误码	msg	说明
0	登录成功	—
40101	用户名或密码错误	凭据不匹配
40102	账号已被禁用	is_active = False
40103	用户名和密码不能为空	缺少必填参数
3.2 获取当前用户信息
接口路径：GET /api/auth/me

功能描述：根据请求 Header 中的 JWT Token 返回当前登录用户的详细信息。前端可用于判断登录态是否有效、获取当前角色以控制 UI 展示。

请求头：

Authorization: Bearer <access_token>
请求参数：无

响应示例：

{
    "code": 0,
    "msg": "获取成功",
    "data": {
        "id": 1,
        "username": "admin",
        "role": "admin",
        "role_display": "管理员",
        "is_active": true,
        "date_joined": "2026-06-01T10:00:00+08:00",
        "last_login": "2026-07-02T14:30:00+08:00"
    },
    "success": true,
    "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
前端用途：

// 页面初始化时检查登录态
const res = await axios.get('/api/auth/me');
if (res.data.code === 0) {
    const user = res.data.data;
    // user.role === 'admin' → 显示管理功能入口
    // user.role === 'operator' → 隐藏管理功能入口
}
错误码：

错误码	msg	说明
0	获取成功	—
40104	Token 无效或已过期	需要重新登录
40105	Token 格式错误	Header 格式不正确
3.3 修改密码
接口路径：POST /api/auth/change-password

功能描述：已登录用户修改自己的登录密码。需要提供旧密码进行验证。

请求头：

Authorization: Bearer <access_token>
请求体（application/json）：

参数名	类型	必填	说明
old_password	string	✅ 是	旧密码
new_password	string	✅ 是	新密码（建议至少8位，含字母和数字）
请求示例：

{
    "old_password": "admin123",
    "new_password": "newPass456"
}
响应示例：

{
    "code": 0,
    "msg": "密码修改成功，请使用新密码重新登录",
    "data": null,
    "success": true,
    "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
错误码：

错误码	msg	说明
0	密码修改成功	—
40106	旧密码不正确	验证失败
40107	新密码格式不符合要求	长度不足或缺少必要字符
40104	Token 无效或已过期	需要重新登录
4. 前端对接指南
4.1 登录流程
// 1. 用户输入用户名密码，点击登录
async function login(username, password) {
    const res = await axios.post('/api/auth/login', {
        username,
        password
    });

    if (res.data.code === 0) {
        const { access_token, refresh_token, user } = res.data.data;

        // 2. 存储 Token（localStorage 或 sessionStorage）
        localStorage.setItem('access_token', access_token);
        localStorage.setItem('refresh_token', refresh_token);

        // 3. 设置 Axios 全局请求头
        axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;

        // 4. 根据角色跳转页面
        if (user.role === 'admin') {
            router.push('/dashboard');
        } else {
            router.push('/monitor');
        }
    }
}
4.2 Token 过期处理
// Axios 响应拦截器
axios.interceptors.response.use(
    response => response,
    async error => {
        if (error.response?.data?.code === 40104) {
            // Token 过期，尝试刷新
            const refreshToken = localStorage.getItem('refresh_token');
            // 刷新逻辑（如有 refresh 接口）
            // 刷新失败则跳转登录页
            router.push('/login');
        }
        return Promise.reject(error);
    }
);
4.3 退出登录
前端清除本地存储的 Token 即可，无需调用后端接口：

function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    delete axios.defaults.headers.common['Authorization'];
    router.push('/login');
}
5. 账号管理说明
5.1 不提供注册接口
本系统不提供开放注册功能。所有账号由管理员通过数据库直接管理，原因如下：

系统为内部工业监控系统，用户数量有限且固定
避免未授权人员自行注册账号
简化系统复杂度，减少安全风险面
5.2 管理员如何创建账号
方式一：Django 管理后台（推荐）

访问 Django Admin（/admin），在 认证与授权 → 用户 中直接添加用户：

管理员：勾选 is_staff（员工状态）
运维人员：不勾选 is_staff
方式二：直接操作数据库

-- 创建管理员
INSERT INTO auth_user (username, password, is_staff, is_active, is_superuser, email, date_joined)
VALUES ('zhangsan', '<Django加密后的密码哈希>', 1, 1, 0, 'zhangsan@example.com', NOW());

-- 创建运维人员
INSERT INTO auth_user (username, password, is_staff, is_active, is_superuser, email, date_joined)
VALUES ('lisi', '<Django加密后的密码哈希>', 0, 1, 0, 'lisi@example.com', NOW());
⚠️ 注意：password 字段不能直接存明文，需使用 Django 的 make_password() 方法或 manage.py createsuperuser 命令生成密码哈希。

5.3 账号管理操作
操作	方式	说明
创建账号	Django Admin / SQL INSERT	管理员操作
禁用账号	将 is_active 设为 0	禁用后该账号无法登录
删除账号	Django Admin / SQL DELETE	建议优先禁用而非删除
重置密码	Django Admin 中修改密码	或执行 manage.py changepassword <username>
修改角色	修改 is_staff 字段	1=管理员，0=运维人员
6. 错误码汇总
错误码	说明	触发场景
0	成功	—
40101	用户名或密码错误	登录凭据不匹配
40102	账号已被禁用	is_active = False 的账号尝试登录
40103	用户名和密码不能为空	登录时缺少必填字段
40104	Token 无效或已过期	Access Token 过期或被篡改
40105	Token 格式错误	Header 中 Authorization 格式不正确
40106	旧密码不正确	修改密码时旧密码验证失败
40107	新密码格式不符合要求	新密码长度不足或缺少必要字符
模块一：实时监控面板
原始文档：实时监控模块 lzw.md | 作者：lzw

文档版本信息
项目	内容
文档版本	V2.0
编制日期	2026年7月2日
涉及模块	实时监控面板
技术栈	Django REST Framework + MySQL 8.0 + MQTT + SSE
对接前端	Vue 3 实时监控面板页面
数据流架构	树莓派 → MQTT → 后端（入库+SSE推送） → 前端
1. 接口概览
根据系统数据流架构，实时监控面板模块涉及 3 种通信方式：

通信方式	方向	用途	数据内容
HTTP	前端 → 后端	历史数据查询、控制指令下发	历史温度、告警记录、分合闸/复位指令
SSE	后端 → 前端	实时数据推送	红外图像帧、实时温度、告警事件
MQTT	树莓派 → 后端	上行数据采集	红外图像、温度数据、设备状态
1.1 HTTP 接口总览
序号	方法	接口路径	功能	调用时机
1	GET	/api/dashboard/initial	获取仪表盘初始数据	页面加载时
2	GET	/api/temperature/history	获取历史温度数据（趋势图用）	切换趋势图时间范围时
3	GET	/api/alarms/history	获取历史告警列表	查看告警历史时
4	POST	/api/control/reset	发送复位指令	用户点击复位按钮时
5	POST	/api/control/trip	发送分闸指令	用户点击分闸按钮时
6	POST	/api/control/threshold	修改告警阈值	用户修改阈值配置时
1.2 SSE 事件流总览
序号	事件名称	功能	推送频率
1	status	推送实时温度、断路器状态	每 5 秒一次
2	alarm	推送实时告警事件	告警触发时立即推送
3	image	推送红外热像图帧	每秒 1 帧
2. 通用规范
2.1 基础信息
项目	说明
接口基础路径	http://{后端PC IP}:8000/api
SSE 连接地址	http://{后端PC IP}:8000/api/dashboard/stream
数据格式	JSON
字符编码	UTF-8
时区	Asia/Shanghai（UTC+8）
2.2 统一响应格式
{
    "code": 0,
    "message": "success",
    "data": { ... }
}
2.3 告警类型枚举
值	显示名称	颜色
hot_spot	热斑告警	🟠 橙色
over_temp	温度过载告警	🔴 红色
offline	设备离线告警	⚫ 灰色
3. HTTP 接口详细说明
3.1 获取仪表盘初始数据
接口路径：GET /api/dashboard/initial

功能描述：页面加载时获取初始数据，包含各支路最新温度、断路器状态、设备状态、今日告警统计等。后续数据通过 SSE 实时推送更新。

请求参数：无

响应示例：

{
    "code": 0,
    "message": "success",
    "data": {
        "timestamp": "2026-07-02T14:35:12+08:00",
        "branches": [
            {
                "id": 1,
                "temperature": 45.2,
                "area_ratio": 0.0,
                "breaker_status": "closed",
                "alarm_status": "normal",
                "updated_at": "2026-07-02T14:35:10+08:00"
            },
            {
                "id": 2,
                "temperature": 92.5,
                "area_ratio": 7.3,
                "breaker_status": "open",
                "alarm_status": "alarm",
                "updated_at": "2026-07-02T14:35:10+08:00"
            }
        ],
        "global": {
            "max_temp": 92.5,
            "min_temp": 28.3,
            "max_temp_branch": 2,
            "min_temp_branch": 3
        },
        "alarm_statistics": {
            "date": "2026-07-02",
            "total": 3,
            "breakdown": {
                "hot_spot": 2,
                "over_temp": 1,
                "offline": 0
            },
            "unresolved": 1
        },
        "devices": {
            "total": 4,
            "online": 4,
            "offline_list": []
        },
        "thermal_camera": {
            "status": "online",
            "fps": 1.0
        },
        "mqtt": {
            "status": "connected"
        },
        "thresholds": {
            "temperature": 80.0,
            "area_ratio": 5.0
        }
    }
}
3.2 获取历史温度数据
接口路径：GET /api/temperature/history

功能描述：获取指定时间范围内的温度历史数据，用于绘制温度趋势曲线图。

请求参数：

参数	类型	必填	说明
branch	Integer	是	支路编号（1~4）
start	String	是	开始时间，格式 YYYY-MM-DD HH:MM:SS
end	String	是	结束时间，格式 YYYY-MM-DD HH:MM:SS
interval	String	否	聚合粒度：hour / day，默认 hour
响应示例：

{
    "code": 0,
    "message": "success",
    "data": {
        "branch": 2,
        "start": "2026-07-01 00:00:00",
        "end": "2026-07-01 23:59:59",
        "interval": "hour",
        "series": [
            {
                "time": "00:00",
                "max_temp": 45.2,
                "avg_temp": 42.1
            },
            {
                "time": "01:00",
                "max_temp": 44.8,
                "avg_temp": 41.5
            }
        ]
    }
}
3.3 获取历史告警列表
接口路径：GET /api/alarms/history

功能描述：获取历史告警记录列表，支持分页和多条件筛选。

请求参数：

参数	类型	必填	说明
page	Integer	否	页码，默认 1
limit	Integer	否	每页条数，默认 20，最大 100
branch	Integer	否	支路编号筛选
alarm_type	String	否	告警类型：hot_spot / over_temp / offline
status	String	否	处置状态：pending / resolved / recovering
start	String	否	开始时间
end	String	否	结束时间
响应示例：

{
    "code": 0,
    "message": "success",
    "data": {
        "total": 156,
        "page": 1,
        "limit": 20,
        "list": [
            {
                "id": 1001,
                "timestamp": "2026-07-02T14:35:12+08:00",
                "branch": 2,
                "alarm_type": "hot_spot",
                "temperature": 92.5,
                "area_ratio": 7.3,
                "status": "pending",
                "image_path": "/storage/images/2026-07-02_143512_branch2.jpg"
            }
        ]
    }
}
3.4 发送复位指令
接口路径：POST /api/control/reset

功能描述：发送断路器复位指令，闭合指定支路的断路器。

请求体：

{
    "branch": 2,
    "operator": "admin"
}
响应示例：

{
    "code": 0,
    "message": "复位指令已发送，断路器正在闭合",
    "data": {
        "branch": 2,
        "command": "reset",
        "status": "sent"
    }
}
3.5 发送分闸指令
接口路径：POST /api/control/trip

功能描述：发送断路器分闸指令，断开指定支路的断路器。

请求体：

{
    "branch": 2,
    "operator": "admin",
    "reason": "人工远程分闸"
}
响应示例：

{
    "code": 0,
    "message": "分闸指令已发送，断路器正在断开",
    "data": {
        "branch": 2,
        "command": "trip",
        "status": "sent"
    }
}
3.6 修改告警阈值
接口路径：POST /api/control/threshold

功能描述：修改告警触发的温度阈值和面积阈值。

请求体：

{
    "temperature": 85.0,
    "area_ratio": 6.0
}
响应示例：

{
    "code": 0,
    "message": "阈值修改成功",
    "data": {
        "temperature": 85.0,
        "area_ratio": 6.0,
        "effective_at": "2026-07-02T14:40:00+08:00"
    }
}
4. SSE 事件流详细说明
4.1 连接方式
连接地址：GET /api/dashboard/stream

重连机制：SSE 协议自带断线重连，前端无需额外处理

4.2 事件1：实时状态推送（status）
事件名称：status | 推送频率：每 5 秒一次

数据格式：

{
    "timestamp": "2026-07-02T14:35:17+08:00",
    "branches": [
        {
            "id": 1,
            "temperature": 45.2,
            "area_ratio": 0.0,
            "breaker_status": "closed",
            "alarm_status": "normal"
        }
    ],
    "global": {
        "max_temp": 92.5,
        "min_temp": 28.3,
        "max_temp_branch": 2,
        "min_temp_branch": 3
    },
    "devices": {
        "thermal_camera": "online",
        "mqtt": "connected"
    }
}
4.3 事件2：实时告警推送（alarm）
事件名称：alarm | 推送频率：告警触发时立即推送

{
    "timestamp": "2026-07-02T14:35:12+08:00",
    "alarm_id": 1001,
    "branch": 2,
    "alarm_type": "hot_spot",
    "temperature": 92.5,
    "area_ratio": 7.3,
    "auto_trip": true,
    "image_path": "/storage/images/2026-07-02_143512_branch2.jpg",
    "description": "2号光伏板热斑面积达7.3%，最高温度92.5℃"
}
4.4 事件3：红外图像帧推送（image）
事件名称：image | 推送频率：每秒 1 帧

{
    "timestamp": "2026-07-02T14:35:18+08:00",
    "image": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
    "annotated": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
    "width": 256,
    "height": 192
}
5. MQTT 消息详细说明（后端内部）
说明：此部分为树莓派与后端 PC 之间的通信，前端无需关心。

5.1 上行：温度/状态数据
主题：pv/hotspot/up/status | 频率：每 5 秒

{
    "timestamp": "2026-07-02T14:35:17+08:00",
    "device_id": "raspberrypi-01",
    "branches": [
        {"id": 1, "temperature": 45.2, "area_ratio": 0.0},
        {"id": 2, "temperature": 92.5, "area_ratio": 7.3}
    ],
    "breaker_status": {"1": "closed", "2": "open"},
    "thermal_camera": "online"
}
5.2 上行：红外图像帧
主题：pv/hotspot/up/image | 频率：每秒 1 帧

5.3 下行：控制指令
主题：pv/hotspot/down/control

{
    "command": "reset",
    "branch": 2,
    "timestamp": "2026-07-02T14:40:00+08:00",
    "operator": "admin"
}
6. 错误码定义（实时监控模块）
错误码	说明	处理建议
0	成功	—
40001	请求参数错误	检查请求参数格式
40002	缺少必填参数	补充缺失参数
40003	支路编号无效	支路编号应为 1~4
40004	阈值超出合理范围	温度阈值 30120℃，面积阈值 130%
40401	资源不存在	检查请求路径或 ID
50001	服务器内部错误	联系后端开发人员
50002	数据库查询失败	联系后端开发人员
50003	MQTT 服务不可用	检查 MQTT Broker 状态
50004	SSE 推送失败	检查 SSE 连接状态
50301	树莓派离线	检查树莓派网络连接
模块二：趋势图表
原始文档：趋势图表模块接口文档 wlj.md | 作者：wlj

接口总览
接口名称	接口路径	请求方式	状态
实时动态曲线（SSE推送）	GET /api/trend-chart/realtime	GET（SSE）	开发中
历史曲线查询	GET /api/trend-chart/history	GET	开发中
告警阈值查询	GET /api/trend-chart/threshold	GET	开发中
故障告警历史查询	GET /api/trend-chart/alarm-history	GET	开发中
一、实时动态曲线接口（SSE 推送）
接口路径：GET /api/trend-chart/realtime
逻辑概述：通过 SSE 长连接 + Redis 缓存推送实时温度与热斑面积数据；连接建立后默认推送最近 10 分钟秒级数据，之后持续推送新数据
数据来源：temperature_logs 表
请求参数（Query）
字段	类型	必填	说明
branch	int	否	支路编号（1~4），不传则返回全部支路数据
duration	int	否	初始加载时长（秒），默认 600（10分钟），最大 3600
SSE 事件类型
事件名	说明
init	连接建立后首次批量推送历史数据
update	每 5 秒推送最新一条数据
heartbeat	每 30 秒心跳保活
① 初始化批量数据事件（event: init）
event: init
data: [{"timestamp":"2026-07-02 15:30:00.000","branch":1,"max_temp":45.20,"avg_temp":42.10,"area_ratio":3.50},...]
② 实时推送数据事件（event: update）
event: update
data: {"timestamp":"2026-07-02 15:35:05.000","branch":1,"max_temp":46.10,"avg_temp":43.00,"area_ratio":4.20}
③ 心跳事件（event: heartbeat）
每 30 秒发送 event: heartbeat / data: "ping"

SSE 连接控制
客户端操作	行为
连接建立	推送 event: init（最近 N 秒历史数据），之后每 5 秒推送 event: update
前端缩放时间轴	前端发送 action=pause，服务端暂停实时推送
前端恢复区间	前端发送 action=resume，服务端补推暂停期间数据后恢复实时推送
连接断开	服务端清理该连接资源，Redis 频道取消订阅
二、历史曲线查询接口
接口路径：GET /api/trend-chart/history
逻辑概述：根据支路编号和时间范围查询历史温度与热斑面积数据，支持 1h / 24h / 7d / 30d 四种时间粒度
数据来源：temperature_logs 表（1h/24h/7d）+ temperature_daily_stats 聚合表（30d）
请求参数（Query）
字段	类型	必填	说明
branch	int	是	支路编号（1~4）
range	string	是	时间范围：1h / 24h / 7d / 30d
start_time	string	否	自定义起始时间（YYYY-MM-DD HH:MM:SS），与 range 互斥
end_time	string	否	自定义结束时间，与 start_time 配合使用
聚合规则
range	聚合粒度	数据来源	时间标签格式	说明
1h	raw（5秒原始）	temperature_logs 原始行	YYYY-MM-DD HH:MM:SS	最多约 720 条
24h	1min（按分钟）	按分钟 AVG/MAX 聚合	HH:MM	最多约 1440 个数据点
7d	1hour（按小时）	按小时 AVG/MAX 聚合	MM-DD HH:00	最多约 168 个数据点
30d	1day（按天）	temperature_daily_stats 聚合表	YYYY-MM-DD	最多 30 个数据点
响应示例
{
    "code": 0,
    "msg": "成功",
    "data": {
        "range": "24h",
        "aggregation": "1min",
        "branch": 1,
        "data": [
            {
                "time": "00:00",
                "avg_max_temp": 42.5,
                "peak_temp": 45.2,
                "avg_area_ratio": 2.80,
                "max_area_ratio": 5.10
            }
        ]
    },
    "success": true,
    "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
三、告警阈值查询接口
接口路径：GET /api/trend-chart/threshold
逻辑概述：读取设备温度告警阈值与热斑面积告警阈值，供前端在趋势图中绘制红色预警警戒线
数据来源：alarm_logs 表最新一条告警记录的 threshold_temp 与 threshold_area 字段
响应示例
{
    "code": 0,
    "msg": "成功",
    "data": {
        "temp_threshold": 80.00,
        "area_threshold": 20.00,
        "temp_warning_line": 70.00,
        "area_warning_line": 15.00,
        "updated_at": "2026-07-01 10:00:00"
    },
    "success": true,
    "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
四、故障告警历史查询接口
接口路径：GET /api/trend-chart/alarm-history
逻辑概述：根据支路编号和时间范围查询告警历史记录，供前端渲染故障状态时钟图（圆形仪表盘）
数据来源：alarm_logs 表
请求参数（Query）
字段	类型	必填	说明
branch	int	是	支路编号（1~4）
range	string	是	时间范围：1h / 24h / 7d / 30d
start_time	string	否	自定义起始时间，与 range 互斥
end_time	string	否	自定义结束时间
响应示例
{
    "code": 0,
    "msg": "成功",
    "data": {
        "range": "24h",
        "branch": 1,
        "data": [
            {
                "id": 1001,
                "timestamp": "2026-07-02 08:15:30.000",
                "alarm_level": "hot_spot",
                "alarm_level_text": "热斑告警",
                "warning_level": 2,
                "description": "1号光伏板热斑面积达15%，温度125℃",
                "temperature": 125.00,
                "area_ratio": 15.00,
                "threshold_temp": 80.00,
                "threshold_area": 10.00,
                "auto_trip": true,
                "resolution_status": "resolved",
                "resolution_status_text": "已处理",
                "resolved_at": "2026-07-02 09:00:00.000"
            }
        ]
    },
    "success": true,
    "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
前端时钟图着色规则
条件	扇区颜色	说明
仅 alarm_level = over_temp	🟡 黄色	温度超标，面积正常
仅 alarm_level = hot_spot	🔵 蓝色	热斑面积异常，温度正常
同一时段同时存在两种告警	🔴 红色	温度与面积双重异常
该时段无告警	无填充	正常运行
五、统一响应格式（趋势图表模块）
字段	类型	说明
code	int	业务状态码，0 表示成功
msg	string	提示信息
data	object/array/null	返回数据体
success	bool	请求是否成功
trace_id	string	链路追踪 ID（UUID）
六、数据字典
时间范围（range）
值	含义	聚合粒度
1h	最近 1 小时	秒级原始数据（5s 间隔）
24h	最近 24 小时	按分钟聚合
7d	最近 7 天	按小时聚合
30d	最近 30 天	按天聚合
告警分类（alarm_level）
枚举值	中文名称	时钟图颜色
hot_spot	热斑告警	🔵 蓝色
over_temp	温度过载告警	🟡 黄色
offline	设备离线告警	⚫ 灰色
告警严重等级（warning_level）
值	名称	判定逻辑
1	一级告警	温度 ≥ 80℃ 或 面积 ≥ 20%
2	二级告警	温度 6080℃ 或 面积 1020%
3	三级告警	温度 < 60℃ 且 面积 < 10%
处置状态（resolution_status）
枚举值	中文名称
pending	未处理
resolved	已处理
recovering	恢复中
七、业务规则与约束
规则项	说明
数据操作类型	仅查询（SELECT），本模块无新增、修改、删除数据操作
温度日志保留周期	temperature_logs 保留 7 天秒级数据；temperature_daily_stats 保留 30 天日级数据
告警日志保留周期	alarm_logs 保留至少 1 年，未处理告警永久保留
实时推送频率	每 5 秒推送一次
心跳间隔	每 30 秒发送一次心跳
缓存策略	实时数据通过 Redis Pub/Sub 推送；阈值数据建议缓存 TTL 600s
并发控制	同一用户对同一支路只允许维持 1 个 SSE 连接
八、相关数据表
本模块涉及 3 张数据库表，均只做 SELECT 查询：

表名	实时动态曲线	历史曲线查询	告警阈值查询	故障告警历史查询	操作类型
temperature_logs	✅	✅（1h/24h/7d）	—	—	SELECT
temperature_daily_stats 🆕	—	✅（30d）	—	—	SELECT
alarm_logs	—	—	✅	✅	SELECT
temperature_daily_stats（温度日聚合表）🆕
注意：此表为趋势图表模块新增的聚合表，用于支撑 30 天历史查询。

CREATE TABLE temperature_daily_stats (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '自增主键',
    stat_date DATE NOT NULL COMMENT '统计日期',
    branch TINYINT UNSIGNED NOT NULL COMMENT '支路编号（1~4）',
    avg_max_temp DECIMAL(5,2) NOT NULL COMMENT '当日平均最高温度（℃）',
    peak_temp DECIMAL(5,2) NOT NULL COMMENT '当日峰值温度（℃）',
    avg_area_ratio DECIMAL(5,2) NOT NULL COMMENT '当日平均热斑面积占比（%）',
    max_area_ratio DECIMAL(5,2) NOT NULL COMMENT '当日最大热斑面积占比（%）',
    sample_count INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '当日原始采样条数',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间',
    CONSTRAINT pk_temperature_daily_stats PRIMARY KEY (id),
    CONSTRAINT uk_daily_stats_date_branch UNIQUE KEY (stat_date, branch),
    CONSTRAINT chk_daily_stats_branch CHECK (branch BETWEEN 1 AND 4)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='温度日聚合统计表';
九、错误码说明（趋势图表模块）
Code	含义	触发场景
0	成功	正常返回
10001	参数错误	branch 不在 1~4 范围
10002	必填参数缺失	branch 或 range 未传入
20001	未登录	Token 缺失或无效
30001	数据不存在	查询时间范围内无数据
40001	业务异常	SSE 连接数超限等
90001	系统异常	Redis 连接失败、数据库异常等
模块三：设备历史记录
原始文档：设备历史记录模块接口文档 cgj.md | 作者：cgj

一、接口概述
1.1 基础信息
项目	说明
Base URL	/api
认证方式	JWT Token（Header: Authorization: Bearer <token>）
数据格式	请求/响应均为 application/json
时间格式	ISO 8601，如 2026-06-01T00:00:00
1.2 响应格式
{
  "code": 0,
  "message": "string",
  "data": {}
}
二、接口速查表
序号	接口名称	方法	路径	权限
1	历史温度查询	GET	/history/temperature/	管理员/运维
2	温度历史导出	POST	/history/temperature/export/	仅管理员
3	历史告警查询	GET	/history/alarm/	管理员/运维
4	故障原图预签名URL	GET	/history/alarm/{id}/presign/	管理员/运维
5	告警历史导出	POST	/history/alarm/export/	仅管理员
三、接口详情
3.1 历史温度查询
GET /api/history/temperature/
请求参数（Query String）
参数名	类型	必填	说明	示例
start_time	string	✅ 是	开始时间（ISO 8601）	2026-06-01T00:00:00
end_time	string	✅ 是	结束时间（ISO 8601）	2026-06-30T23:59:59
branch	int	❌ 否	支路编号（1~4），不传则查所有	1
min_temp	float	❌ 否	最低温度筛选（℃）	40.00
max_temp	float	❌ 否	最高温度筛选（℃）	80.00
page	int	❌ 否	页码，默认 1	1
size	int	❌ 否	每页条数，默认 100，最大 1000	100
响应示例
{
  "code": 0,
  "data": {
    "total": 1250,
    "page": 1,
    "page_size": 100,
    "list": [
      {
        "id": 1,
        "branch": 1,
        "timestamp": "2026-06-01T10:23:45.123",
        "max_temp": 45.60,
        "min_temp": 32.10,
        "avg_temp": 38.50,
        "area_ratio": 0.00,
        "hotspot_count": 0
      }
    ]
  }
}
字段说明
字段	类型	说明
total	int	满足条件的总记录数
page	int	当前页码
page_size	int	每页条数
list[].id	int	记录ID
list[].branch	int	支路编号（1~4）
list[].timestamp	string	采集时间（毫秒精度）
list[].max_temp	float	该支路最高温度（℃）
list[].min_temp	float	该支路最低温度（℃）
list[].avg_temp	float	该支路平均温度（℃）
list[].area_ratio	float	热斑面积占比（%）
list[].hotspot_count	int	热斑数量
3.2 温度历史导出
POST /api/history/temperature/export/
权限要求：仅管理员可调用（is_staff=True）

请求体：

{
  "start_time": "2026-06-01T00:00:00",
  "end_time": "2026-06-30T23:59:59",
  "branch": 1
}
成功时直接返回 Excel 文件流（.xlsx）。

3.3 历史告警查询
GET /api/history/alarm/
请求参数（Query String）
参数名	类型	必填	说明
start_time	string	✅ 是	开始时间（ISO 8601）
end_time	string	✅ 是	结束时间（ISO 8601）
branch	int	❌ 否	支路编号（1~4）
alarm_level	string	❌ 否	告警分类（hot_spot/over_temp/offline）
resolution_status	string	❌ 否	处置状态（pending/resolved/recovering）
page	int	❌ 否	页码，默认 1
size	int	❌ 否	每页条数，默认 100，最大 1000
响应示例
{
  "code": 0,
  "data": {
    "total": 8,
    "page": 1,
    "page_size": 100,
    "list": [
      {
        "id": 456,
        "branch": 1,
        "timestamp": "2026-06-15T14:12:30.000",
        "alarm_level": "hot_spot",
        "alarm_level_name": "热斑告警",
        "warning_level": 1,
        "description": "1号光伏板热斑面积达15%，温度125℃",
        "image_path": "/storage/images/alarm/456_20260615_141230.jpg",
        "annotated_image_path": "/storage/images/alarm/456_20260615_141230_annotated.jpg",
        "temperature": 125.00,
        "temp_difference": 35.20,
        "area_ratio": 15.20,
        "threshold_temp": 80.00,
        "threshold_area": 10.00,
        "auto_trip": true,
        "action": "trip",
        "resolution_status": "pending",
        "resolved_at": null,
        "resolved_by": null,
        "maintenance": null
      },
      {
        "id": 789,
        "branch": 2,
        "timestamp": "2026-06-16T09:30:00.000",
        "alarm_level": "over_temp",
        "alarm_level_name": "温度过载告警",
        "warning_level": 2,
        "description": "2号光伏板温度达85℃，持续超阈值",
        "temperature": 85.50,
        "temp_difference": 12.30,
        "area_ratio": 5.00,
        "threshold_temp": 80.00,
        "threshold_area": 10.00,
        "auto_trip": false,
        "action": "none",
        "resolution_status": "resolved",
        "resolved_at": "2026-06-16T10:30:00.000",
        "resolved_by": "zhangli",
        "maintenance": {
          "id": 3,
          "user_id": 2,
          "repair_detail": "清洁散热，调整角度后恢复正常",
          "repair_images": [
            "/storage/maintenance/2026-06-16/img1.jpg",
            "/storage/maintenance/2026-06-16/img2.jpg"
          ]
        }
      }
    ]
  }
}
3.4 故障原图预签名URL
GET /api/history/alarm/{id}/presign/
根据告警记录 ID 生成 OSS 预签名 URL（有效期 5 分钟），供前端 <img> 加载原图。

参数名	类型	必填	说明
id	int	✅ 是	告警记录ID（路径参数）
type	string	❌ 否	图片类型：original（原图）或 annotated（标注图）
3.5 告警历史导出
POST /api/history/alarm/export/
权限要求：仅管理员可调用（is_staff=True）

请求体参数与历史告警查询的筛选条件一致，成功时直接返回 Excel 文件流。

四、枚举值汇总
告警分类枚举（alarm_level）
枚举值	显示名称	前端颜色
hot_spot	热斑告警	🟠 橙色
over_temp	温度过载告警	🔴 红色
offline	设备离线告警	⚫ 灰色
严重等级（warning_level）
等级值	名称	说明
1	一级告警	温度 ≥ 80℃ 或 面积 ≥ 20%
2	二级告警	温度 6080℃ 或 面积 1020%
3	三级告警	温度 < 60℃ 且 面积 < 10%
处置状态枚举（resolution_status）
枚举值	显示名称
pending	未处理
resolved	已处理
recovering	恢复中
执行动作枚举（action）
枚举值	显示名称
trip	跳闸
reset	复位
none	无动作
五、错误码汇总
错误码	说明	出现场景
400	请求参数错误	缺少必填参数或参数格式错误
401	身份认证失败	Token 无效、过期或未携带
403	无权限执行此操作	普通运维调用导出接口
404	资源不存在	告警记录 ID 无效
模块四：系统日志管理
原始文档：系统日志模块接口文档设计 zhy.md | 作者：zhy

一、通用说明
1.1 通用响应格式
{
    "code": 0,
    "msg": "成功",
    "data": {},
    "success": true,
    "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
1.2 通用错误码
错误码	说明
0	成功
10001	参数错误
20001	未登录
20005	无访问权限
30001	数据不存在
40001	业务操作失败
90001	系统异常
二、接口列表总览
序号	接口名称	请求方式	路径	权限	对应前端功能
1	获取人员操作日志列表	GET	/api/log/operation	运维（仅自己）/管理员	操作日志表格展示
2	新增人员操作日志（手动录入）	POST	/api/log/operation/create	运维/管理员	"新增操作记录"按钮
3	获取故障处置日志列表	GET	/api/log/fault	运维（仅自己）/管理员	故障处置日志表格展示
4	新增故障处置日志（手动录入）	POST	/api/log/fault/create	运维/管理员	"新增处置记录"按钮
5	获取告警日志列表	GET	/api/log/alarm	运维/管理员	告警日志表格展示
6	上传图片（通用）	POST	/api/log/upload-image	运维/管理员	详情弹窗图片上传
7	导出日志Excel	GET	/api/log/export/excel	仅管理员（全量）/ 运维（仅自身）	"批量导出"按钮
8	获取日志统计概览	GET	/api/log/statistics	运维/管理员	仪表盘统计（可选）
三、接口详细说明
3.1 获取人员操作日志列表
接口路径：GET /api/log/operation

接口描述：分页查询人员操作日志。权限隔离：运维仅能看到自己的操作记录，管理员可查看全部。

请求参数（Query）：

参数名	类型	必填	说明
page	integer	否	页码，默认 1
limit	integer	否	每页条数，默认 20
start_time	string	否	开始时间，格式 YYYY-MM-DD HH:mm:ss
end_time	string	否	结束时间
operator	string	否	操作人员姓名（模糊匹配）
device_code	string	否	故障支路编号（如 1、2）
action_type	string	否	操作类型：remote_control / threshold_update / repair_device
is_success	boolean	否	运行状态：true=正常，false=异常
返回参数：

{
    "code": 0,
    "msg": "获取成功",
    "data": {
        "count": 45,
        "next": "http://api.example.com/api/log/operation?page=2",
        "previous": null,
        "results": [
            {
                "id": 2001,
                "operator_name": "zzy",
                "operation_time": "2026-07-02 09:46:00",
                "device_code": "1",
                "action_type": "remote_control",
                "is_success": false,
                "detail": "手动关闭支路1维修",
                "images": ["/media/operation/2026/07/02/img_001.jpg"]
            }
        ]
    },
    "trace_id": "xxx"
}
前端表格字段映射：

表格列名	返回字段	说明
操作日期	operation_time	取日期部分
操作时间	operation_time	取时间部分
操作人员	operator_name	—
操作支路	device_code	—
操作类型	action_type	需前端映射为中文
运行状态	is_success	true=正常（绿），false=异常（红）
详情	id	点击"查看"弹窗
3.2 新增人员操作日志（手动录入）
接口路径：POST /api/log/operation/create

接口描述：运维人员手动录入操作日志，user_id 自动取当前登录用户。

请求参数（Body）：

参数名	类型	必填	说明
device_code	string	是	操作支路编号（如 1、2、1,2,3 表示多支路）
action_type	string	是	操作类型：remote_control / threshold_update / repair_device
is_success	boolean	是	运行状态：true=正常，false=异常
detail	string	否	操作详情描述（文字备注）
images	array	否	已上传的图片URL数组
3.3 获取故障处置日志列表
接口路径：GET /api/log/fault

接口描述：分页查询故障排查处置日志。权限隔离：运维仅能看到自己的处置记录，管理员可查看全部。

请求参数（Query）：

参数名	类型	必填	说明
page	integer	否	页码，默认 1
limit	integer	否	每页条数，默认 20
start_time	string	否	开始时间
end_time	string	否	结束时间
fault_device	string	否	故障设备类型（如：光伏板、保险丝）
device_code	string	否	故障支路编号
repairer	string	否	维修人员姓名（模糊匹配）
返回参数：

{
    "code": 0,
    "msg": "获取成功",
    "data": {
        "count": 12,
        "results": [
            {
                "id": 3001,
                "fault_date": "2026-07-02",
                "fault_time": "09:46:00",
                "fault_device": "保险丝",
                "device_code": "2",
                "images": ["/media/maintenance/2026/07/02/img_001.jpg"],
                "repairer_name": "zzp",
                "remark": "支路2保险丝熔断，已更换同规格保险丝",
                "created_at": "2026-07-02 10:30:00"
            }
        ]
    },
    "trace_id": "xxx"
}
3.4 新增故障处置日志（手动录入）
接口路径：POST /api/log/fault/create

请求参数（Body）：

参数名	类型	必填	说明
fault_date	string	是	故障日期，格式 YYYY-MM-DD
fault_time	string	是	故障时间，格式 HH:mm:ss
fault_device	string	是	故障设备类型（如：光伏板、保险丝、热像仪、断路器）
device_code	string	是	故障支路编号（如 2、2,4 表示多支路）
remark	string	是	处置内容/备注描述（最大1000字符）
images	array	否	已上传的图片URL数组
3.5 获取告警日志列表
接口路径：GET /api/log/alarm

接口描述：分页查询系统自动记录的光伏热斑告警数据。运维和管理员均可查看全部告警。

请求参数（Query）：

参数名	类型	必填	说明
page	integer	否	页码，默认 1
limit	integer	否	每页条数，默认 20
start_time	string	否	开始时间
end_time	string	否	结束时间
device_code	string	否	支路编号
warning_level	integer	否	告警等级：1/2/3
resolution_status	string	否	处置状态：pending / resolved / recovering
返回参数：

{
    "code": 0,
    "msg": "获取成功",
    "data": {
        "count": 156,
        "results": [
            {
                "id": 1001,
                "alarm_date": "2026-07-02",
                "alarm_time": "19:46:00",
                "device_code": "1,2,3",
                "max_temperature": "78.00",
                "temp_difference": "18.00",
                "warning_level": 1,
                "threshold_temp": "70.00",
                "auto_trip": true,
                "resolution_status": "recovering"
            }
        ]
    },
    "trace_id": "xxx"
}
3.6 上传图片（通用）
接口路径：POST /api/log/upload-image

请求参数（multipart/form-data）：

参数名	类型	必填	说明
image	File	是	图片文件，支持 jpg/png/webp，最大 5MB
type	string	否	图片用途：operation / maintenance，默认 maintenance
3.7 导出日志 Excel
接口路径：GET /api/log/export/excel

导出当前日志模块数据为 Excel 文件。管理员导出全量，运维仅导出自身日志。

参数名	类型	必填	说明
log_type	string	是	日志类型：operation / fault / alarm
start_time	string	否	开始时间
end_time	string	否	结束时间
3.8 获取日志统计概览（可选）
接口路径：GET /api/log/statistics

{
    "code": 0,
    "msg": "获取成功",
    "data": {
        "date": "2026-07-02",
        "operation_total": 45,
        "fault_total": 8,
        "alarm_total": 12,
        "pending_alarm": 7
    },
    "trace_id": "xxx"
}
四、枚举值汇总（系统日志模块）
操作类型（action_type）
枚举值	显示名称
remote_control	远程分合闸控制
threshold_update	修改告警阈值
repair_device	维修设备
告警等级（warning_level）
值	名称	颜色
1	一级告警	🔴 红色
2	二级告警	🟠 橙色
3	三级告警	🟡 黄色
处置状态（resolution_status）
枚举值	显示名称	颜色
pending	未处理	⚪ 灰色
resolved	已处理	🟢 绿色
recovering	恢复中	🟡 黄色
故障设备（fault_device）
光伏板 / 保险丝 / 热像仪 / 断路器（自由文本）

五、接口路径与前端组件映射
前端组件/功能	调用接口	说明
OperationLogTable 表格	GET /api/log/operation	展示操作日志列表
"新增操作记录"按钮	POST /api/log/operation/create	手动录入操作日志
FaultDisposeLogTable 表格	GET /api/log/fault	展示故障处置日志列表
"新增处置记录"按钮	POST /api/log/fault/create	手动录入故障处置日志
AlarmLogTable 表格	GET /api/log/alarm	展示告警日志列表
LogAddDialog 图片上传	POST /api/log/upload-image	上传图片
LogDetailDialog 详情	复用列表接口，通过 id 查单条	查看详情弹窗
LogExportDialog 导出	GET /api/log/export/excel	导出Excel
LogSearchForm 筛选	各列表接口的 Query 参数	条件检索
附录：跨模块差异与统一建议
A. 响应格式差异
模块	code字段	消息字段	success字段	trace_id字段	分页字段
实时监控	code	message	❌ 无	❌ 无	total, page, limit
趋势图表	code	msg	✅ success	✅ trace_id	聚合数据无分页
设备历史记录	code	message	❌ 无	❌ 无	total, page, page_size
系统日志	code	msg	✅ success	✅ trace_id	count, next, previous
建议：统一为 {"code": 0, "msg": "success", "data": {}, "success": true, "trace_id": "..."} 格式。

B. Base URL 差异
模块	Base URL
实时监控	/api
趋势图表	/api
设备历史记录	/api
用户认证	/api
系统日志	/api/log
建议：已统一去掉 /v1/，所有模块接口统一在 /api/ 下。系统日志模块的 /api/log 路径保持不变。

C. 错误码体系差异
模块	错误码风格
实时监控	5位数字（40001-50301），按HTTP状态码分组
趋势图表	5位数字（10001-90001），按业务层级分组
设备历史记录	HTTP标准状态码（400/401/403/404）
系统日志	5位数字（10001-90001），与趋势图表一致
建议：统一使用 5 位数字错误码，参照趋势图表和系统日志模块的体系。

D. 分页参数差异
模块	页码字段	条数字段	总数字段	数据数组字段
实时监控	page	limit	total	list
趋势图表	—（聚合）	—	—	data
设备历史记录	page	size	total	list
系统日志	page	limit	count	results
建议：统一分页参数为 page/size，总数用 total，数据用 list。

E. 字段命名差异
概念	实时监控	趋势图表	设备历史记录	系统日志	数据库文档
支路编号	branch	branch	branch	device_code	branch
告警类型	alarm_type	alarm_level	alarm_level	—	alarm_level
处置状态	status	resolution_status	resolution_status	resolution_status	resolution_status
告警时间	timestamp	timestamp	timestamp	alarm_date+alarm_time	timestamp
最高温度	temperature	temperature	temperature	max_temperature	temperature
建议：以数据库文档字段命名为准，接口层保持一致性。

文档版本：V1.0（汇总版） 汇总日期：2026-07-02 原始文档：实时监控模块 (lzw) / 趋势图表模块 (wlj) / 设备历史记录模块 (cgj) / 系统日志模块 (zhy)