import { createAsync } from "@solidjs/router";
import { For, Suspense, createSignal } from "solid-js";
import { getSystemLogs } from "~/lib/api";
import Card from "~/components/Card";

const levelColors: Record<string, string> = {
  info: "text-sky-400",
  warn: "text-amber-400",
  error: "text-red-400",
  debug: "text-gray-500",
};

export default function LogsPage() {
  const [level, setLevel] = createSignal<string | undefined>();
  const [page, setPage] = createSignal(1);
  const logs = createAsync(() => getSystemLogs(level(), undefined, page()));

  return (
    <div class="p-6 space-y-6">
      <h2 class="text-2xl font-bold">系统日志</h2>

      <div class="flex gap-2">
        {["全部", "info", "warn", "error"].map((l) => (
          <button
            onClick={() => { setLevel(l === "全部" ? undefined : l); setPage(1); }}
            class={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
              (l === "全部" && !level()) || l === level()
                ? "bg-indigo-600 text-white"
                : "bg-gray-800 text-gray-400 hover:bg-gray-700"
            }`}
          >
            {l}
          </button>
        ))}
      </div>

      <Suspense fallback={<p class="text-gray-500">加载中...</p>}>
        <Card>
          <div class="space-y-2 max-h-[70vh] overflow-y-auto font-mono text-xs">
            <For each={logs()}>
              {(log) => (
                <div class="flex gap-3 py-1.5 border-b border-gray-800/50">
                  <span class="text-gray-600 whitespace-nowrap">{new Date(log.createdAt).toLocaleString("zh-CN")}</span>
                  <span class={`uppercase w-12 shrink-0 ${levelColors[log.level] ?? "text-gray-400"}`}>{log.level}</span>
                  <span class="text-gray-500 w-32 shrink-0 truncate">{log.source}</span>
                  <span class="text-gray-300 flex-1">{log.message}</span>
                </div>
              )}
            </For>
          </div>

          <div class="flex justify-end mt-4 pt-4 border-t border-gray-800 gap-2">
            <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page() === 1} class="px-3 py-1 text-sm rounded-md bg-gray-800 text-gray-400 hover:bg-gray-700 disabled:opacity-40">上一页</button>
            <button onClick={() => setPage((p) => p + 1)} class="px-3 py-1 text-sm rounded-md bg-gray-800 text-gray-400 hover:bg-gray-700">下一页</button>
          </div>
        </Card>
      </Suspense>
    </div>
  );
}
