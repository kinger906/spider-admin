import { type ParentProps, Show, Suspense, createEffect } from "solid-js";
import { createAsync, useNavigate } from "@solidjs/router";
import Layout from "~/components/Layout";
import { getAuthUser } from "~/lib/auth";

export default function AppLayout(props: ParentProps) {
  const user = createAsync(() => getAuthUser());
  const navigate = useNavigate();

  createEffect(() => {
    if (user() === null) {
      navigate("/login", { replace: true });
    }
  });

  return (
    <Suspense fallback={<div class="min-h-screen bg-gray-950 flex items-center justify-center text-gray-500">加载中...</div>}>
      <Show when={user()}>
        {(u) => <Layout user={u()}>{props.children}</Layout>}
      </Show>
    </Suspense>
  );
}
