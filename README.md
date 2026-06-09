# 膜结构车棚 / 遮阳棚 - 自动获客系统

自动化线索采集、触达、意向筛选、人工交接的一站式获客工具。

## 快速开始

### 1. 安装依赖

```
pip install -r requirements.txt
```

### 2. 修改配置

编辑 `config/settings.py`，修改以下关键配置：

- `BUSINESS_NAME` - 公司名称
- `BUSINESS_PHONE` - 联系电话
- `BUSINESS_WECHAT` - 微信号
- `BUSINESS_REGION` - 所在城市
- `TARGET_AREAS` - 目标采集区域
- `PRODUCT_KEYWORDS` - 产品关键词

### 3. 启动系统

```
# 完整系统（Web后台 + 自动采集 + 自动触达）
python main.py

# 仅启动Web管理后台
python main.py --web-only

# 自定义端口
python main.py --port 8080
```

启动后访问 http://localhost:5000 打开管理后台。

## 常用命令

```
# 手动执行一次线索采集
python main.py --harvest

# 手动执行一次自动触达
python main.py --outreach

# 从Excel导入已有客户数据
python main.py --import 客户名单.xlsx

# 查看数据统计
python main.py --stats
```

## Excel 导入格式

准备一个Excel文件，第一行为表头，支持以下字段名（中英文均可）：

| 字段 | 可用的表头名 |
|------|-------------|
| 名称 | 名称、公司、公司名、客户名称 |
| 联系人 | 联系人、姓名 |
| 电话 | 电话、手机、手机号 |
| 邮箱 | 邮箱、email |
| 微信 | 微信、微信号 |
| 地址 | 地址、详细地址 |
| 类型 | 类型、客户类型 |
| 区域 | 区域、地区 |
| 需求 | 需求、需求描述 |
| 备注 | 备注 |

系统会自动去重（基于电话号码）。

## 系统架构

```
数字营销/
├── config/
│   └── settings.py          # 系统配置（业务信息、关键词、渠道开关）
├── lead_harvester/
│   ├── harvester_main.py    # 采集调度器
│   ├── map_harvester.py     # 百度地图POI采集
│   ├── search_harvester.py  # 搜索引擎采集
│   └── classified_harvester.py  # 58同城等分类信息采集
├── auto_outreach/
│   ├── outreach_main.py     # 触达调度器
│   ├── sms_sender.py        # 短信发送（支持阿里云短信）
│   ├── wechat_sender.py     # 企业微信发送
│   └── email_sender.py      # 邮件发送
├── crm/
│   ├── models.py            # 数据库模型（线索、消息、日志）
│   └── database.py          # 数据库操作封装
├── dashboard/
│   ├── app.py               # Flask Web应用（API + 页面）
│   └── templates/           # HTML模板
├── data/                    # SQLite数据库文件
├── logs/                    # 运行日志
├── main.py                  # 主入口
└── requirements.txt
```

## 线索生命周期

```
新线索 → 已联系 → 有意向 → 报价中 → 已成交
                                  ↘ 已流失
```

- **新线索 (new)**: 刚采集或导入，尚未联系
- **已联系 (contacted)**: 已通过短信/微信/邮件触达
- **有意向 (interested)**: 客户回复或表达了兴趣
- **报价中 (quoting)**: 已发送报价
- **已成交 (closed_won)**: 成功签约
- **已流失 (closed_lost)**: 客户明确拒绝或长期无回复

## 意向评分机制

系统根据客户行为自动评分（0-100分）：

| 行为 | 加分 |
|------|------|
| 提供了电话 | +20 |
| 提供了地址 | +10 |
| 主动搜索找到我们 | +30 |
| 有明确面积需求 | +25 |
| 询价 | +40 |
| 要求上门测量 | +50 |
| 回复了消息 | +35 |
| 多次访问 | +20 |

评分达到 60 分时，系统会将该线索标记为"待人工接入"，在仪表盘高意向区域显示。

## 开通真实触达渠道

### 短信（阿里云短信）
1. 注册阿里云，开通短信服务
2. 申请短信签名和模板
3. 在 `config/settings.py` 中填写 `SMS_ACCESS_KEY` 等配置
4. 设置 `SMS_ENABLED = True`

### 企业微信
1. 注册企业微信
2. 创建自建应用，获取 CorpID/Secret/AgentID
3. 在配置中填写对应参数
4. 设置 `WECHAT_WORK_ENABLED = True`

### 邮件
1. 开通QQ邮箱/企业邮箱的SMTP服务
2. 获取授权码
3. 在配置中填写 SMTP 参数
4. 设置 `EMAIL_ENABLED = True`

## 注意事项

- 采集模块默认使用模拟模式，接入真实API前请先测试
- 短信/微信/邮件默认为模拟模式（日志中可见发送内容），不会真实发送
- 系统有每日发送上限保护，防止过度触达
- 建议在工作时间（9:00-18:00）发送营销消息
- 请遵守相关法律法规，合理使用自动化营销工具
