# 得到个人学习内容归档器

一个仅供个人学习归档使用的本地工具：在你已经手动登录、且网页端可正常阅读的前提下，把得到课程文章正文整理为 Markdown，便于本地检索或 RAG。

## 合规边界

- 只处理你已购买、已解锁、并且网页端可直接阅读的内容。
- 不绕过付费、风控、验证码、DRM 或反爬机制。
- 登录只能通过浏览器人工完成；脚本不会要求你输入账号密码，也不会单独导出 cookies。
- 抓取默认串行执行，每讲间隔 2 到 4 秒，避免对网站造成压力。
- 一旦检测到验证码、风险提示、访问异常等文案，脚本立即停止，等待你手动处理。

## 环境要求

- Windows
- Python 3.10+
- Chromium 浏览器由 Playwright 自动安装

## 安装

在 `d:\Desk\Jingyingrike` 目录执行：

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

## 首次登录

```powershell
python src/main.py login --course-url "<课程主页URL>"
```

执行后会打开可见浏览器。你手动完成登录后，回到终端按 Enter，脚本会刷新课程页并校验登录态；成功后浏览器状态保存在 `state\browser_profile\`。

## 抓取

抓取全部：

```powershell
python src/main.py crawl --course-url "<课程主页URL>" --out ".\output_md"
```

只抓某个专题：

```powershell
python src/main.py crawl --course-url "<课程主页URL>" --topic "再看一眼" --out ".\output_md"
```

列出当前课程内所有可抓取专题：

```powershell
python src/main.py topics --course-url "<课程主页URL>" --headless false
```

按专题范围抓取，例如从 `发刊词` 到 `发现，而非设计`：

```powershell
python src/main.py crawl --course-url "<课程主页URL>" --start-topic "发刊词" --end-topic "发现，而非设计" --out ".\output_md" --headless false
```

从某个专题后面开始，连续抓接下来的 2 个专题：

```powershell
python src/main.py crawl --course-url "<课程主页URL>" --start-after-topic "再看一眼" --topic-limit 2 --out ".\output_md" --headless false
```

如果不指定 `--start-after-topic`，只写 `--topic-limit 2`，则会从课程里的第一个专题开始连续抓 2 个专题。

如果想更稳妥地长时间跑，可以按批次抓取并在批次之间自动冷却，例如每批 2 本、批次间暂停 45 秒：

```powershell
python src/main.py crawl --course-url "<课程主页URL>" --start-topic "发刊词" --end-topic "发现，而非设计" --batch-size 2 --batch-cooldown 45 --out ".\output_md" --headless false
```

如果某个区间中有不想抓的专题，可以重复传入 `--exclude-topic` 排除：

```powershell
python src/main.py crawl --course-url "<课程主页URL>" --start-topic "非专业知识·价值对齐" --end-topic "第六季结束语" --exclude-topic "万维钢·高手修炼手册" --batch-size 2 --batch-cooldown 45 --out ".\output_md" --headless false
```

## 断点续跑

- 已成功抓取且缓存存在的讲次，后续会自动跳过。
- Markdown 文件通过缓存重建，不做逐条追加，避免重复章节或半截文件。
- 失败讲次修复后重新执行 `crawl` 即可补抓。

## 输出结构

- `src\`：代码
- `output_md\`：生成的 Markdown
- `state\`：浏览器会话、进度、缓存
- `logs\`：运行日志
- `tests\`：单元测试

## 运行测试

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

## 合规提示

- 本项目仅用于个人学习归档
- 仅抓取你本人已购买且网页登录可见的内容
- 不得尝试绕过付费、验证码、风控或 DRM
