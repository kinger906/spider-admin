import Card from "~/components/Card";

export default function SettingsPage() {
  return (
    <div class="p-6 space-y-6">
      <h2 class="text-2xl font-bold">系统设置</h2>

      <Card title="数据库配置">
        <dl class="grid grid-cols-2 gap-4 text-sm">
          <div>
            <dt class="text-gray-500">数据库类型</dt>
            <dd class="text-gray-200 mt-1">Neon Postgres</dd>
          </div>
          <div>
            <dt class="text-gray-500">文件存储</dt>
            <dd class="text-gray-200 mt-1">Vercel Blob</dd>
          </div>
          <div>
            <dt class="text-gray-500">部署平台</dt>
            <dd class="text-gray-200 mt-1">Vercel</dd>
          </div>
          <div>
            <dt class="text-gray-500">CI/CD</dt>
            <dd class="text-gray-200 mt-1">GitHub Actions</dd>
          </div>
        </dl>
      </Card>

      <Card title="爬虫默认配置">
        <div class="space-y-4">
          <div>
            <label class="block text-sm text-gray-400 mb-1">默认重试次数</label>
            <input type="number" value="3" class="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300 w-32 focus:border-indigo-500 focus:outline-none" />
          </div>
          <div>
            <label class="block text-sm text-gray-400 mb-1">请求超时 (秒)</label>
            <input type="number" value="30" class="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300 w-32 focus:border-indigo-500 focus:outline-none" />
          </div>
        </div>
      </Card>

      <Card title="安全设置">
        <div class="space-y-4">
          <div>
            <label class="block text-sm text-gray-400 mb-1">API 密钥状态</label>
            <div class="flex items-center gap-2">
              <span class="inline-block w-2 h-2 bg-emerald-400 rounded-full"></span>
              <span class="text-sm text-gray-300">已配置</span>
            </div>
          </div>
          <p class="text-xs text-gray-600">API 密钥通过环境变量 API_SECRET 配置，用于 Python 爬虫与管理端之间的安全通信。</p>
        </div>
      </Card>
    </div>
  );
}
