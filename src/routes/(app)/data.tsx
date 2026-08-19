import { createAsync } from "@solidjs/router";
import { For, Suspense, createSignal, Show } from "solid-js";
import { getDataRecords, getCrawlers } from "~/lib/api";
import Card from "~/components/Card";

export default function DataPage() {
  const [crawlerId, setCrawlerId] = createSignal<number | undefined>();
  const [search, setSearch] = createSignal("");
  const [page, setPage] = createSignal(1);

  const crawlerList = createAsync(() => getCrawlers());
  const records = createAsync(() => getDataRecords(crawlerId(), search(), page()));

  function exportJson() {
    const data = records()?.data;
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `spider-data-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function exportCsv() {
    const data = records()?.data;
    if (!data?.length) return;
    const flatData = data.map((r) => ({ id: r.id, crawlerId: r.crawlerId, url: r.url, ...((r.data as Record<string, unknown>) ?? {}) }));
    const headers = Object.keys(flatData[0]);
    const csv = [headers.join(","), ...flatData.map((row) => headers.map((h) => JSON.stringify((row as any)[h] ?? "")).join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `spider-data-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div class="p-6 space-y-6">
      <div class="flex items-center justify-between">
        <h2 class="text-2xl font-bold">数据查询</h2>
        <div class="flex gap-2">
          <button onClick={exportJson} class="px-3 py-1.5 text-sm rounded-lg bg-gray-800 text-gray-300 hover:bg-gray-700">导出 JSON</button>
          <button onClick={exportCsv} class="px-3 py-1.5 text-sm rounded-lg bg-gray-800 text-gray-300 hover:bg-gray-700">导出 CSV</button>
        </div>
      </div>

      <div class="flex gap-4">
        <select
          onChange={(e) => { setCrawlerId(e.target.value ? Number(e.target.value) : undefined); setPage(1); }}
          class="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300 focus:border-indigo-500 focus:outline-none"
        >
          <option value="">全部爬虫</option>
          <For each={crawlerList()}>
            {(c) => <option value={c.id}>{c.name}</option>}
          </For>
        </select>
        <input
          type="text"
          placeholder="搜索数据内容..."
          value={search()}
          onInput={(e) => { setSearch(e.target.value); setPage(1); }}
          class="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300 placeholder:text-gray-600 focus:border-indigo-500 focus:outline-none"
        />
      </div>

      <Suspense fallback={<p class="text-gray-500">加载中...</p>}>
        <Card>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="text-left text-gray-500 text-xs uppercase tracking-wider">
                  <th class="pb-3">ID</th>
                  <th class="pb-3">爬虫</th>
                  <th class="pb-3">URL</th>
                  <th class="pb-3">数据</th>
                  <th class="pb-3">时间</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-800">
                <For each={records()?.data}>
                  {(record) => (
                    <tr class="hover:bg-gray-800/50">
                      <td class="py-2.5 text-gray-400">#{record.id}</td>
                      <td class="py-2.5">{record.crawlerId}</td>
                      <td class="py-2.5 text-indigo-400 max-w-[200px] truncate">
                        <Show when={record.url} fallback="-">
                          <a href={record.url!} target="_blank" class="hover:underline">{record.url}</a>
                        </Show>
                      </td>
                      <td class="py-2.5 text-gray-400 max-w-[400px]">
                        <pre class="text-xs whitespace-pre-wrap break-all">{JSON.stringify(record.data, null, 1)}</pre>
                      </td>
                      <td class="py-2.5 text-gray-500 whitespace-nowrap">{new Date(record.createdAt).toLocaleString("zh-CN")}</td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
          </div>

          <div class="flex items-center justify-between mt-4 pt-4 border-t border-gray-800">
            <span class="text-sm text-gray-500">共 {records()?.total ?? 0} 条</span>
            <div class="flex gap-2">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page() === 1} class="px-3 py-1 text-sm rounded-md bg-gray-800 text-gray-400 hover:bg-gray-700 disabled:opacity-40">上一页</button>
              <button onClick={() => setPage((p) => p + 1)} class="px-3 py-1 text-sm rounded-md bg-gray-800 text-gray-400 hover:bg-gray-700">下一页</button>
            </div>
          </div>
        </Card>
      </Suspense>
    </div>
  );
}
