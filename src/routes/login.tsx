import { createSignal } from "solid-js";
import { useNavigate } from "@solidjs/router";
import { Title } from "@solidjs/meta";
import { login } from "~/lib/auth";

export default function LoginPage() {
  const [username, setUsername] = createSignal("");
  const [password, setPassword] = createSignal("");
  const [error, setError] = createSignal("");
  const [loading, setLoading] = createSignal(false);
  const navigate = useNavigate();

  async function handleSubmit(e: Event) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const result = await login(username(), password());
      if (result.ok) {
        navigate("/", { replace: true });
      } else {
        setError(result.error || "登录失败");
      }
    } catch {
      setError("网络错误，请重试");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <Title>登录 - Spider Admin</Title>
      <div class="min-h-screen flex items-center justify-center bg-gray-950 px-4">
        <div class="w-full max-w-sm">
          <div class="text-center mb-8">
            <h1 class="text-3xl font-bold tracking-tight">
              <span class="text-indigo-400">Spider</span> Admin
            </h1>
            <p class="text-gray-500 text-sm mt-2">爬虫管理系统</p>
          </div>

          <form onSubmit={handleSubmit} class="rounded-xl border border-gray-800 bg-gray-900 p-6 space-y-5">
            <div>
              <label class="block text-sm text-gray-400 mb-1.5">用户名</label>
              <input
                type="text"
                value={username()}
                onInput={(e) => setUsername(e.target.value)}
                placeholder="请输入用户名"
                required
                autofocus
                class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3.5 py-2.5 text-sm text-gray-200 placeholder:text-gray-600 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/30 transition-colors"
              />
            </div>

            <div>
              <label class="block text-sm text-gray-400 mb-1.5">密码</label>
              <input
                type="password"
                value={password()}
                onInput={(e) => setPassword(e.target.value)}
                placeholder="请输入密码"
                required
                class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3.5 py-2.5 text-sm text-gray-200 placeholder:text-gray-600 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/30 transition-colors"
              />
            </div>

            {error() && (
              <div class="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                {error()}
              </div>
            )}

            <button
              type="submit"
              disabled={loading()}
              class="w-full py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium text-white transition-colors"
            >
              {loading() ? "登录中..." : "登 录"}
            </button>
          </form>

          <p class="text-center text-xs text-gray-600 mt-6">
            Powered by SolidStart · Neon Postgres
          </p>
        </div>
      </div>
    </>
  );
}
