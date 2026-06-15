# API 优先的批量 BibTeX 获取工具 — 设计文档

- 日期: 2026-06-13
- 分支: `feature/api-first-rewrite`
- 状态: 设计已确认,待写实现计划

## 1. 背景与目标

当前实现(`get_google_scholar_bibtex.py`)用 `undetected-chromedriver` 驱动浏览器爬 Google Scholar 拿 BibTeX。问题:

- **慢**:每条 5–10 秒人为延迟,几百条要数小时。
- **脆**:依赖 Scholar 的 HTML 选择器,会随页面改版失效。
- **要人工**:频繁触发验证码,需手动解。
- **不一致**:不同来源(Scholar vs Semantic Scholar)的 BibTeX 在作者姓名顺序、是否缩写等上不一致,而用户最信任的是**论文对应期刊/DOI 的权威 BibTeX**。

**目标**:重写为一个 API 优先的 Python 命令行批量工具,做到"又快、又准、又一致、又鲁棒":

- 快:用学术元数据 API 直连 + 异步并发,几百条几十秒级。
- 准:标题查询严格相似度验证,低置信匹配标记"存疑"而非静默采纳。
- 一致:统一以 **DOI 权威源**(出版商/Crossref 官方 BibTeX)为准,只有无 DOI 时才降级,且降级内容统一归一化。
- 鲁棒:多源优先级链 + 每源独立限流重试,Google Scholar 仅作最后兜底。

**非目标(v1)**:付费 API(SerpAPI/Scopus/WoS 等);从自由文本引用串解析(anystyle/refextract);GUI;PDF 下载。

## 2. 调研依据

两轮经对抗式验证(3 票)的深度调研结论,直接驱动本设计:

**数据源现状(截至 2026)**

- **DOI content negotiation**:对 `https://doi.org/{DOI}` 或 `https://api.crossref.org/works/{DOI}/transform/application/x-bibtex` 发 `Accept: application/x-bibtex` **直接返回权威 BibTeX**。两端点等价,**必须用 HTTPS**(http 会 406,是老教程常见坑)。每请求只返回一条,批量须逐条。
- **Crossref REST**:`/works?query.bibliographic={title}` 做标题检索;`mailto` 进礼貌池。无需 API key。限额(2025-12-01 新规):礼貌池单条 10 req/s、**3 并发**;列表查询 3 req/s、3 并发。公共池 5 req/s、1 并发。
- **OpenAlex**:覆盖广,100 req/s。**⚠️ 自 2026-02-13 起强制 API key**:无 key 仅 100 credits/天(真用会 409),免费 key 给 100k credits/天。**不原生产出 BibTeX**(仅 RIS/CSV/TXT)→ 仅用于标题→DOI 消歧。
- **Semantic Scholar**:原生 `citationStyles.bibtex`。但**即便有 key 也约 1 RPS**。key 可选但推荐。
- **DBLP**:`dblp.org/rec/{key}.bib` **原生返回 BibTeX**(CS/ML 会议神器);搜索走 `/search/publ/api?q=` 返回 XML/JSON,再按 key 取 `.bib`。无需 key,限额宽松。
- **Google Scholar 爬取**:主动封锁、验证码、需付费代理,**仅最后兜底**;无官方 API、批量不返回原生 BibTeX。

**可复用的成熟库(已验证活跃)**

- `RapidFuzz`(MIT,C++/Cython,v3.14):标题相似度匹配,**优于 thefuzz**。
- `bibtexparser`(v1.4.4 稳定 / v2 beta,2026-01):BibTeX 解析与归一化。
- `httpx`:异步 HTTP 客户端。
- `pyalex` / `habanero` / `danielnsilva/semanticscholar`:对应官方源的客户端 —— **借鉴,但 v1 走 httpx 直连以统一 async 与限流控制**。
- `betterbib`(活跃 CLI):同类先例(`doi-to`/`sync`/`convert`),借鉴不依赖(许可证标注 MIT/GPL 混乱)。
- `Zotero translation-server` / `manubot cite`:成熟的"标识符解析"方案,留作未来可选重型兜底,v1 不引入。

**结论:核心零件都有成熟库,我们只写"编排层",底层一律复用。** 付费 API v1 不碰(免费源 + Scholar 手动兜底已够;且本轮调研未能验证其定价/限流/合规,不据此决策)。

## 3. 架构:每条输入的处理管线

