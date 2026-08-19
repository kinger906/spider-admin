import { createAsync, useParams, A, action, useAction } from "@solidjs/router";
import { Show, Suspense, For } from "solid-js";
import { getCrawler, getTasks, triggerCrawler, pauseCrawler, stopCrawler } from "~/lib/api";
import Card from "~/components/Card";
import StatusBadge from "~/components/StatusBadge";

export default function CrawlerDetail() {
  const params = useParams<{ id: string }>();
  const id = () => Number(params.id);
  const crawler = createAsync(() => getCrawler(id()));
  const taskList = createAsync(() => getTasks(id()));

  async function handleTrigger() {
    await triggerCrawler(id());
  }
  async function handlePause() {
    await pauseCrawler(id());
  }
  async function handleStop() {
    await stopCrawler(id());
  }

  return (
    <div class="p-6 space-y-6">
      <A href="/crawlers" class="text-sm text-gray-500 hover:text-gray-300">← 返回爬虫列表</A>

      <Suspense fallback={<p class="text-gray-500">加载中...</p>}>
        <Show when={crawler()}>
          {(c) => (
            <>
              <div class="flex items-center gap-4">
                <h2 class="text-2xl font-bold">{c().name}</h2>
                <StatusBadge status={c().status} />
              </div>

              <p class="text-gray-400">{c().description}</p>

              <div class="flex gap-3">
                <button onClick={handleTrigger} class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm font-medium transition-colors">
                  触发运行
                </button>
                <button onClick={handlePause} class="px-4 py-2 bg-amber-600/20 text-amber-400 hover:bg-amber-600/30 rounded-lg text-sm font-medium transition-colors">
                  暂停
                </button>
                <button onClick={handleStop} class="px-4 py-2 bg-red-600/20 text-red-400 hover:bg-red-600/30 rounded-lg text-sm font-medium transition-colors">
                  停止
                </button>
              </div>

              <Card title="配置信息">
                <dl class="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <dt class="text-gray-500">文件路径</dt>
                    <dd class="text-gray-200 font-mono text-xs mt-1">{c().filePath}</dd>
                  </div>
                  <div>
                    <dt class="text-gray-500">调度规则</dt>
                    <dd class="text-gray-200 mt-1">{c().schedule || "手动触发"}</dd>
                  </div>
                  <div>
                    <dt class="text-gray-500">重试次数</dt>
                    <dd class="text-gray-200 mt-1">{c().retryLimit}</dd>
                  </div>
                  <div>
                    <dt class="text-gray-500">最后运行</dt>
                    <dd class="text-gray-200 mt-1">{c().lastRunAt ? new Date(c().lastRunAt).toLocaleString("zh-CN") : "从未"}</dd>
                  </div>
                </dl>
              </Card>

              <Card title="任务历史">
                <Show when={taskList()} fallback={<p class="text-gray-500">暂无任务</p>}>
                  {(tl) => (
                    <table class="w-full text-sm">
                      <thead>
                        <tr class="text-left text-gray-500 text-xs uppercase tracking-wider">
                          <th class="pb-3">ID</th>
                          <th class="pb-3">状态</th>
                          <th class="pb-3">数据量</th>
                          <th class="pb-3">重试</th>
                          <th class="pb-3">触发</th>
                          <th class="pb-3">时间</th>
                        </tr>
                      </thead>
                      <tbody class="divide-y divide-gray-800">
                        <For each={tl().data}>
                          {(task) => (
                            <tr class="hover:bg-gray-800/50">
                              <td class="py-2.5 text-gray-400">#{task.id}</td>
                              <td class="py-2.5"><StatusBadge status={task.status} /></td>
                              <td class="py-2.5 text-gray-400">{task.itemsCount}</td>
                              <td class="py-2.5 text-gray-400">{task.retryCount}</td>
                              <td class="py-2.5 text-gray-500">{task.triggeredBy}</td>
                              <td class="py-2.5 text-gray-500">{new Date(task.createdAt).toLocaleString("zh-CN")}</td>
                            </tr>
                          )}
                        </For>
                      </tbody>
                    </table>
                  )}
                </Show>
              </Card>
            </>
          )}
        </Show>
      </Suspense>
    </div>
  );
}
