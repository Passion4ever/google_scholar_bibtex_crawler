# Google Scholar BibTeX Crawler

用浏览器自动从 Google Scholar 抓取论文的 BibTeX。基于 **nodriver**(CDP 直连,无需 ChromeDriver,不挑 Chrome 版本),输出经统一归一化(引用键 `lastnameYYYYword`、作者统一"姓, 名"顺序)。

> API 优先的版本(Crossref / OpenAlex / DBLP / Semantic Scholar,无需浏览器、零验证码)在 `dev-api` 分支开发中。

## 安装

```bash
pip install -r requirements.txt
playwright install chromium     # 下载隔离 Chromium(首次运行也会自动下)
```

## 使用

```bash
python -m scholar_bibtex.scholar_browser <input.txt> [output.bib]
```

输入文件每行一条 DOI 或论文标题,`#` 开头为注释:

```
10.1038/s41586-023-06415-8
De novo design of protein structure and function with RFdiffusion
```

## 特点

- **不碰你自己的浏览器**:自动用 Playwright 的独立 Chromium(找不到会自动下载),与系统 Chrome/其它浏览器完全隔离。
- **不挑 Chrome 版本**:nodriver 走 CDP,没有 ChromeDriver 版本匹配问题。
- **验证码**:Google Scholar 按 IP/行为防爬,任何工具都绕不开。遇到时脚本暂停并**响铃 + 系统通知**,你在浏览器窗口手动完成后回终端按 Enter。cookie/会话持久化,**解一次后续大幅减少**(若窗口黑屏,点一下/拖动即可重绘)。
- **断点续传**:重跑同一命令,已成功的跳过;失败条目写入 `<output>.failed.txt`。
- **统一输出**:引用键与作者姓名顺序归一化,跨条目一致。
- **跨平台**:macOS / Windows / Linux。

> 减少验证码最有效的办法是**别用已被标记/数据中心 IP**(住宅 IP 最好)、放慢节奏、靠 cookie 养信任。脚本已内置随机延迟与会话持久化。

## License

MIT
