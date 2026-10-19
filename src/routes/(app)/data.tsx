import { createAsync } from "@solidjs/router";
import {
  For,
  Suspense,
  createSignal,
  Show,
  createMemo,
  createEffect,
  onCleanup,
  onMount,
} from "solid-js";
import { getDataRecords, getCrawlers } from "~/lib/api";
import { formatBeijing } from "~/lib/datetime";
import Card from "~/components/Card";

const PAGE_SIZE_OPTIONS = [20, 50, 100, 200] as const;
const DEFAULT_PAGE_SIZE = 200;

type DataRecord = Awaited<ReturnType<typeof getDataRecords>>["data"][number];

type RecordPayload = {
  title?: string;
  forum_name?: string;
  published_at?: string;
  download_links?: string[];
  tags?: string[] | string;
  category?: string;
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

/** 桌面下载列：多显示一些，末尾 … */
function shortLink(link: string, max = 72): string {
  if (link.length <= max) return link;
  const head = Math.max(40, max - 12);
  return `${link.slice(0, head)}…`;
}

function payloadOf(record: { data: unknown }): RecordPayload {
  const d = record.data;
  return d && typeof d === "object" ? (d as RecordPayload) : {};
}

function linksOf(record: { data: unknown }): string[] {
  const links = payloadOf(record).download_links;
  if (!Array.isArray(links)) return [];
  // 展示层去重（历史数据可能已重复入库）
  return [...new Set(links.map(String).map((s) => s.trim()).filter(Boolean))];
}

function tagsOf(data: RecordPayload): string[] {
  if (Array.isArray(data.tags)) {
    return data.tags.map(String).map((t) => t.trim()).filter(Boolean);
  }
  if (typeof data.tags === "string" && data.tags.trim()) {
    return data.tags.split(/[,，]/).map((t) => t.trim()).filter(Boolean);
  }
  if (typeof data.category === "string" && data.category.trim()) {
    return data.category.split(/[,，]/).map((t) => t.trim()).filter(Boolean);
  }
  return [];
}

function buildPageItems(current: number, totalPages: number): Array<number | "…"> {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }
  const pages = new Set<number>([1, totalPages, current, current - 1, current + 1]);
  if (current <= 3) {
    pages.add(2);
    pages.add(3);
    pages.add(4);
  }
  if (current >= totalPages - 2) {
    pages.add(totalPages - 1);
    pages.add(totalPages - 2);
    pages.add(totalPages - 3);
  }
  const sorted = [...pages].filter((p) => p >= 1 && p <= totalPages).sort((a, b) => a - b);
  const out: Array<number | "…"> = [];
  for (let i = 0; i < sorted.length; i++) {
    if (i > 0 && sorted[i]! - sorted[i - 1]! > 1) out.push("…");
    out.push(sorted[i]!);
  }
  return out;
}

