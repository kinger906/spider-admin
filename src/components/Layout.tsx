import { A, useNavigate } from "@solidjs/router";
import { createSignal, type ParentProps, Show } from "solid-js";
import { logout } from "~/lib/auth";

const navItems = [
  { href: "/", label: "仪表盘", icon: "📊" },
  { href: "/crawlers", label: "爬虫管理", icon: "🕷️" },
  { href: "/tasks", label: "任务监控", icon: "⚡" },
  { href: "/data", label: "数据查询", icon: "🗄️" },
  { href: "/logs", label: "系统日志", icon: "📋" },
  { href: "/settings", label: "系统设置", icon: "⚙️" },
];

interface LayoutProps extends ParentProps {
  user: { username: string; displayName: string | null; role: string };
}

export default function Layout(props: LayoutProps) {
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = createSignal(false);

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  function closeMenu() {
    setMenuOpen(false);
  }

  const sidebar = (
    <>
      <div class="px-5 py-5 border-b border-gray-800">
        <h1 class="text-xl font-bold tracking-tight">
          <span class="text-indigo-400">Spider</span> Admin
        </h1>
        <p class="text-xs text-gray-500 mt-1">爬虫管理系统</p>
      </div>
      <nav class="flex-1 py-4 space-y-1 px-3 overflow-y-auto">
        {navItems.map((item) => (
          <A
            href={item.href}
            onClick={closeMenu}
            class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-400 hover:bg-gray-800 hover:text-gray-100 transition-colors"
            activeClass="!bg-indigo-500/10 !text-indigo-400"
            end={item.href === "/"}
          >
            <span class="text-base">{item.icon}</span>
            {item.label}
          </A>
        ))}
      </nav>
      <div class="px-4 py-4 border-t border-gray-800 space-y-3">
        <div class="flex items-center gap-2.5">
          <div class="w-8 h-8 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center text-xs font-bold shrink-0">
            {(props.user.displayName || props.user.username).charAt(0).toUpperCase()}
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm text-gray-200 truncate">
              {props.user.displayName || props.user.username}
            </p>
            <p class="text-xs text-gray-500">{props.user.role}</p>
          </div>
        </div>
        <button
          onClick={handleLogout}
          class="w-full text-xs text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-md px-2 py-1.5 transition-colors text-left"
        >
          退出登录
        </button>
      </div>
    </>
  );

  return (
    <div class="flex h-dvh min-h-0 bg-gray-950">
      {/* Desktop sidebar */}
      <aside class="hidden md:flex w-60 shrink-0 border-r border-gray-800 bg-gray-900 flex-col">
        {sidebar}
      </aside>

      {/* Mobile drawer */}
      <Show when={menuOpen()}>
        <div class="fixed inset-0 z-40 md:hidden">
          <button
            type="button"
            class="absolute inset-0 bg-black/60"
            aria-label="关闭菜单"
            onClick={closeMenu}
          />
          <aside class="absolute inset-y-0 left-0 w-[min(16.5rem,85vw)] bg-gray-900 border-r border-gray-800 flex flex-col shadow-xl">
            {sidebar}
          </aside>
        </div>
      </Show>

      <div class="flex-1 flex flex-col min-w-0 min-h-0">
        <header class="md:hidden sticky top-0 z-30 flex items-center gap-3 px-3 py-2.5 border-b border-gray-800 bg-gray-950/95 backdrop-blur">
          <button
            type="button"
            onClick={() => setMenuOpen(true)}
            class="p-2 rounded-lg text-gray-300 hover:bg-gray-800"
            aria-label="打开菜单"
          >
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <span class="text-sm font-semibold text-gray-200">
            <span class="text-indigo-400">Spider</span> Admin
          </span>
        </header>
        <main class="flex-1 overflow-auto min-h-0">{props.children}</main>
      </div>
    </div>
  );
}
