# 微信养号自动化系统

> **目标**: 在真实 Android 手机上自动模拟真人使用微信，批量养出 L1~L4 级别的深度使用微信号，用于手机性能 benchmark 测试。
>
> **技术路线**: uiautomator2 + Python + ADB + OpenCV + EasyOCR，纯手机端真机操作。定位策略为坐标 + 截图 + OpenCV + OCR 混合方案（因微信 FLAG_SECURE 屏蔽 UiAutomation 控件树）。
>
> **详细方案**: 参见 [`具体执行方案.md`](具体执行方案.md)（架构设计、实施路线图、功能状态清单）。

---

## 一、系统要求

### 硬件
- **PC**: Windows / macOS / Linux，USB 接口充足
- **手机**: Android 11+ 真机（推荐 Moto 测试机），每台登录 1 个微信号
- **SIM 卡**: 每台手机 1 张独立 4G SIM 卡
- **USB 线**: 数据线（非仅充电线），如需多台手机建议配 USB Hub（带外接供电）

### 软件
- Python 3.10+
- ADB（Android Debug Bridge）
- 微信最新版（手机端）

---

## 二、快速上手

### 2.1 环境搭建

```bash
# 1. 进入项目目录
cd wechat_farm

# 2. 创建虚拟环境
python -m venv wechat_env
wechat_env\Scripts\activate   # Windows
# source wechat_env/bin/activate  # macOS / Linux

# 3. 安装依赖
pip install -r requirements.txt

# 4. 手机端配置
#    a) 开启开发者模式 → USB 调试 → 不锁定屏幕
#    b) USB 连接电脑，手机上点"允许 USB 调试"
#    c) 安装 uiautomator2 agent 到手机：
python -m uiautomator2 init

# 5. 初始化项目
python main.py init
```

### 2.2 验证连通性

```bash
# 确认 ADB 识别到手机
adb devices
# 预期输出:  XXXXXXXX    device

# 启动 weditor 查看微信控件树（开发调试必备）
python -m weditor
# 浏览器打开 http://localhost:17310，连接设备后查看控件树
```

### 2.3 调试模式（先人工操作看是否有bug）

```bash
# 快速调试：一键跑通全部核心功能（约20分钟）
#   ① 发朋友圈(1张图)  ② 朋友圈点赞+评论  ③ 发送文字
#   ④ 发送图片        ⑤ 刷视频号(3min)    ⑥ 阅读公众号(2min)
#   ⑦ 浏览收藏夹(1min)
# 联系人配置: 编辑 scripts/fast_test.py 顶部 CONTACT_NAME
python main.py fast-debug

# 完整调试：单设备执行一次当天养号剧本（按时间窗口调度）
python main.py debug
```

### 2.4 服务器自动化部署

完成前三步后，配置定时任务让系统每天自动运行。

#### 2.4.1 一次性配置

服务器上可能有多台设备，为避免干扰，此处手动完成：

```bash
# 1. 手动建库
python -c "from storage.db import Database; db = Database('wechat_farm.db'); db.init_db()"

# 2. 录入账号（替换为实际的序列号和注册日期）
python -c "
from storage.db import Database
db = Database('wechat_farm.db')
db.insert_account(id='acc_001', device_serial='N0URB40116', registration_date='2026-07-01', batch_name='batch_a', persona_id='p01')
db.bind_device(serial='N0URB40116', account_id='acc_001')
"

# 3. 验证（只操作指定设备）
python -c "
import uiautomator2 as u2
d = u2.connect('N0URB40116')
d.app_start('com.tencent.mm')
print('OK')
"
```

> 多台手机时，每台重复步骤 2~3 即可。

#### 2.4.2 设置定时任务

**Windows（任务计划程序）：**

```powershell
# 每天早上 7:00 执行当日养号剧本
schtasks /create /tn "WechatFarm_Daily" /tr "d:\养微信号\wechat_farm\wechat_env\Scripts\python.exe d:\养微信号\wechat_farm\main.py run" /sc daily /st 07:00

# 每周一推进阶段
schtasks /create /tn "WechatFarm_Advance" /tr "d:\养微信号\wechat_farm\wechat_env\Scripts\python.exe d:\养微信号\wechat_farm\main.py advance" /sc weekly /d MON /st 08:00
```

**Linux（Cron）：**

```bash
crontab -e
0 7 * * * cd /path/to/wechat_farm && ./wechat_env/bin/python main.py run >> logs/cron.log 2>&1
0 8 * * 1 cd /path/to/wechat_farm && ./wechat_env/bin/python main.py advance >> logs/cron.log 2>&1
```

#### 2.4.3 启动 Agent 监控

完成 2.4.2 后，需**手动**对 Agent 发以下指令，激活 24h 监控：

