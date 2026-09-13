# 📄 arxiv-scout

每天自动帮你从 arXiv 拉取新论文、用 LLM 按你的研究方向打分，把最相关的几篇推送到邮箱；可选联动 [paperwise](https://github.com/HJCheng0602/paperwise) 做深度精读。

## 功能

- 每日从 arXiv 指定分类拉取新论文
- 关键词预筛 + DeepSeek LLM 相关性评分（1-10 分）+ 一句话中文摘要
- 识别论文是否已被顶会/顶刊确认接收（启发式，基于 arXiv 的 comment/journal_ref 字段）
- 推送 Top N 到邮箱（简洁 HTML 格式）
- 所有论文元数据自动存入 SQLite 数据库，按 arXiv ID 去重（Actions 会以 bot 身份每日自动 commit 更新这个数据库文件）
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

## 常见问题

**Actions 显示绿勾但没收到邮件？**
`SMTP_USER`/`SMTP_PASSWORD`/`TO_EMAIL` 任一没配置时，程序会跳过发送并在日志里打印警告，但整个 workflow 仍然算成功（不算报错）。去 Actions → 具体某次 run → 展开 "Run daily digest" 步骤看日志，搜 `[警告]` 关键字确认具体原因。

**DeepSeek API 报错 model not found / invalid model？**
说明 `config.yaml` 里 `llm.model` 填的名字在 DeepSeek 那边已经下线或改名了，去 [platform.deepseek.com](https://platform.deepseek.com) 文档页确认当前可用模型列表，改成正确的名字。

**Gmail 一直登录失败？**
必须用[应用专用密码](https://myaccount.google.com/apppasswords)，不是你的 Gmail 登录密码；且账号需要先开启两步验证才能生成应用专用密码。

**当天没有推送、Actions 日志显示"今日无新论文"？**
正常现象，arXiv 周末和部分节假日不更新，脚本会直接跳过退出。

**想确认 Secrets 是否都配置对了？**
去 Actions → Daily Paper Digest → Run workflow 手动触发一次，比等第二天早上更快看到结果。

## 致谢

项目调研阶段参考了以下同类项目的设计思路（每日推送、配置化研究方向、本地存储、知识图谱等）：

- [gpt_paper_assistant](https://github.com/tatsu-lab/gpt_paper_assistant)
- [daily-arXiv-ai-enhanced](https://github.com/dw-dengwei/daily-arXiv-ai-enhanced)
- [Aries](https://github.com/LAMDA-NeSy/Aries)
- [zotero-arxiv-daily](https://github.com/TideDra/zotero-arxiv-daily)
- [paperwise](https://github.com/HJCheng0602/paperwise)
- [litgraph](https://github.com/kl-demi/litgraph)
- [papersearch](https://github.com/dylansechet/papersearch)
- [academic-paper-scraper](https://github.com/labrat-0/academic-paper-scraper)
- [research-papers-mcp](https://pypi.org/project/research-papers-mcp/)

本项目由 **Claude Sonnet 5** 协助设计与实现。

## License

MIT License，见 [LICENSE](LICENSE)。
