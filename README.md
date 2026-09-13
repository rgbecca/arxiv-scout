# 📄 arxiv-scout

每天自动帮你从 arXiv 拉取新论文、用 LLM 按你的研究方向打分，把最相关的几篇推送到邮箱；可选联动 [paperwise](https://github.com/HJCheng0602/paperwise) 做深度精读。

## 功能

- 每日从 arXiv 指定分类拉取新论文
- 关键词预筛 + DeepSeek LLM 相关性评分（1-10 分）+ 一句话中文摘要
- 识别论文是否已被顶会/顶刊确认接收（启发式，基于 arXiv 的 comment/journal_ref 字段）
- 推送 Top N 到邮箱（简洁 HTML 格式）
- 所有论文元数据自动存入 SQLite 数据库，按 arXiv ID 去重
- 收藏感兴趣的论文（`star.py`），可选联动 [paperwise](https://github.com/HJCheng0602/paperwise) 批量生成精读报告（`deepread.py`）
- 改研究方向只需编辑 `config.yaml`

## 5 分钟部署

### 1. Fork 或 clone 本仓库

```bash
git clone https://github.com/<你的用户名>/arxiv-scout.git
cd arxiv-scout
```

### 2. 获取 API Key

- **DeepSeek API Key**：去 [platform.deepseek.com](https://platform.deepseek.com) 注册，充值 10 元够用几个月
- **邮箱 SMTP**：见下方各邮箱配置说明

### 3. 在 GitHub 仓库设置 Secrets

进入你的 repo → Settings → Secrets and variables → Actions → New repository secret，添加以下 secrets：

| Secret 名称 | 说明 | 示例 |
|---|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | `sk-xxxxxxxx` |
| `SMTP_SERVER` | 邮箱 SMTP 服务器 | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP 端口 | `587` |
| `SMTP_USER` | 发件邮箱地址 | `you@gmail.com` |
| `SMTP_PASSWORD` | 邮箱密码或应用专用密码 | `xxxx xxxx xxxx xxxx` |
| `TO_EMAIL` | 收件邮箱 | `you@example.com` |

### 4. 修改研究方向

编辑 `config.yaml` 中的 `discovery` 部分（自然语言描述 + arXiv 分类 + 关键词），完整字段说明见文件内注释。

### 5. 启用 GitHub Actions

进入 Actions 页面 → 点击 "I understand my workflows, go ahead and enable them"

### 6. 手动测试

Actions → Daily Paper Digest → Run workflow → 等待完成 → 检查邮箱

默认每天 UTC 22:00（北京时间 06:00）自动运行，可在 `.github/workflows/daily.yml` 里改 `cron` 调整时间。

## 邮箱 SMTP 配置参考

### Gmail（推荐，最稳定）
- `SMTP_SERVER`: `smtp.gmail.com`
- `SMTP_PORT`: `587`
- `SMTP_USER`: 你的 Gmail 地址
- `SMTP_PASSWORD`: [应用专用密码](https://myaccount.google.com/apppasswords)（不是 Gmail 登录密码）

### QQ 邮箱
- `SMTP_SERVER`: `smtp.qq.com`
- `SMTP_PORT`: `587`
- `SMTP_USER`: 你的 QQ 邮箱
- `SMTP_PASSWORD`: 在 QQ 邮箱设置中生成的授权码

### 163 邮箱
- `SMTP_SERVER`: `smtp.163.com`
- `SMTP_PORT`: `587`
- `SMTP_USER`: 你的 163 邮箱
- `SMTP_PASSWORD`: 在设置中开启 SMTP 后生成的授权码

## 本地开发 / 调试

```bash
pip install -r requirements.txt

# 设置环境变量
export DEEPSEEK_API_KEY="sk-xxx"
export SMTP_USER="you@gmail.com"
export SMTP_PASSWORD="xxxx"
export TO_EMAIL="you@example.com"
export SMTP_SERVER="smtp.gmail.com"
export SMTP_PORT="587"

# 运行每日抓取 + 评分 + 推送
cd src && python main.py
```

## 收藏与深度精读（可选）

每天看完推送邮件，觉得哪几篇值得细读，可以本地收藏：

```bash
cd src
python star.py                    # 交互模式：列出近期推送、未收藏的论文，输入序号选择
python star.py 2506.00001         # 或直接指定 arXiv ID
python star.py --download 2506.00001   # 额外下载 PDF 作为本地备份（默认不下载）
```

如果想要更进一步生成结构化精读报告 + 向量知识库检索，需要额外安装独立项目 [paperwise](https://github.com/HJCheng0602/paperwise)：

```bash
git clone https://github.com/HJCheng0602/paperwise.git
cd paperwise && pip install -e . && cp .env.example .env
# 编辑 .env 填入 LLM Key（复用 DEEPSEEK_API_KEY 即可）
```

然后回到本项目，指定 paperwise 的路径并批量精读已收藏的论文：

```bash
export PAPERWISE_REPO_DIR="/path/to/paperwise"
cd src && python deepread.py              # 处理所有已收藏但还没精读的论文
python deepread.py 2506.00001             # 或只处理指定论文
```

报告会生成在 `paperwise/outputs/{arxiv_id}_{标题}/report.md`。这一步完全可选，不装 paperwise 不影响每日推送功能。

## 项目结构

```
config.yaml          # 研究方向 / 分类 / 关键词配置
src/
  fetch.py           # 从 arXiv 拉取新论文
  score.py           # 调用 DeepSeek 评分 + 生成摘要
  store.py           # SQLite 存储 + 去重
  email_push.py      # 邮件推送
  star.py            # 收藏待精读论文
  deepread.py        # 调用 paperwise 批量精读（可选）
  main.py            # 每日主流程入口
data/papers.db        # 论文元数据（首次运行自动创建）
.github/workflows/    # 每日定时任务
tests/                # 收藏/精读流程的离线单元测试
```

## 成本

DeepSeek 评分约 **¥0.05/天**（每天约评 100 篇论文的标题+摘要）。GitHub Actions 对 public repo 完全免费。paperwise 精读一篇论文约 $0.005-0.01。