```
输入行
  │
  ▼
[classify] DOI?  (正则 ^10\.\d{4,}/\S+$,容忍 https://doi.org/ 前缀)
  │
  ├─ 是 DOI ──────────────► [authoritative fetch]
  │                          doi.org CN (HTTPS, Accept: application/x-bibtex)
  │                          失败 → Crossref transform 端点
  │                          confidence = exact-doi
  │
  └─ 是标题 ─► [disambiguate] 并发查多源,各返回候选(title + doi):
              Crossref query.bibliographic / OpenAlex / DBLP / Semantic Scholar
                       │
                       ▼
              [verify] RapidFuzz 归一化标题相似度,取最高分候选:
                 score ≥ HIGH(默认95) → 采纳
                 LOW ≤ score < HIGH    → 采纳但标记「存疑 REVIEW」
                 score < LOW(默认85)  → 视为未命中
                       │
                       ▼
              命中且有 DOI → 走 authoritative fetch(权威源)
              命中但无 DOI、源有原生 .bib(DBLP/S2)→ 直接用该 BibTeX
              全部未命中 → [Scholar 兜底](复用现有 Selenium)→ 标记 source=scholar, REVIEW
  │
  ▼
[normalize] bibtexparser:统一字段顺序、引用键风格、缩进
  │
  ▼
[output] 带溯源标注写出(见 §7)
```

**消除"不一致"的根治逻辑**:永远优先把记录锚定到 DOI,再取 DOI 权威 BibTeX;只有彻底无 DOI 时才用其他源的原生 BibTeX,且统一过归一化。Scholar 从主力降为极少数兜底,验证码几乎不再触发。

## 4. 数据源与优先级

每个源实现统一接口(见 §8 `sources/base.py`),返回候选列表或权威结果。

**DOI 输入** —— 取权威 BibTeX:
1. `doi.org` content negotiation(HTTPS)
2. 失败退 `api.crossref.org/works/{doi}/transform/application/x-bibtex`

**标题输入** —— 先消歧到 DOI(并发查下列源,合并候选),再取权威:
1. **Crossref** `query.bibliographic`(主力,覆盖广,直接给 DOI)
2. **OpenAlex**(覆盖广;需免费 key;给 DOI;未配 key 则自动跳过)
3. **DBLP**(CS/ML 命中率高;命中即可拿原生 `.bib`,也常带 DOI)
4. **Semantic Scholar**(原生 bibtex + DOI;~1 RPS,作补充)

候选合并后用 §5 的验证选定唯一结果。

**全部未命中** —— **Google Scholar 兜底**(复用现有 Selenium 代码),结果一律标 `REVIEW`。

## 5. 标题匹配与验证(RapidFuzz)

- **归一化**:小写、去标点、折叠空白、去除常见噪声(尾随句点等);可选去除副标题后缀做二次比对。
- **打分**:`rapidfuzz` `token_sort_ratio`(对词序不敏感)为主,辅以 `WRatio`;若候选带年份且与查询年份冲突则降级。
- **阈值(可配置,默认)**:
  - `HIGH = 95`:自动采纳。
  - `LOW = 85`:`LOW ≤ score < HIGH` 采纳但标 `REVIEW`;`score < LOW` 视为未命中。
- 多源候选取最高分;并列时优先**有 DOI**且来自更权威源(Crossref > OpenAlex > DBLP > S2)。
- 阈值默认偏严(宁可标存疑/失败,不要静默拿错)。最终阈值与 scorer 选择在实现期用真实样本回归校准。

## 6. 并发与限流

- 框架:`asyncio` + `httpx.AsyncClient`。
- **每源独立限流器**(信号量 + 最小请求间隔),按实测限额:
  - doi.org CN:≤5 并发(礼貌)
  - Crossref(礼貌池,带 `mailto`):单条 ≤3 并发/10 req/s;标题列表 ≤3 并发/3 req/s
  - OpenAlex:≤10 并发(远低于 100 req/s 上限,留余量;尊重 credits/天)
  - Semantic Scholar:≤1 并发、≤1 req/s
  - DBLP:≤3 并发
  - Scholar 兜底:单浏览器串行 + 现有随机延迟(只处理极少数漏网)
- 全局并发上限默认 ~8。
- **重试退避**:每请求超时 + 指数退避;遇 429 尊重 `Retry-After`;失败沿源链降级,绝不崩整批。
- 所有 API 请求带可配置 `mailto`(进 Crossref 礼貌池)与规范 `User-Agent`。

## 7. 输出格式与溯源

保持 `.bib` 兼容(注释行以 `%` 开头),每条带来源与置信标注:

```bibtex
% Query: 10.1038/s41586-023-06415-8
% Source: doi.org(crossref) | Confidence: exact-doi
@article{...}

% Query: Machine learning for functional protein design
% Source: crossref/query.bibliographic | Match: "Machine learning for functional protein design" score=99 | Confidence: high
@article{...}

% Query: some ambiguous title
% REVIEW: 匹配到 "a slightly different title" score=88 via openalex —— 请人工核对
@article{...}
```

