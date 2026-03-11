# 学习策略师个人归档器

把微信公众号目录页中的文章按分类整理为 Markdown，仅用于个人学习、检索与本地 RAG。

## 合规边界

- 只抓取网页端可正常访问的公众号文章。
- 不绕过风控、验证码或付费限制。
- 如果微信弹出环境异常/验证码页，脚本会停下；可在有头模式下人工处理后继续。
- 只保存纯文字，不保存图片。

## 目录结构

```text
d:\Desk\Celueshi\
  README.md
  requirements.txt
  src\
    main.py
    wechat_client.py
    directory_parser.py
    article_extractor.py
    grouping.py
    writer.py
    models.py
    utils.py
  output_md\
  state\
    browser_profile\
    progress.json
    article_cache\
    directory_cache\
    run_context.json
  logs\
  tests\
```

## 安装

```powershell
cd d:\Desk\Celueshi
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

## 用法

先看目录页能识别出哪些分组：

```powershell
.\.venv\Scripts\python src/main.py catalog --index-url "https://mp.weixin.qq.com/s/3kYQGLeX5NHNd5U8Bjlorg" --headless false
```

抓取全部：

```powershell
.\.venv\Scripts\python src/main.py crawl --index-url "https://mp.weixin.qq.com/s/3kYQGLeX5NHNd5U8Bjlorg" --out ".\output_md" --headless false
```

只抓某个一级分类：

```powershell
.\.venv\Scripts\python src/main.py crawl --index-url "https://mp.weixin.qq.com/s/3kYQGLeX5NHNd5U8Bjlorg" --category "学科学习" --out ".\output_md" --headless false
```

只抓某个二级分类：

```powershell
.\.venv\Scripts\python src/main.py crawl --index-url "https://mp.weixin.qq.com/s/3kYQGLeX5NHNd5U8Bjlorg" --category "学科学习" --section "语文" --out ".\output_md" --headless false
```

## 输出规则

- 一级分类作为文件夹，例如 `output_md\学科学习\`
- 二级分类作为 Markdown 文件，例如 `output_md\学科学习\语文.md`
- 如果一级分类下没有二级分类，则直接写成同名文件，例如 `output_md\信息源\信息源.md`
- 每篇文章格式如下：

```md
# 语文

## 深度|今年高考作文的玄机与应对
> 来源：https://mp.weixin.qq.com/s/...

正文...
```

## 正文清洗

- 删除图片、音视频、二维码、推荐卡片等非文字节点
- 只保留正文纯文本
- 出现以下内容前截断：
  - `报名链接`
  - `试听课链接`
  - `购课相关咨询请添加`
  - `写留言`

## 断点续跑

- 已成功抓取的文章会写入 `state\article_cache\`
- 进度写入 `state\progress.json`
- 重复执行相同 `crawl` 命令会跳过已完成文章
- 使用 `--force` 可强制重抓

## 有头 / 无头

- `--headless false`
  - 显示浏览器窗口
  - 更适合第一次调试和人工处理微信验证码
- `--headless true`
  - 后台运行
  - 更省资源

## 已知风险

- 微信公众号偶尔会触发环境异常页，尤其是在连续打开很多文章时。
- 如果有头模式下遇到验证码，按页面提示手动处理，再回终端继续即可。
- 少数旧文章如果已失效或被删除，会记录到日志并继续后续文章。
