# Google Scholar BibTeX Crawler

批量把 DOI 或论文标题转成 BibTeX 引用信息。

## 安装

```bash
pip install -r requirements.txt
```

## 新版(API 优先,推荐)

更快、更准、更一致:DOI 走官方 content negotiation 取**权威 BibTeX**,标题先消歧到 DOI 再取权威,严格相似度验证并**标记存疑**,多源降级(Crossref / OpenAlex / DBLP / Semantic Scholar),Google Scholar 仅作最后兜底。

```bash
python -m scholar_bibtex <input.txt> [output.bib] [--proxy HOST:PORT]
```

可选环境变量:

- `CROSSREF_MAILTO`:进入 Crossref 礼貌池(更高速率),建议设置
- `OPENALEX_API_KEY`:启用 OpenAlex 源(2026-02 起必需;未设则自动跳过)
- `SEMANTIC_SCHOLAR_API_KEY`:可选,提升 Semantic Scholar 速率

输出每条带来源与置信标注;低置信匹配标 `% REVIEW` 需人工核对;失败条目写入 `<output>.failed.txt`。可选开关:`--no-openalex` / `--no-semantic-scholar` / `--no-dblp` / `--no-scholar`、`--high` / `--low`(相似度阈值)、`--concurrency`。

## 旧版(纯 Google Scholar 抓取)

仍保留,适合 API 查不到的少数论文:

```bash
python get_google_scholar_bibtex.py <input.txt> [output.bib] [--proxy HOST:PORT]
```

### 示例

```bash
# 基本使用
python get_google_scholar_bibtex.py papers.txt

# 使用代理
python get_google_scholar_bibtex.py papers.txt --proxy 127.0.0.1:7890
```

### 输入格式

每行一条，支持 DOI 或论文标题：

```
10.1038/s41586-023-06415-8
De novo design of protein structure and function with RFdiffusion
```

## 说明

- 遇到验证码时手动完成，按 Enter 继续
- 支持断点续传
- 可最小化窗口运行

## License

MIT
