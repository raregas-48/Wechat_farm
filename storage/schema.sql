-- 微信养号自动化系统 — 数据库建表语句
-- SQLite 3.x

-- ============================================================
-- 账号表
-- ============================================================
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,                   -- 账号唯一标识
    wechat_id TEXT UNIQUE,                 -- 微信号
    phone TEXT,                            -- 绑定手机号
    device_serial TEXT,                    -- 绑定的手机设备序列号
    imei TEXT,                             -- 设备 IMEI
    sim_number TEXT,                       -- SIM 卡号
    registration_date TEXT,                -- 注册日期 "YYYY-MM-DD"
    batch_name TEXT,                       -- 所属批次
    stage TEXT DEFAULT 'trust_building',   -- 当前阶段
    persona_id TEXT,                       -- 人格模板 ID
    level TEXT DEFAULT 'L1',              -- 账号等级 L1-L5
    state TEXT DEFAULT 'normal',          -- 当前状态: normal/warning/cooldown/suspended/mature
    mode TEXT DEFAULT 'full',             -- 行为模式: full/consume_only/paused
    notes TEXT,                            -- 备注
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- ============================================================
-- 行为日志表
-- ============================================================
CREATE TABLE IF NOT EXISTS action_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    action_type TEXT NOT NULL,             -- 动作类型
    action_params TEXT,                    -- 动作参数 (JSON)
    scheduled_time TEXT,                   -- 计划执行时间
    executed_at TEXT,                      -- 实际执行时间
    success INTEGER DEFAULT 1,            -- 是否成功
    error_msg TEXT,                        -- 错误信息
    screenshot_path TEXT,                  -- 异常截图路径
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE INDEX IF NOT EXISTS idx_action_logs_account
    ON action_logs(account_id, executed_at);

CREATE INDEX IF NOT EXISTS idx_action_logs_type
    ON action_logs(action_type);

-- ============================================================
-- 好友列表表
-- ============================================================
CREATE TABLE IF NOT EXISTS friends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    friend_name TEXT NOT NULL,
    friend_wechat_id TEXT,
    source TEXT,                           -- 来源: active_add/passive_add/group
    added_date TEXT,
    last_chat_time TEXT,
    chat_count INTEGER DEFAULT 0,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE INDEX IF NOT EXISTS idx_friends_account
    ON friends(account_id);

-- ============================================================
-- 朋友圈记录表
-- ============================================================
CREATE TABLE IF NOT EXISTS moments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    content TEXT,
    has_images INTEGER DEFAULT 0,
    image_paths TEXT,                      -- JSON 数组
    posted_at TEXT,
    likes_count INTEGER DEFAULT 0,
    comments_count INTEGER DEFAULT 0,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE INDEX IF NOT EXISTS idx_moments_account
    ON moments(account_id, posted_at);

-- ============================================================
-- 健康检查记录表
-- ============================================================
CREATE TABLE IF NOT EXISTS health_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    check_time TEXT DEFAULT (datetime('now', 'localtime')),
    moments_visible INTEGER DEFAULT 1,     -- 朋友圈是否可见
    add_friend_normal INTEGER DEFAULT 1,   -- 加好友是否正常
    message_delay_ms REAL,                 -- 消息延迟（毫秒）
    captcha_count INTEGER DEFAULT 0,       -- 滑块验证次数
    risk_score REAL DEFAULT 0.0,          -- 风险评分
    state TEXT DEFAULT 'normal',          -- 判定状态
    notes TEXT,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE INDEX IF NOT EXISTS idx_health_checks_account
    ON health_checks(account_id, check_time);

-- ============================================================
-- 内容生成记录表（用于同质化检测）
-- ============================================================
CREATE TABLE IF NOT EXISTS content_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    content_type TEXT NOT NULL,            -- post/chat/comment
    content_hash TEXT,                     -- MD5 哈希
    content_preview TEXT,                  -- 内容摘要（前 50 字）
    source TEXT DEFAULT 'template',        -- 来源: template/llm
    generated_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE INDEX IF NOT EXISTS idx_content_history_hash
    ON content_history(content_hash);

-- ============================================================
-- 设备绑定表
-- ============================================================
CREATE TABLE IF NOT EXISTS device_bindings (
    serial TEXT PRIMARY KEY,               -- 设备序列号
    account_id TEXT UNIQUE,
    model TEXT,                            -- 设备型号
    android_version TEXT,                  -- Android 版本
    first_seen TEXT DEFAULT (datetime('now', 'localtime')),
    last_seen TEXT DEFAULT (datetime('now', 'localtime')),
    status TEXT DEFAULT 'active',         -- active/inactive/error
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);
