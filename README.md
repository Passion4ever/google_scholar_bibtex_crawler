# Google Scholar BibTeX Crawler

批量把 DOI 或论文标题转成 BibTeX 引用信息。

## 安装

```bash
pip install -r requirements.txt
```

## 新版(API 优先,推荐)

更快、更准、更一致:DOI 走官方 content negotiation 取**权威 BibTeX**,标题先消歧到 DOI 再取权威,严格相似度验证并**标记存疑**,多源交叉验证(Crossref / OpenAlex / DBLP / Semantic Scholar)。无需浏览器、零验证码。

```bash
python -m scholar_bibtex <input.txt> [output.bib] [--proxy HOST:PORT]
```

配置(环境变量或项目根目录的 `.env` 文件,环境变量优先;`.env` 已被 git 忽略):

- `CROSSREF_MAILTO`:进入 Crossref 礼貌池(更高速率),建议设置
- `OPENALEX_API_KEY`:启用 OpenAlex 源(2026-02 起必需;未设则自动跳过)
- `SEMANTIC_SCHOLAR_API_KEY`:可选,提升 Semantic Scholar 速率

`.env` 示例:

```
CROSSREF_MAILTO=you@example.com
OPENALEX_API_KEY=...
SEMANTIC_SCHOLAR_API_KEY=...
```

**多源交叉验证**:同一标题在多个源(Crossref/OpenAlex/DBLP/Semantic Scholar)若给出同一 DOI,可信度提升;若给出**不同** DOI(同名不同篇),标 `% REVIEW` 并在 `% NOTE` 列出冲突 DOI,绝不静默选错。F1000/年鉴/ResearchHub 等"转载/评注"DOI 会被自动排除。

输出每条带来源与置信标注;低置信匹配标 `% REVIEW` 需人工核对;失败条目写入 `<output>.failed.txt`。可选开关:`--no-openalex` / `--no-semantic-scholar` / `--no-dblp`、`--high` / `--low`(相似度阈值)、`--concurrency`。

真机冒烟测试(可选):`RUN_LIVE=1 python -m pytest tests/test_live_smoke.py`。

## Google Scholar 浏览器版(nodriver,准确度优先)

用浏览器直接抓 Google Scholar 的 BibTeX。比 API 版**慢**(每条有礼貌延迟、偶尔需手动过验证码),但 GS 对"标题→正确论文"的消歧覆盖面更广。基于 **nodriver**(CDP 直连,无需 ChromeDriver,不挑 Chrome 版本)。

```bash
pip install -r requirements.txt
playwright install chromium     # 下载隔离 Chromium(首次运行也会自动下)
python -m scholar_bibtex.scholar_browser <input.txt> [output.bib]
```

特点(对普通用户开箱即用):

- **不碰你自己的浏览器**:自动用 Playwright 的独立 Chromium(找不到会自动下载),与系统 Chrome/Helium 完全隔离。
- **验证码**:GS 按 IP/行为防爬,任何工具都绕不开。遇到时脚本暂停并**弹系统通知 + 响铃**,你在浏览器窗口手动完成后回终端按 Enter。cookie/会话持久化,**解一次后续大幅减少**(若窗口黑屏,点一下/拖动即可重绘)。
- **断点续传**:重跑同一命令,已成功的跳过。
- 输出每条带 `% Query` 注释,失败条目写入 `<output>.failed.txt`。

> 减少验证码的最有效办法是**别用已被标记的 IP / 数据中心 IP**(住宅 IP 最好)、放慢节奏、靠 cookie 养信任。脚本已内置随机延迟与会话持久化。

## 输入格式

每行一条,支持 DOI 或论文标题;`#` 开头为注释:

```
10.1038/s41586-023-06415-8
De novo design of protein structure and function with RFdiffusion
```

## License

MIT