function RecordCard(props: {
  record: DataRecord;
  crawlerName: (id: number) => string;
  copiedKey: () => string;
  onCopy: (key: string, text: string) => void;
}) {
  const data = () => payloadOf(props.record);
  const links = () => linksOf(props.record);
  const tags = () => tagsOf(data());
  return (
    <article class="rounded-xl border border-gray-800 bg-gray-900/80 p-3.5 space-y-3">
      <div class="space-y-1.5">
        <h3 class="text-sm font-medium text-gray-100 leading-snug break-words">
          {data().title || `记录 #${props.record.id}`}
        </h3>
        <div class="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-gray-500">
          <span>#{props.record.id}</span>
          <Show when={data().published_at || props.record.createdAt}>
            <span>·</span>
            <span>发布 {data().published_at || formatBeijing(props.record.createdAt)}</span>
          </Show>
          <Show when={props.record.url}>
            <span>·</span>
            <a
              href={props.record.url!}
              target="_blank"
              rel="noreferrer"
              class="text-indigo-400 active:text-indigo-300"
            >
              打开原链 →
            </a>
          </Show>
        </div>
        <Show when={tags().length > 0}>
          <div class="flex flex-wrap gap-1.5 pt-0.5">
            <For each={tags()}>
              {(tag) => (
                <span class="text-[11px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">
                  {tag}
                </span>
              )}
            </For>
          </div>
        </Show>
      </div>

      <Show when={links().length > 0} fallback={<p class="text-xs text-gray-600">无下载链接</p>}>
        <div class="space-y-2">
          <div class="flex items-center justify-between gap-2">
            <span class="text-xs text-gray-500">下载链接 ({links().length})</span>
            <Show when={links().length > 1}>
              <button
                type="button"
                onClick={() => props.onCopy(`all-${props.record.id}`, links().join("\n"))}
                class="text-xs px-2 py-1 rounded-md bg-indigo-500/15 text-indigo-300 active:bg-indigo-500/30"
              >
                {props.copiedKey() === `all-${props.record.id}` ? "已复制全部" : "复制全部"}
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
                    onClick={() => props.onCopy(`${props.record.id}-${idx()}`, link)}
                    class="shrink-0 px-3 rounded-lg bg-indigo-600 text-white text-xs font-medium active:bg-indigo-500 min-w-[3.25rem]"
                  >
                    {props.copiedKey() === `${props.record.id}-${idx()}` ? "已复制" : "复制"}
                  </button>
                </li>
              )}
            </For>
          </ul>
        </div>
      </Show>
    </article>
  );
}

