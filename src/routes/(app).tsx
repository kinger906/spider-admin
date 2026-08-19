import { type ParentProps, Show, Suspense } from "solid-js";
import { createAsync, useNavigate } from "@solidjs/router";
import Layout from "~/components/Layout";
import { getAuthUser } from "~/lib/auth";

export default function AppLayout(props: ParentProps) {
  const user = createAsync(() => getAuthUser());
  const navigate = useNavigate();

  return (
    <Suspense fallback={<div class="min-h-screen bg-gray-950" />}>
      <Show
        when={user()}
        fallback={(() => { navigate("/login", { replace: true }); return null; })()}
      >
        {(u) => <Layout user={u()}>{props.children}</Layout>}
      </Show>
    </Suspense>
  );
}