- **失败条目**单独写 `<output>.failed.txt`(含原因:无候选/全部低于阈值/网络失败),便于人工补。
- `REVIEW` 条目同时在终端汇总末尾列出。

## 8. 模块结构

从单文件 330 行 → 小型包,每模块单一职责、可独立测试:

```
scholar_bibtex/
├── __init__.py
├── cli.py            # argparse 入口(兼容旧用法见 §11)
├── config.py         # key/mailto/阈值/并发,来自环境变量+命令行
├── models.py         # Candidate / Result 数据类(bibtex, doi, source, confidence, match_title, score)
├── classify.py       # DOI vs 标题 识别
├── pipeline.py       # async 编排:分类 → 消歧 → 验证 → 取权威 → 归一化(每条)
├── matching.py       # RapidFuzz 标题归一化 + 相似度 + 阈值判定
├── normalize.py      # bibtexparser 归一化
├── progress.py       # 断点续传/输出(移植现有"仅跳过成功项"逻辑)
├── ratelimit.py      # 每源 async 限流器(信号量 + 最小间隔 + 退避)
└── sources/
    ├── base.py            # Source 协议:async lookup(query, kind) -> list[Candidate] | Result
    ├── doi_negotiation.py # DOI → 权威 BibTeX
    ├── crossref.py        # 标题检索 + DOI 消歧
    ├── openalex.py        # 标题检索消歧(需 key,缺 key 跳过)
    ├── dblp.py            # 标题检索 + 原生 .bib
    ├── semantic_scholar.py# 标题检索 + 原生 bibtex
    └── scholar.py         # 复用现有 Selenium,降为最后兜底
```

## 9. 依赖

- 新增:`httpx`、`rapidfuzz`、`bibtexparser>=1.4,<2`(v2 仍 beta,稳定后再迁移)。
- 保留为**可选 extra**(仅 Scholar 兜底用):`undetected-chromedriver`、`selenium`。
- `requirements.txt` 拆分核心与可选;README 标注 OpenAlex/S2 key 为可选、Scholar 兜底需本机 Chrome。

## 10. 配置项

经环境变量与命令行参数(命令行优先):

- `CROSSREF_MAILTO`(进礼貌池;未设则用公共池,仅告警)
- `OPENALEX_API_KEY`(未设则跳过 OpenAlex 源)
- `SEMANTIC_SCHOLAR_API_KEY`(可选,提额)
- `--proxy`(沿用;给 Scholar 兜底 / 网络环境)
- `--high` / `--low`(相似度阈值覆盖)
- `--concurrency`、各源开关(`--no-openalex` 等)

## 11. 兼容与迁移

- 旧脚本 `get_google_scholar_bibtex.py` **保留在 `main`,不动**,确保随时可跑。
- 新包在本分支开发;提供入口 `python -m scholar_bibtex <input> [output] [opts]`,命令行参数尽量兼容旧用法(`input`/`output`/`--proxy`)。
- 现有 Selenium 抓取逻辑基本原样搬入 `sources/scholar.py`,作为最后兜底,而非删除。
- 现有 `.bib` 断点续传格式向后兼容(沿用 `% Query:` + 内容块解析)。

## 12. 错误处理

- 单条失败不影响整批:沿源链降级,最终写入 `failed.txt`。
- 网络/限流:每源超时 + 退避 + 尊重 429。
- 归一化失败:回退到原始 BibTeX 并告警,不丢数据。
- 断点续传:仅"取到 @ 内容"的条目算完成;失败条目下次重试(已在现有逻辑中修复)。

## 13. 测试策略

- 纯函数单元测试(无网络):`classify`、`matching`(阈值/边界)、`normalize`、`progress` 解析。
- 源适配器:用录制的 fixture(离线 JSON/BibTeX 样本)测解析与候选构建;真实联网测试标记为可选/network。
- 端到端:小样本输入跑通管线,断言溯源标注与 failed 输出。
- 遵循 TDD:先写失败测试再实现。

## 14. 风险与开放问题

- **OpenAlex 认证/计费**仍在演进(2026-02 起 key + credit 按量计费),实现期先探活再定行为;缺 key 自动跳过。
- **阈值校准**:HIGH/LOW 默认值需用真实样本回归微调。
- **Semantic Scholar ~1 RPS**:大批量时它会是瓶颈,故仅作补充源、可关闭。
- **DBLP 覆盖**偏 CS/ML;非该领域命中率低,属正常降级。
- **付费 API** 与 **scholarly 库当前可用性** 未在本轮充分验证;若未来需要大规模 Scholar 兜底,需专项调研(定价/限流/合规)。