**第 1 步：让 Agent 阅读项目规则**

```
请阅读 wechat_farm/CLAUDE.md，你现在是本项目的上层调度员，24h 辅助项目运行。
```

**第 2 步：设置定时检查（逐条发送）**

```
设置每天早上 7:05 检查昨晚日志，有失败动作通知我
设置每天晚上 22:00 生成今日报告总结
设置每 4 小时检查 adb devices，设备离线通知我
```

---

完成以上两步后，你的自动化系统架构：

```
Windows 任务计划（07:00 自动执行剧本）
       +
Agent 定时监控（07:05 / 22:00 / 每4h 检查日志和设备）
       =
完整的 24h 无人值守自动化
```

---

## 三、常用命令

| 命令 | 说明 |
|------|------|
| `python main.py init` | 初始化数据库，检测设备 |
| `python main.py fast-debug` | **快速调试** — 一键跑通全部核心功能（约20分钟） |
| `python main.py debug` | **完整调试** — 单设备执行一次当天剧本 |
| `python main.py run` | **生产模式** — 全部设备并发运行 |
| `python main.py status` | 查看所有设备在线状态 |
| `python main.py accounts` | 查看所有账号列表（阶段/状态/等级） |
| `python main.py report` | 生成当日的养号运行报告 |
| `python main.py advance` | 检查并推进所有账号的养号阶段 |
| `python main.py health-check <账号ID>` | 对指定账号执行健康检查 |
| `python -c "from monitor.health_check import DeviceHealthChecker; DeviceHealthChecker().run_all()"` | 设备健康检查(12项) |
| `python -c "from monitor.health_check import AccountHealthChecker; import uiautomator2 as u2; AccountHealthChecker(u2.connect()).run_all()"` | 账号健康检查(6项) |

---

## 四、账号录入

在数据库中录入账号信息（首次使用需要）：

```python
# 方式1: Python 交互式
from storage.db import Database
db = Database("wechat_farm.db")
db.init_db()

# 插入账号
db.insert_account(
    id="acc_001",
    wechat_id="wxid_xxx",
    device_serial="ABCD1234",       # adb devices 看到的序列号
    registration_date="2026-07-01", # 注册日期
    batch_name="batch_a",
    persona_id="p01",
    phone="138xxxx1234",
)

# 绑定设备
db.bind_device(
    serial="ABCD1234",
    account_id="acc_001",
    model="Moto G54",
    android_version="14",
)
```

```bash
# 方式2: 直接用 SQLite
sqlite3 wechat_farm.db

INSERT INTO accounts (id, wechat_id, device_serial, registration_date, batch_name, persona_id)
VALUES ('acc_001', 'wxid_xxx', 'ABCD1234', '2026-07-01', 'batch_a', 'p01');
```

### 录入好友

剧本中的聊天动作会从 `friends` 表随机抽取联系人。需手动录入：

```python
db.add_friend(
    account_id="acc_001",
    friend_name="张三",           # 微信里的昵称或备注，聊天时用这个名字搜索
    friend_wechat_id="wxid_xxx",  # 可选
)
```

或 SQL：

```sql
INSERT INTO friends (account_id, friend_name) VALUES ('acc_001', '张三');
```

---

## 五、项目结构

```
wechat_farm/
├── main.py                        # CLI 主入口
├── CLAUDE.md                      # Agent 调度配置（供上层 AI 阅读）
├── config/         # 配置: 全局参数、阶段规则、元素定位字典
├── core/           # 核心(15个模块): 微信操作、OCR识别、拟人化引擎
│   ├── wechat_control.py          # ← 统一调用入口
│   ├── moments_interact.py        # 朋友圈点赞/评论 (OCR定位)
│   ├── moment_poster.py           # 发朋友圈 (6阶段自动)
│   ├── message_sender.py          # 发送文字消息
│   ├── image_sender.py            # 发送图片消息
│   ├── channels_browser.py        # 刷视频号
│   ├── public_account_browser.py  # 浏览公众号
│   ├── favorites_browser.py       # 浏览收藏夹
│   ├── search_helper.py           # 全局搜索
│   └── humanizer.py               # 拟人化引擎
├── scripts/        # 行为剧本: 4个阶段 + 快速调试
├── scheduler/      # 定时调度、任务队列、批次管理
├── monitor/        # 健康检查(18项)、告警、指标上报
├── storage/        # SQLite 数据库
├── content/        # 文案模板、人格档案、LLM客户端
└── utils/          # 日志、ADB工具、截图工具
```

---

## 六、养号四阶段

