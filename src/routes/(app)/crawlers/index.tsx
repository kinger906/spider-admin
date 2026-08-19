import { createAsync, A } from "@solidjs/router";
import { For, Suspense } from "solid-js";
import { getCrawlers, updateCrawler } from "~/lib/api";
import Card from "~/components/Card";
import StatusBadge from "~/components/StatusBadge";

export const route = { preload: () => getCrawlers() };

export default function CrawlersPage() {
  const crawlerList = createAsync(() => getCrawlers());

  async function toggleEnabled(id: number, current: boolean) {
    await updateCrawler(id, { enabled: !current });
  }

  return (
    <div class="p-6 space-y-6">
      <div class="flex items-center justify-between">
        <h2 class="text-2xl font-bold">爬虫管理</h2>
        <span class="text-sm text-gray-500">爬虫通过 Python 注册自动发现</span>
      </div>

      <Suspense fallback={<p class="text-gray-500">加载中...</p>}>
        <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          <For each={crawlerList()}>
            {(crawler) => (
              <Card>
                <div class="flex items-start justify-between mb-3">
                  <div>
                    <A href={`/crawlers/${crawler.id}`} class="text-lg font-semibold hover:text-indigo-400 transition-colors">
                      {crawler.name}
                    </A>
                    <p class="text-xs text-gray-500 mt-0.5">{crawler.slug}</p>
                  </div>
                  <StatusBadge status={crawler.status} />
                </div>
                <p class="text-sm text-gray-400 mb-4 line-clamp-2">{crawler.description || "暂无描述"}</p>
                <div class="flex items-center justify-between text-xs text-gray-500">
                  <span>调度: {crawler.schedule || "手动"}</span>
                  <span>重试: {crawler.retryLimit}次</span>
                </div>
                <div class="flex items-center justify-between mt-4 pt-3 border-t border-gray-800">
                  <span class="text-xs text-gray-600">
                    最后运行: {crawler.lastRunAt ? new Date(crawler.lastRunAt).toLocaleString("zh-CN") : "从未"}
                  </span>
                  <button
                    onClick={() => toggleEnabled(crawler.id, crawler.enabled)}
                    class={`text-xs px-3 py-1 rounded-md transition-colors ${
                      crawler.enabled
                        ? "bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20"
                        : "bg-gray-800 text-gray-500 hover:bg-gray-700"
                    }`}
                  >
                    {crawler.enabled ? "已启用" : "已禁用"}
                  </button>
                </div>
              </Card>
            )}
          </For>
        </div>
      </Suspense>
    </div>
  );
}
