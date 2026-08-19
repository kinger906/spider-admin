import { createAsync } from "@solidjs/router";
import { For, Suspense, createSignal } from "solid-js";
import { getTasks } from "~/lib/api";
import Card from "~/components/Card";
import StatusBadge from "~/components/StatusBadge";

export default function TasksPage() {
  const [page, setPage] = createSignal(1);
  const taskList = createAsync(() => getTasks(undefined, page()));

  return (
    <div class="p-6 space-y-6">
      <h2 class="text-2xl font-bold">任务监控</h2>

      <Suspense fallback={<p class="text-gray-500">加载中...</p>}>
        <Card>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="text-left text-gray-500 text-xs uppercase tracking-wider">
                  <th class="pb-3">ID</th>
                  <th class="pb-3">爬虫ID</th>
                  <th class="pb-3">状态</th>
                  <th class="pb-3">数据量</th>
                  <th class="pb-3">重试</th>
                  <th class="pb-3">触发方式</th>
                  <th class="pb-3">开始时间</th>
                  <th class="pb-3">结束时间</th>
                  <th class="pb-3">错误</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-800">
                <For each={taskList()?.data}>
                  {(task) => (
                    <tr class="hover:bg-gray-800/50">
                      <td class="py-2.5 text-gray-400">#{task.id}</td>
                      <td class="py-2.5">{task.crawlerId}</td>
                      <td class="py-2.5"><StatusBadge status={task.status} /></td>
                      <td class="py-2.5 text-gray-400">{task.itemsCount}</td>
                      <td class="py-2.5 text-gray-400">{task.retryCount}</td>
                      <td class="py-2.5 text-gray-500">{task.triggeredBy}</td>
                      <td class="py-2.5 text-gray-500">{task.startedAt ? new Date(task.startedAt).toLocaleString("zh-CN") : "-"}</td>
                      <td class="py-2.5 text-gray-500">{task.finishedAt ? new Date(task.finishedAt).toLocaleString("zh-CN") : "-"}</td>
                      <td class="py-2.5 text-red-400 max-w-[200px] truncate">{task.errorMessage || "-"}</td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
          </div>

          <div class="flex items-center justify-between mt-4 pt-4 border-t border-gray-800">
            <span class="text-sm text-gray-500">共 {taskList()?.total ?? 0} 条</span>
            <div class="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page() === 1}
                class="px-3 py-1 text-sm rounded-md bg-gray-800 text-gray-400 hover:bg-gray-700 disabled:opacity-40"
              >
                上一页
              </button>
              <button
                onClick={() => setPage((p) => p + 1)}
                class="px-3 py-1 text-sm rounded-md bg-gray-800 text-gray-400 hover:bg-gray-700"
              >
                下一页
              </button>
            </div>
          </div>
        </Card>
      </Suspense>
    </div>
  );
}
