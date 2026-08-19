import { A } from "@solidjs/router";
import { type ParentProps } from "solid-js";

const navItems = [
  { href: "/", label: "仪表盘", icon: "📊" },
  { href: "/crawlers", label: "爬虫管理", icon: "🕷️" },
  { href: "/tasks", label: "任务监控", icon: "⚡" },
  { href: "/data", label: "数据查询", icon: "🗄️" },
  { href: "/logs", label: "系统日志", icon: "📋" },
  { href: "/settings", label: "系统设置", icon: "⚙️" },
];

export default function Layout(props: ParentProps) {
  return (
    <div class="flex h-screen">
      <aside class="w-60 shrink-0 border-r border-gray-800 bg-gray-900 flex flex-col">
        <div class="px-5 py-6 border-b border-gray-800">
          <h1 class="text-xl font-bold tracking-tight">
            <span class="text-indigo-400">Spider</span> Admin
          </h1>
          <p class="text-xs text-gray-500 mt-1">爬虫管理系统</p>
        </div>
        <nav class="flex-1 py-4 space-y-1 px-3">
          {navItems.map((item) => (
            <A
              href={item.href}
              class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-400 hover:bg-gray-800 hover:text-gray-100 transition-colors"
              activeClass="!bg-indigo-500/10 !text-indigo-400"
              end={item.href === "/"}
            >
              <span class="text-base">{item.icon}</span>
              {item.label}
            </A>
          ))}
        </nav>
        <div class="px-5 py-4 border-t border-gray-800 text-xs text-gray-600">
          v1.0.0 · Powered by SolidStart
        </div>
      </aside>
      <main class="flex-1 overflow-auto">{props.children}</main>
    </div>
  );
}
