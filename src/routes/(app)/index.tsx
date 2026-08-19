import { createAsync } from "@solidjs/router";
import { For, Show, Suspense } from "solid-js";
import { getDashboardStats } from "~/lib/api";
import Card from "~/components/Card";
import StatusBadge from "~/components/StatusBadge";

export const route = { preload: () => getDashboardStats() };

export default function Dashboard() {
  const stats = createAsync(() => getDashboardStats());

  return (
    <div class="p-6 space-y-6">
      <h2 class="text-2xl font-bold">仪表盘</h2>

      <Suspense fallback={<p class="text-gray-500">加载中...</p>}>
        <Show when={stats()}>
          {(s) => (
            <>
              <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard label="爬虫总数" value={s().crawlers?.total ?? 0} accent="indigo" />
                <StatCard label="运行中" value={s().crawlers?.running ?? 0} accent="emerald" />
                <StatCard label="任务成功" value={s().tasks?.success ?? 0} accent="sky" />
                <StatCard label="数据记录" value={s().records?.total ?? 0} accent="violet" />
              </div>

              <Card title="最近任务">
                <div class="overflow-x-auto">
                  <table class="w-full text-sm">
                    <thead>
                      <tr class="text-left text-gray-500 text-xs uppercase tracking-wider">
                        <th class="pb-3">ID</th>
                        <th class="pb-3">爬虫</th>
                        <th class="pb-3">状态</th>
                        <th class="pb-3">数据量</th>
                        <th class="pb-3">触发方式</th>
                        <th class="pb-3">创建时间</th>
                      </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-800">
                      <For each={s().recentTasks}>
                        {(task) => (
                          <tr class="hover:bg-gray-800/50">
                            <td class="py-2.5 text-gray-400">#{task.id}</td>
                            <td class="py-2.5">{task.crawlerId}</td>
                            <td class="py-2.5"><StatusBadge status={task.status} /></td>
                            <td class="py-2.5 text-gray-400">{task.itemsCount}</td>
                            <td class="py-2.5 text-gray-500">{task.triggeredBy}</td>
                            <td class="py-2.5 text-gray-500">{new Date(task.createdAt).toLocaleString("zh-CN")}</td>
                          </tr>
                        )}
                      </For>
                    </tbody>
                  </table>
                </div>
              </Card>
            </>
          )}
        </Show>
      </Suspense>
    </div>
  );
}

function StatCard(props: { label: string; value: number; accent: string }) {
  const accentMap: Record<string, string> = {
    indigo: "text-indigo-400",
    emerald: "text-emerald-400",
    sky: "text-sky-400",
    violet: "text-violet-400",
  };
  return (
    <div class="rounded-xl border border-gray-800 bg-gray-900 p-5">
      <p class="text-xs text-gray-500 uppercase tracking-wider">{props.label}</p>
      <p class={`text-3xl font-bold mt-2 ${accentMap[props.accent] ?? "text-gray-100"}`}>
        {props.value.toLocaleString()}
      </p>
    </div>
  );
}
