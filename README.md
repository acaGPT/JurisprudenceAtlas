# JurisprudenceAtlas

《法理学》课程地图 —— 把课程大纲从一篇长文还原为一张可检索、可筛选的索引页。

- **站点地址**：<https://acagpt.github.io/JurisprudenceAtlas/>
- **数据来源**：<https://github.com/acaGPT/Jurisprudence.wiki>
- **当前版本**：v0.1.1

## 这个站点做什么

课程大纲是一份九百余行、九单元四十六章的长文档。它适合通读，不适合查找：
想知道「第四单元有哪几章」「哪几章已经有了课前概览」「哪一章讨论哈特与富勒之争」，
都只能在长文里翻。

本站把大纲解析为结构化数据，提供三件事：

1. **单元分组浏览**——九个单元各自成区，章卡并列，可一屏看尽一个单元；
2. **跨字段检索**——在章号、中英题名、中英梗概五个字段上做即时过滤；
3. **撰写进度可视**——每章标注课前概览是「已有」还是「待撰写」，并可据此筛选。

## 内容边界

本站**不复制正文**。章节梗概、文献数目、课前概览链接均取自大纲原文，
阅读入口一律指向课程 Wiki。正文与文献的增删改，只在 Wiki 一处发生；
本站的数据层由脚本从 Wiki 重新生成，不手工维护第二份内容。

`index.html` 页脚与 `LICENSE` 载明本站的版权条款。

## 目录结构

```
.
├── tools/
│   └── extract-syllabus.py     # 从 Wiki 大纲抽取数据层
├── site/                       # 站点源（发布到 gh-pages 分支）
│   ├── index.html              # 课程地图
│   ├── 404.html                # 容错页（自包含，根路径运行时推导）
│   ├── .nojekyll
│   └── assets/
│       ├── css/site.css
│       ├── js/app.js
│       ├── data/syllabus.json   # 生成物
│       ├── data/meta.json       # 生成物
│       └── favicon.svg
└── README.md
```

## 重建数据层

数据层由 Wiki 克隆生成。先取得大纲，再抽取：

```bash
git clone https://github.com/acaGPT/Jurisprudence.wiki.git

python3 tools/extract-syllabus.py \
  --wiki Jurisprudence.wiki \
  --out site/assets/data \
  --auto
```

输出 `syllabus.json`（单元、章节、文献计数、课前概览链接）与 `meta.json`
（生成时间、源 commit、汇总统计）。控制的输出样例：

```
单元 9 · 章节 47 · 经典文献 235 · 延伸阅读 132 · 已有课前概览 10
```

Wiki 更新后重跑该命令即可，站点无需改动。

## 发布

站点为纯静态页，无构建步骤、无第三方依赖。

```bash
python3 ~/.workbuddy/skills/gh-pages-maker/scripts/new_pages_site.py \
  --name JurisprudenceAtlas \
  --source site \
  --description "《法理学》课程地图：九单元四十七章的可检索索引，直达课程 Wiki" \
  --org acaGPT --copyright iLINGBIN --branch gh-pages --auto
```

本地预览：

```bash
python3 -m http.server 8899 --directory site
```

## 分支

| 分支 | 内容 |
|---|---|
| `main` | 站点源、抽取脚本、说明文档 |
| `gh-pages` | 发布产物（站点源 + `LICENSE` + 站点 `README`），Pages 由此分支根目录发布 |

## 已知事项

- 大纲中的章节标题带章号前缀，抽取时已剥离，章号由卡片徽章单独呈现。
- 大纲中的章节按「中文题名 + 英文题名」两行成对书写，抽取器据此配对合并。
  两章题名若紧邻（PVI.1.a 与 PVI.1.b），块终点须越过本章两行再取下一个异章
  标题，否则会把文献与课前概览小节整段丢给下一章——改动大纲结构后建议重跑
  抽取器，核对各章 `refs_count` 与 `preclass_list` 是否归位。
- `PVI.1.b. Global Debates on Legal Formalism vs Legal Realism` 此前只挂在大纲
  PVI.1.a 的课前概览小节里、且未进 Wiki 首页，已于 v0.1.1 在 Wiki 侧补登本章的
  中英题名、把概览链接归位，并补齐首页导航。

## 版权

Copyright (c) 2026 iLINGBIN. 保留所有权利（All Rights Reserved）。

本站及其所索引的课程内容，未获书面许可，不得以复制、改写、汇编、翻译、上传网络、
制作衍生讲义、商业性使用等方式利用。课堂内为教学目的之讲授、投影、复印，
属许可范围内之使用；公开出版、网络公开发布、商业培训或二次改编须先行取得书面同意。
详见 [LICENSE](LICENSE)。
