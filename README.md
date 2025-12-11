# Google Scholar BibTeX Crawler

一个自动从 Google Scholar 提取 BibTeX 引用信息的 Python 爬虫工具。

## 特性

- 自动从 Google Scholar 搜索论文并提取 BibTeX
- 使用 `undetected-chromedriver` 绑过反爬检测，减少验证码
- 随机延迟模拟人类行为
- Cookie 持久化，复用登录状态
- 断点续传，中断后可继续
- 支持 DOI、论文标题等多种输入格式

## 安装

### 1. 克隆仓库

```bash
git clone https://github.com/your-username/Google_scholar_bibtex_crawler.git
cd Google_scholar_bibtex_crawler
```

### 2. 创建虚拟环境（推荐）

```bash
conda create -n bib python=3.10
conda activate bib
```

### 3. 安装依赖

```bash
pip install undetected-chromedriver selenium
```

### 4. 确保已安装 Chrome 浏览器

程序会自动下载匹配的 ChromeDriver，无需手动配置。

## 使用方法

```bash
python get_google_scholar_bibtex.py <input.txt> [output.bib]
```

### 参数说明

| 参数 | 说明 |
|------|------|
| `input.txt` | **必需**，输入文件，每行一条论文信息 |
| `output.bib` | 可选，输出文件，默认为 `input.bib` |

### 示例

```bash
# 输入 papers.txt，自动输出到 papers.bib
python get_google_scholar_bibtex.py papers.txt

# 指定输出文件名
python get_google_scholar_bibtex.py papers.txt references.bib
```

### 输入文件格式

每行一条记录，支持以下格式：

```
# DOI（推荐，最精确）
10.1038/s41586-023-06415-8

# 纯标题
De novo design of protein structure and function with RFdiffusion

# 完整引用（会自动提取标题）
Watson, J.L., et al. De novo design of protein structure and function with RFdiffusion. Nature 620, 1089–1100 (2023).
```

### 输出示例

```bibtex
@article{watson2023novo,
  title={De novo design of protein structure and function with RFdiffusion},
  author={Watson, Joseph L and Juergens, David and Bennett, Nathaniel R and others},
  journal={Nature},
  volume={620},
  number={7976},
  pages={1089--1100},
  year={2023},
  publisher={Nature Publishing Group UK London}
}
```

## 注意事项

1. **验证码处理**：如果遇到 Google 验证码，程序会暂停并提示，手动完成验证后按 Enter 继续
2. **请求频率**：程序默认每次请求间隔 5-10 秒，避免触发反爬
3. **Cookie 缓存**：首次运行后会保存 Cookie 到 `.google_scholar_cookies.pkl`，后续运行会自动加载
4. **断点续传**：如果程序中断，重新运行会跳过已处理的记录

## 文件说明

```
.
├── get_google_scholar_bibtex.py  # 主程序
├── examples/
│   ├── example.txt               # 输入示例
│   └── example.bib               # 输出示例
├── .google_scholar_cookies.pkl   # Cookie 缓存（自动生成，已忽略）
└── README.md
```

## 常见问题

### Q: 为什么会出现验证码？

Google Scholar 会对频繁请求进行限制。本工具已通过以下方式尽量减少验证码：
- 使用 `undetected-chromedriver` 绕过自动化检测
- 随机延迟模拟人类行为
- Cookie 持久化复用会话

如果仍然出现验证码，手动完成一次后通常可以继续运行。

### Q: 程序中断了怎么办？

直接重新运行即可，程序会自动跳过已处理的记录（断点续传）。

### Q: 如何提高搜索准确率？

- **最佳**：使用 DOI（如 `10.1038/s41586-023-06415-8`）
- **推荐**：使用纯标题（不带作者、期刊信息）
- **避免**：使用完整引用格式（可能干扰搜索）

## License

MIT License
