import { type ParentProps } from "solid-js";

export default function Card(props: ParentProps<{ title?: string; class?: string }>) {
  return (
    <div class={`rounded-xl border border-gray-800 bg-gray-900 ${props.class ?? ""}`}>
      {props.title && (
        <div class="px-5 py-3.5 border-b border-gray-800">
          <h3 class="text-sm font-semibold text-gray-200">{props.title}</h3>
        </div>
      )}
      <div class="p-5">{props.children}</div>
    </div>
  );
}
