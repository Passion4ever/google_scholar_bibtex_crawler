# Google Scholar BibTeX Crawler

自动从 Google Scholar 提取 BibTeX 引用信息。

## 安装

```bash
pip install -r requirements.txt
```

## 使用

```bash
python get_google_scholar_bibtex.py <input.txt> [output.bib]
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
