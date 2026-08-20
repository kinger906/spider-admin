# Spider Admin - 爬虫管理系统

集中管理多个 Python 爬虫项目及其爬取数据的全栈系统。

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | SolidStart + SolidJS + TypeScript + TailwindCSS v4 |
| 构建 | Vite (via Vinxi) |
| 部署 | Vercel |
| 数据库 | Neon Postgres + Drizzle ORM |
| 文件存储 | Vercel Blob |
| 爬虫 | Python 3.12 + requests + BeautifulSoup |
| CI/CD | GitHub Actions |
| 包管理 | pnpm (前端) / pip (爬虫) |

## 项目结构

```
spider/
├── src/                     # SolidStart 前端 + API
│   ├── components/          # UI 组件
│   ├── db/                  # 数据库 schema & 连接
│   ├── lib/                 # 服务端函数 (API 层)
│   └── routes/              # 页面路由 & REST API
├── crawlers/                # Python 爬虫模块
│   ├── framework/           # 爬虫基础框架
│   │   ├── base.py          # BaseCrawler 抽象类
│   │   ├── registry.py      # 自动发现 & 注册
│   │   ├── runner.py        # 带重试的任务执行器
│   │   └── db.py            # 数据库操作
│   ├── spiders/             # 各爬虫实现 (一个文件一个爬虫)
│   │   ├── hackernews.py
│   │   └── github_trending.py
│   └── run.py               # CLI 入口
└── .github/workflows/       # GitHub Actions
    ├── crawl.yml             # 定时爬取调度
    └── deploy.yml            # 前端 CI/CD
```

## 快速开始

### 1. 环境变量

复制 `.env.example` 为 `.env` 并填写：

```bash
DATABASE_URL=postgresql://...@ep-xxx.neon.tech/spider?sslmode=require
BLOB_READ_WRITE_TOKEN=vercel_blob_xxx
API_SECRET=your-secret
```

### 2. 安装依赖

```bash
pnpm install                           # 前端
pip install -r crawlers/requirements.txt  # 爬虫
```

### 3. 初始化数据库

```bash
pnpm db:push
```

### 4. 启动开发

```bash
pnpm dev
```

### 5. 运行爬虫

```bash
cd crawlers
python run.py --list              # 列出所有爬虫
python run.py --sync              # 同步注册到数据库
python run.py hackernews          # 运行指定爬虫
python run.py github-trending     # 运行 GitHub Trending 爬虫
```

## 编写新爬虫

在 `crawlers/spiders/` 下新建 Python 文件：

```python
from framework import BaseCrawler, CrawlerRegistry
from framework.base import CrawlerMeta

class MyCrawler(BaseCrawler):
    meta = CrawlerMeta(
        name="My Crawler",
        slug="my-crawler",
        description="描述",
        schedule="0 */12 * * *",  # cron 表达式
    )

    def crawl(self) -> list[dict]:
        # 实现爬取逻辑
        return [{"data": {...}, "url": "..."}]

CrawlerRegistry.register(MyCrawler)
```

然后在 `.github/workflows/crawl.yml` 的 matrix 中添加 slug 即可。

## 管理端功能

- **仪表盘**: 爬虫总数、运行状态、数据统计、最近任务
- **爬虫管理**: 列表/详情、启用/禁用、触发/暂停/停止
- **任务监控**: 全部任务状态、重试次数、执行日志
- **数据查询**: 按爬虫筛选、关键词搜索、JSON/CSV 导出
- **系统日志**: 按级别过滤的日志查看器
- **系统设置**: 配置概览

## GitHub Actions

- `crawl.yml`: 定时调度爬虫 (支持 cron + 手动触发)
- `deploy.yml`: 推送 `master` 时构建，并把 Secrets 同步到 Vercel Production，再 `--prebuilt` 部署

## GitHub Secrets 配置

在仓库 **Settings → Secrets and variables → Actions** 中添加：

| Secret | 说明 |
|--------|------|
| `DATABASE_URL` | Neon Postgres 连接字符串（必填，CI 会同步到 Vercel） |
| `API_SECRET` | 会话密钥，**至少 32 个字符**（必填，CI 会同步到 Vercel） |
| `BLOB_READ_WRITE_TOKEN` | Vercel Blob Token（可选） |
| `VERCEL_TOKEN` | Vercel 部署 Token |
| `VERCEL_ORG_ID` | Vercel 组织 ID |
| `VERCEL_PROJECT_ID` | Vercel 项目 ID |

`API_SECRET` 示例：`spider-secret-key-min-32-chars!!`

部署后可访问 `/api/health` 检查环境变量是否生效：
- `hasDatabaseUrl: true`
- `hasApiSecret: true`