export default function DataPage() {
  const [crawlerId, setCrawlerId] = createSignal<number | undefined>();
  const [searchInput, setSearchInput] = createSignal("");
  const [search, setSearch] = createSignal("");
  const [page, setPage] = createSignal(1);
  const [pageSize, setPageSize] = createSignal(DEFAULT_PAGE_SIZE);
  const [copiedKey, setCopiedKey] = createSignal("");
  const [mobileItems, setMobileItems] = createSignal<DataRecord[]>([]);
  const [mobileLoadingMore, setMobileLoadingMore] = createSignal(false);
  let sentinelRef: HTMLDivElement | undefined;

  const crawlerList = createAsync(() => getCrawlers());
  const records = createAsync(() =>
    getDataRecords(crawlerId(), search(), page(), pageSize())
  );

  const totalPages = createMemo(() => {
    const total = records()?.total ?? 0;
    return Math.max(1, Math.ceil(total / pageSize()));
  });

  const pageItems = createMemo(() => buildPageItems(page(), totalPages()));

  const hasMore = createMemo(() => page() < totalPages());

  const crawlerName = createMemo(() => {
    const map = new Map((crawlerList() ?? []).map((c) => [c.id, c.name]));
    return (id: number) => map.get(id) ?? String(id);
  });

  // 移动端：按页累积；筛选/每页变化时从第 1 页重建
  createEffect(() => {
    const r = records();
    if (!r?.data) return;
    const p = page();
    if (p === 1) {
      setMobileItems(r.data);
      setMobileLoadingMore(false);
      return;
    }
    setMobileItems((prev) => {
      const seen = new Set(prev.map((x) => x.id));
      const merged = [...prev];
      for (const row of r.data) {
        if (!seen.has(row.id)) merged.push(row);
      }
      return merged;
    });
    setMobileLoadingMore(false);
  });

  function commitSearch() {
    const next = searchInput().trim();
    if (next === search()) return;
    setSearch(next);
    setPage(1);
    setMobileItems([]);
  }

  async function handleCopy(key: string, text: string) {
    const ok = await copyText(text);
    if (!ok) return;
    setCopiedKey(key);
    window.setTimeout(() => {
      setCopiedKey((cur) => (cur === key ? "" : cur));
    }, 1500);
  }

  function goPage(p: number) {
    const next = Math.min(Math.max(1, p), totalPages());
    setPage(next);
  }

  function loadMoreMobile() {
    if (mobileLoadingMore() || !hasMore()) return;
    setMobileLoadingMore(true);
    setPage((p) => p + 1);
  }

  onMount(() => {
    if (typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(
      (entries) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        // 仅移动端列表可见时滚动加载
        if (window.matchMedia("(min-width: 768px)").matches) return;
        loadMoreMobile();
      },
      { root: null, rootMargin: "240px 0px", threshold: 0 }
    );
    let observed: Element | null = null;
    const tryObserve = () => {
      if (!sentinelRef || sentinelRef === observed) return;
      if (observed) io.unobserve(observed);
      io.observe(sentinelRef);
      observed = sentinelRef;
    };
    tryObserve();
    const id = window.setInterval(tryObserve, 300);
    onCleanup(() => {
      window.clearInterval(id);
      io.disconnect();
    });
  });

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

  const PaginationBar = () => (
    <div class="hidden md:flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between pt-1">
      <div class="flex flex-wrap items-center gap-3 text-sm text-gray-500">
        <span class="shrink-0">共 {records()?.total ?? 0} 条</span>
        <label class="inline-flex items-center gap-1.5">
          <span class="text-gray-500">每页</span>
          <select
            value={pageSize()}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setPage(1);
              setMobileItems([]);
            }}
            class="bg-gray-800 border border-gray-700 rounded-md px-2 py-1.5 text-sm text-gray-300 focus:border-indigo-500 focus:outline-none"
          >
            <For each={[...PAGE_SIZE_OPTIONS]}>
              {(n) => <option value={n}>{n}</option>}
            </For>
          </select>
          <span>条</span>
        </label>
      </div>

      <div class="flex flex-wrap items-center gap-1.5">
        <button
          type="button"
          onClick={() => goPage(page() - 1)}
          disabled={page() <= 1}
          class="px-3 py-1.5 text-sm rounded-md bg-gray-800 text-gray-300 hover:bg-gray-700 disabled:opacity-40"
        >
          上一页
        </button>
        <For each={pageItems()}>
          {(item) =>
            item === "…" ? (
              <span class="px-1.5 text-gray-600 select-none">…</span>
            ) : (
              <button
                type="button"
                onClick={() => goPage(item)}
                class={
                  item === page()
                    ? "min-w-8 px-2 py-1.5 text-sm rounded-md bg-indigo-600 text-white"
                    : "min-w-8 px-2 py-1.5 text-sm rounded-md bg-gray-800 text-gray-300 hover:bg-gray-700"
                }
              >
                {item}
              </button>
            )
          }
        </For>
        <button
          type="button"
          onClick={() => goPage(page() + 1)}
          disabled={page() >= totalPages()}
          class="px-3 py-1.5 text-sm rounded-md bg-gray-800 text-gray-300 hover:bg-gray-700 disabled:opacity-40"
        >
          下一页
        </button>
      </div>
    </div>
  );

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
            setMobileItems([]);
          }}
          class="w-full sm:w-auto bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-gray-300 focus:border-indigo-500 focus:outline-none"
        >
          <option value="">全部爬虫</option>
          <For each={crawlerList()}>{(c) => <option value={c.id}>{c.name}</option>}</For>
        </select>
        <input
          type="search"
          placeholder="搜索标题 / 链接（失焦后搜索）"
          value={searchInput()}
          onInput={(e) => setSearchInput(e.target.value)}
          onBlur={() => commitSearch()}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.currentTarget.blur();
              commitSearch();
            }
          }}
          class="w-full flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-gray-300 placeholder:text-gray-600 focus:border-indigo-500 focus:outline-none"
        />
      </div>

      <Suspense fallback={<p class="text-gray-500">加载中...</p>}>
        {/* Mobile: infinite scroll */}
        <div class="md:hidden space-y-3">
          <For
            each={mobileItems()}
            fallback={<p class="text-gray-500 text-sm py-8 text-center">暂无数据</p>}
          >
            {(record) => (
              <RecordCard
                record={record}
                crawlerName={crawlerName()}
                copiedKey={copiedKey}
                onCopy={handleCopy}
              />
            )}
          </For>
          <div ref={(el) => (sentinelRef = el)} class="py-4 text-center text-xs text-gray-500">
            <Show when={mobileLoadingMore()}>加载中...</Show>
            <Show when={!mobileLoadingMore() && hasMore()}>上拉加载更多</Show>
            <Show when={!hasMore() && mobileItems().length > 0}>已加载全部</Show>
          </div>
          <div class="flex items-center justify-between text-xs text-gray-500 px-1">
            <span>
              已显示 {mobileItems().length} / {records()?.total ?? 0}
            </span>
            <label class="inline-flex items-center gap-1">
              <span>每页</span>
              <select
                value={pageSize()}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setPage(1);
                  setMobileItems([]);
                }}
                class="bg-gray-800 border border-gray-700 rounded px-1.5 py-1 text-gray-300"
              >
                <For each={[...PAGE_SIZE_OPTIONS]}>
                  {(n) => <option value={n}>{n}</option>}
                </For>
              </select>
            </label>
          </div>
        </div>

        {/* Desktop table */}
        <Card class="hidden md:block">
          <div class="overflow-x-auto">
            <table class="w-full text-sm table-fixed">
              <thead>
                <tr class="text-left text-gray-500 text-xs uppercase tracking-wider">
                  <th class="pb-3 pr-3 w-16">ID</th>
                  <th class="pb-3 pr-3 w-36">爬虫</th>
                  <th class="pb-3 pr-3 w-[34%]">标题 / 链接</th>
                  <th class="pb-3 pr-3">下载</th>
                  <th class="pb-3 w-40">入库时间</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-800">
                <For each={records()?.data}>
                  {(record) => {
                    const data = () => payloadOf(record);
                    const links = () => linksOf(record);
                    const tags = () => tagsOf(data());
                    return (
                      <tr class="hover:bg-gray-800/50 align-top">
                        <td class="py-3 pr-3 text-gray-400 whitespace-nowrap">#{record.id}</td>
                        <td class="py-3 pr-3 text-gray-300">
                          <span class="line-clamp-2">{crawlerName()(record.crawlerId)}</span>
                        </td>
                        <td class="py-3 pr-3">
                          <p class="text-gray-100 text-sm leading-snug break-words">
                            {data().title || "-"}
                          </p>
                          <div class="mt-1.5 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs">
                            <Show when={record.url}>
                              <a
                                href={record.url!}
                                target="_blank"
                                rel="noreferrer"
                                class="text-indigo-400 hover:text-indigo-300 whitespace-nowrap"
                              >
                                打开原链 →
                              </a>
                            </Show>
                            <Show when={data().published_at}>
                              <span class="text-gray-500">
                                发布时间 {data().published_at}
                              </span>
                            </Show>
                            <Show when={tags().length > 0}>
                              <span class="inline-flex flex-wrap items-center gap-1">
                                <For each={tags()}>
                                  {(tag) => (
                                    <span class="px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">
                                      {tag}
                                    </span>
                                  )}
                                </For>
                              </span>
                            </Show>
                          </div>
                        </td>
                        <td class="py-3 pr-3">
                          <Show when={links().length > 0} fallback={<span class="text-gray-600">-</span>}>
                            <ul class="space-y-1.5">
                              <For each={links()}>
                                {(link, idx) => (
                                  <li class="inline-flex max-w-full items-center gap-1.5">
                                    <code
                                      class="text-xs text-gray-300 whitespace-nowrap overflow-hidden text-ellipsis max-w-[min(36rem,100%)]"
                                      title={link}
                                    >
                                      {shortLink(link, 80)}
                                    </code>
                                    <button
                                      type="button"
                                      onClick={() => handleCopy(`d-${record.id}-${idx()}`, link)}
                                      class="shrink-0 text-xs px-2 py-0.5 rounded bg-gray-800 text-indigo-300 hover:bg-gray-700"
                                    >
                                      {copiedKey() === `d-${record.id}-${idx()}` ? "已复制" : "复制"}
                                    </button>
                                  </li>
                                )}
                              </For>
                            </ul>
                          </Show>
                        </td>
                        <td class="py-3 text-gray-500 whitespace-nowrap text-xs">
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

        <PaginationBar />
      </Suspense>
    </div>
  );
}
