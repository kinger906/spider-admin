import { createAsync } from "@solidjs/router";
import { For, Suspense, createSignal, Show, createMemo } from "solid-js";
import { getDataRecords, getCrawlers } from "~/lib/api";
import { formatBeijing } from "~/lib/datetime";
import Card from "~/components/Card";

type RecordPayload = {
  title?: string;
  forum_name?: string;
  published_at?: string;
  download_links?: string[];
  post_id?: string;
  thread_id?: string;
  [key: string]: unknown;
};

async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* fall through */
  }
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

function shortLink(link: string): string {
  if (link.startsWith("magnet:?xt=urn:btih:")) {
    const hash = link.slice("magnet:?xt=urn:btih:".length).split("&")[0] ?? "";
    return hash ? `magnet …${hash.slice(-8)}` : "magnet";
  }
  if (link.length <= 48) return link;
  return `${link.slice(0, 28)}…${link.slice(-12)}`;
}

function payloadOf(record: { data: unknown }): RecordPayload {
  const d = record.data;
  return d && typeof d === "object" ? (d as RecordPayload) : {};
}

function linksOf(record: { data: unknown }): string[] {
  const links = payloadOf(record).download_links;
  return Array.isArray(links) ? links.map(String).filter(Boolean) : [];
}

export default function DataPage() {
  const [crawlerId, setCrawlerId] = createSignal<number | undefined>();
  const [search, setSearch] = createSignal("");
  const [page, setPage] = createSignal(1);
  const [copiedKey, setCopiedKey] = createSignal("");

  const crawlerList = createAsync(() => getCrawlers());
  const records = createAsync(() => getDataRecords(crawlerId(), search(), page()));

  const crawlerName = createMemo(() => {
    const map = new Map((crawlerList() ?? []).map((c) => [c.id, c.name]));
    return (id: number) => map.get(id) ?? String(id);
  });

  async function handleCopy(key: string, text: string) {
    const ok = await copyText(text);
    if (!ok) return;
    setCopiedKey(key);
    window.setTimeout(() => {
      setCopiedKey((cur) => (cur === key ? "" : cur));
    }, 1500);
  }

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
    const flatData = data.map((r) => ({
      id: r.id,
      crawlerId: r.crawlerId,
      url: r.url,
      ...((r.data as Record<string, unknown>) ?? {}),
    }));
    const headers = Object.keys(flatData[0]);
    const csv = [
      headers.join(","),
      ...flatData.map((row) =>
        headers.map((h) => JSON.stringify((row as Record<string, unknown>)[h] ?? "")).join(",")
      ),
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `spider-data-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div class="p-3 sm:p-6 space-y-4 sm:space-y-6 pb-8">
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 class="text-xl sm:text-2xl font-bold">数据查询</h2>
        <div class="flex gap-2">
          <button
            onClick={exportJson}
            class="flex-1 sm:flex-none px-3 py-2 text-sm rounded-lg bg-gray-800 text-gray-300 hover:bg-gray-700"
          >
            导出 JSON
          </button>
          <button
            onClick={exportCsv}
            class="flex-1 sm:flex-none px-3 py-2 text-sm rounded-lg bg-gray-800 text-gray-300 hover:bg-gray-700"
          >
            导出 CSV
          </button>
        </div>
      </div>

      <div class="flex flex-col sm:flex-row gap-3 sm:gap-4">
        <select
          onChange={(e) => {
            setCrawlerId(e.target.value ? Number(e.target.value) : undefined);
            setPage(1);
          }}
          class="w-full sm:w-auto bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-gray-300 focus:border-indigo-500 focus:outline-none"
        >
          <option value="">全部爬虫</option>
          <For each={crawlerList()}>{(c) => <option value={c.id}>{c.name}</option>}</For>
        </select>
        <input
          type="search"
          placeholder="搜索标题 / 链接..."
          value={search()}
          onInput={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          class="w-full flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-gray-300 placeholder:text-gray-600 focus:border-indigo-500 focus:outline-none"
        />
      </div>

      <Suspense fallback={<p class="text-gray-500">加载中...</p>}>
        {/* Mobile card list */}
        <div class="md:hidden space-y-3">
          <For each={records()?.data} fallback={<p class="text-gray-500 text-sm py-8 text-center">暂无数据</p>}>
            {(record) => {
              const data = () => payloadOf(record);
              const links = () => linksOf(record);
              return (
                <article class="rounded-xl border border-gray-800 bg-gray-900/80 p-3.5 space-y-3">
                  <div class="space-y-1">
                    <h3 class="text-sm font-medium text-gray-100 leading-snug break-words">
                      {data().title || `记录 #${record.id}`}
                    </h3>
                    <div class="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-gray-500">
                      <span>#{record.id}</span>
                      <span>·</span>
                      <span class="truncate max-w-[10rem]">{crawlerName()(record.crawlerId)}</span>
                      <Show when={data().forum_name}>
                        <span>·</span>
                        <span>{data().forum_name}</span>
                      </Show>
                      <span>·</span>
                      <span>{formatBeijing(record.createdAt)}</span>
                    </div>
                  </div>

                  <Show when={links().length > 0} fallback={<p class="text-xs text-gray-600">无下载链接</p>}>
                    <div class="space-y-2">
                      <div class="flex items-center justify-between gap-2">
                        <span class="text-xs text-gray-500">下载链接 ({links().length})</span>
                        <Show when={links().length > 1}>
                          <button
                            type="button"
                            onClick={() => handleCopy(`all-${record.id}`, links().join("\n"))}
                            class="text-xs px-2 py-1 rounded-md bg-indigo-500/15 text-indigo-300 active:bg-indigo-500/30"
                          >
                            {copiedKey() === `all-${record.id}` ? "已复制全部" : "复制全部"}
                          </button>
                        </Show>
                      </div>
                      <ul class="space-y-2">
                        <For each={links()}>
                          {(link, idx) => (
                            <li class="flex gap-2 items-stretch">
                              <code class="flex-1 min-w-0 text-[11px] leading-relaxed text-gray-300 bg-gray-950/80 border border-gray-800 rounded-lg px-2.5 py-2 break-all select-all">
                                {link}
                              </code>
                              <button
                                type="button"
                                onClick={() => handleCopy(`${record.id}-${idx()}`, link)}
                                class="shrink-0 px-3 rounded-lg bg-indigo-600 text-white text-xs font-medium active:bg-indigo-500 min-w-[3.25rem]"
                              >
                                {copiedKey() === `${record.id}-${idx()}` ? "已复制" : "复制"}
                              </button>
                            </li>
                          )}
                        </For>
                      </ul>
                    </div>
                  </Show>

                  <Show when={record.url}>
                    <a
                      href={record.url!}
                      target="_blank"
                      rel="noreferrer"
                      class="inline-block text-xs text-indigo-400 active:text-indigo-300"
                    >
                      打开原帖 →
                    </a>
                  </Show>
                </article>
              );
            }}
          </For>
        </div>

        {/* Desktop table */}
        <Card class="hidden md:block">
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="text-left text-gray-500 text-xs uppercase tracking-wider">
                  <th class="pb-3 pr-3">ID</th>
                  <th class="pb-3 pr-3">爬虫</th>
                  <th class="pb-3 pr-3">标题 / 链接</th>
                  <th class="pb-3 pr-3">下载</th>
                  <th class="pb-3">时间</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-800">
                <For each={records()?.data}>
                  {(record) => {
                    const data = () => payloadOf(record);
                    const links = () => linksOf(record);
                    return (
                      <tr class="hover:bg-gray-800/50 align-top">
                        <td class="py-3 pr-3 text-gray-400 whitespace-nowrap">#{record.id}</td>
                        <td class="py-3 pr-3 text-gray-300 whitespace-nowrap">
                          {crawlerName()(record.crawlerId)}
                        </td>
                        <td class="py-3 pr-3 max-w-[280px]">
                          <p class="text-gray-200 text-sm leading-snug break-words">
                            {data().title || "-"}
                          </p>
                          <Show when={record.url}>
                            <a
                              href={record.url!}
                              target="_blank"
                              rel="noreferrer"
                              class="text-xs text-indigo-400 hover:underline break-all"
                            >
                              {record.url}
                            </a>
                          </Show>
                        </td>
                        <td class="py-3 pr-3 min-w-[220px]">
                          <Show when={links().length > 0} fallback={<span class="text-gray-600">-</span>}>
                            <ul class="space-y-1.5">
                              <For each={links()}>
                                {(link, idx) => (
                                  <li class="flex items-center gap-2">
                                    <code
                                      class="flex-1 min-w-0 text-xs text-gray-400 truncate"
                                      title={link}
                                    >
                                      {shortLink(link)}
                                    </code>
                                    <button
                                      type="button"
                                      onClick={() => handleCopy(`d-${record.id}-${idx()}`, link)}
                                      class="shrink-0 text-xs px-2 py-1 rounded bg-gray-800 text-indigo-300 hover:bg-gray-700"
                                    >
                                      {copiedKey() === `d-${record.id}-${idx()}` ? "已复制" : "复制"}
                                    </button>
                                  </li>
                                )}
                              </For>
                            </ul>
                          </Show>
                        </td>
                        <td class="py-3 text-gray-500 whitespace-nowrap">
                          {formatBeijing(record.createdAt)}
                        </td>
                      </tr>
                    );
                  }}
                </For>
              </tbody>
            </table>
          </div>
        </Card>

        <div class="flex items-center justify-between gap-3 pt-1 md:pt-0">
          <span class="text-sm text-gray-500 shrink-0">共 {records()?.total ?? 0} 条</span>
          <div class="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page() === 1}
              class="px-4 py-2 text-sm rounded-lg bg-gray-800 text-gray-300 hover:bg-gray-700 disabled:opacity-40"
            >
              上一页
            </button>
            <span class="px-2 py-2 text-sm text-gray-500 tabular-nums">第 {page()} 页</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              class="px-4 py-2 text-sm rounded-lg bg-gray-800 text-gray-300 hover:bg-gray-700"
            >
              下一页
            </button>
          </div>
        </div>
      </Suspense>
    </div>
  );
}