| 阶段 | 时长 | 核心行为 | 每日限量 |
|------|------|---------|---------|
| **信任积累期** | 第1-2周 | 刷朋友圈、看视频号、读文章、搜索、支付 | 不互动 |
| **轻度互动期** | 第3-4周 | 开始聊天、点赞、发圈2-3条/周 | 加1-2好友/天 |
| **正常使用期** | 第2-3月 | 正常社交频率，全面互动 | 加3-5好友/天 |
| **成熟期** | 3个月后 | 自然维持，可投入测试 | 正常使用 |

---

## 七、已实现功能

| 类别 | 已实现 |
|------|--------|
| 朋友圈 | 浏览、发图文、点赞、评论 |
| 聊天 | 发送文字、发送图片 |
| 视频号 | 刷视频、点赞 |
| 公众号 | 阅读文章、收藏文章 |
| 搜索 | 全局搜索 |
| 收藏夹 | 浏览 |
| 系统 | 支付页面、设备健康检查(12项)、账号健康检查(6项)、行为日志 |


---

## 八、环境变量（可选）

```bash
# LLM API（用 AI 生成聊天内容/朋友圈文案）
set LLM_API_KEY=sk-xxxxxxxx          # DeepSeek API Key
set LLM_BASE_URL=https://api.deepseek.com

# 钉钉告警（出现异常时自动通知）
set DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=xxx
```

---

## 九、调试技巧

### 9.1 单步操作验证

```python
import uiautomator2 as u2
d = u2.connect()
d.app_start("com.tencent.mm")

# 逐句测试
d(text="发现").click()
d(text="朋友圈").exists       # True → 定位成功
d(text="朋友圈").click()
```

### 9.2 直接调用核心模块

```python
from core.wechat_control import WeChatControl
from core.humanizer import Humanizer

d = u2.connect()
wc = WeChatControl(d, Humanizer())

wc.open_moments()                             # 进入朋友圈
wc.scroll_moments(5)                          # 刷5次
wc.like_moment(0)                             # 点赞第1条
wc.comment_moment("说得好", post_index=1)      # 评论第2条
wc.browse_moments_interact(120, "哈哈", 0.5)   # 浏览2min随机互动
wc.post_moment("文案", image_count=3)          # 发朋友圈(3图)
wc.send_message("你好", contact="张三")        # 发消息
wc.scroll_channels(20, like_rate=0.2)          # 刷视频号
wc.browse_favorites(120)                      # 浏览收藏夹
wc.global_search("天气")                      # 全局搜索
```

### 9.3 查看运行日志

```bash
# 日志文件
tail -f logs/wechat_farm_*.log

# 查看错误日志
tail -f logs/error_*.log
```

### 9.4 查看数据库

```bash
# 查看今日操作
sqlite3 wechat_farm.db "SELECT * FROM action_logs WHERE date(executed_at)=date('now') ORDER BY executed_at DESC LIMIT 20;"

# 查看失败操作
sqlite3 wechat_farm.db "SELECT account_id, action_type, error_msg FROM action_logs WHERE success=0 ORDER BY executed_at DESC LIMIT 20;"

# 查看账号状态
sqlite3 wechat_farm.db "SELECT id, stage, state, mode FROM accounts;"
```

---

## 十、常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| `d(text="xxx").click()` 报错不存在 | 微信元素 text 变了 | 用 weditor 确认当前值，更新 `wechat_elements.py` |
| `d.app_start("com.tencent.mm")` 失败 | ATX agent 异常 | `python -m uiautomator2 init` 重装 agent |
| 手机锁屏后自动化卡住 | 未开启"不锁定屏幕" | 去开发者选项开启 |
| USB 偶尔断开 | 线材或 Hub 供电不足 | 换数据线，Hub 配外接电源 |
| 多台手机 `adb devices` 时有时无 | USB 端口冲突 | 每台独立 USB 口，减少 Hub 串联层级 |
| 微信更新后定位全部失效 | resourceId 变化 | weditor 重新抓取，更新定位字典 |
| EasyOCR 首次运行慢 | 下载模型 ~100MB | 仅首次，后续使用缓存 |

---

## 十一、红线（绝对禁止）

- ❌ 使用模拟器或云手机（3分钟内被识别）
- ❌ 使用微信多开/外挂/Xposed 框架（直接封号）
- ❌ 同一 IP 批量操作多个微信号（关联封号）
- ❌ 养的号互相加好友/进同一群（一锅端）
- ❌ 使用 Hook/内存注入方式操控微信
- ❌ 批量同时加好友（单日超阈值即功能限制）

---

> **项目版本**: v2.4 | **创建日期**: 2026-07-10 | **更新**: 2026-07-23
> **技术路线**: uiautomator2 + Python + ADB + OpenCV + EasyOCR（坐标/控件/截图/OCR 混合定位）
> **测试设备**: Moto X70 Air Pro (1264×2780, Android 14) | **测试账号**: 稀有气体
