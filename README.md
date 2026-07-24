# 微信养号自动化系统

> **目标**: 在真实 Android 手机上自动模拟真人使用微信，批量养出 L1~L4 级别的深度使用微信号，用于手机性能 benchmark 测试。
>
> **技术路线**: uiautomator2 + Python + ADB + OpenCV + EasyOCR，纯手机端真机操作。定位策略为坐标 + 截图 + OpenCV + OCR 混合方案（因微信 FLAG_SECURE 屏蔽 UiAutomation 控件树）。
>
> **详细方案**: 参见 [`具体执行方案.md`](具体执行方案.md)（架构设计、实施路线图、功能状态清单）。
>
> **使用手册**: 参见 [`使用手册.md`](使用手册.md)（新增设备、更换服务器、日常运维、修改剧本等操作指南）。

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
cd wechat_farm
python -m venv wechat_env
wechat_env\Scripts\activate        # Windows
pip install -r requirements.txt
python -m uiautomator2 init        # 手机上装 agent
python main.py init                # 初始化数据库
```

### 2.2 验证连通性

```bash
adb devices                        # 看到设备序列号即正常
python main.py fast-debug          # 一键跑通全部功能（约20min）
```

### 2.3 服务器部署

```bash
# 1. 手动建库 + 录入账号 + 验证（详见使用手册）
# 2. 设置 Cron 定时任务
crontab -e
0 7 * * * cd ~/wechat_farm && ./wechat_env/bin/python main.py run >> logs/cron.log 2>&1
0 8 * * 1 cd ~/wechat_farm && ./wechat_env/bin/python main.py advance >> logs/cron.log 2>&1

# 3. 启动 Agent 监控（详见使用手册）
```

> 服务器上有其他设备时，不要运行 `python main.py init`，会干扰其他设备。详细步骤参见 [`使用手册.md`](使用手册.md)。

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

## 四、项目结构

```
wechat_farm/
├── main.py                        # CLI 主入口
├── CLAUDE.md                      # Agent 调度配置（供上层 AI 阅读）
├── 使用手册.md                    # 运维操作指南（新增设备、更换服务器等）
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

## 五、养号四阶段

| 阶段 | 时长 | 核心行为 | 每日限量 |
|------|------|---------|---------|
| **信任积累期** | 第1-2周 | 刷朋友圈、看视频号、读文章、搜索、支付 | 不互动 |
| **轻度互动期** | 第3-4周 | 开始聊天、点赞、发圈2-3条/周 | 加1-2好友/天 |
| **正常使用期** | 第2-3月 | 正常社交频率，全面互动 | 加3-5好友/天 |
| **成熟期** | 3个月后 | 自然维持，可投入测试 | 正常使用 |

---

## 六、已实现功能

| 类别 | 已实现 |
|------|--------|
| 朋友圈 | 浏览、发图文、点赞、评论 |
| 聊天 | 发送文字、发送图片 |
| 视频号 | 刷视频、点赞 |
| 公众号 | 阅读文章、收藏文章 |
| 搜索 | 全局搜索 |
| 收藏夹 | 浏览 |
| 系统 | 设备健康检查(12项)、账号健康检查(6项)、行为日志 |


---

## 七、环境变量（可选）

```bash
# LLM API（用 AI 生成聊天内容/朋友圈文案）
set LLM_API_KEY=sk-xxxxxxxx          # DeepSeek API Key
set LLM_BASE_URL=https://api.deepseek.com

# 钉钉告警（出现异常时自动通知）
set DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=xxx
```

---

## 八、调试技巧

### 8.1 单步操作验证

```python
import uiautomator2 as u2
d = u2.connect()
d.app_start("com.tencent.mm")

# 逐句测试
d(text="发现").click()
d(text="朋友圈").exists       # True → 定位成功
d(text="朋友圈").click()
```

### 8.2 直接调用核心模块

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

### 8.3 查看运行日志

```bash
# 日志文件
tail -f logs/wechat_farm_*.log

# 查看错误日志
tail -f logs/error_*.log
```

### 8.4 查看数据库

```bash
# 查看今日操作
sqlite3 wechat_farm.db "SELECT * FROM action_logs WHERE date(executed_at)=date('now') ORDER BY executed_at DESC LIMIT 20;"

# 查看失败操作
sqlite3 wechat_farm.db "SELECT account_id, action_type, error_msg FROM action_logs WHERE success=0 ORDER BY executed_at DESC LIMIT 20;"

# 查看账号状态
sqlite3 wechat_farm.db "SELECT id, stage, state, mode FROM accounts;"
```

---

## 九、常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| `d(text="xxx").click()` 报错不存在 | 微信元素 text 变了 | 用 weditor 确认当前值，更新 `wechat_elements.py` |
| `d.app_start("com.tencent.mm")` 失败 | ATX agent 异常 | `python -m uiautomator2 init` 重装 agent |
| 手机锁屏后自动化卡住 | 未开启"不锁定屏幕" | 去开发者选项开启 |
| USB 偶尔断开 | 线材或 Hub 供电不足 | 换数据线，Hub 配外接电源 |
| 多台手机 `adb devices` 时有时无 | USB 端口冲突 | 每台独立 USB 口，减少 Hub 串联层级 |
| 微信更新后定位全部失效 | resourceId 变化 | weditor 重新抓取，更新定位字典 |
| EasyOCR 首次运行慢 | 下载模型 ~100MB | 仅首次，后续使用缓存 |


