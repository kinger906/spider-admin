const colors: Record<string, string> = {
  idle: "bg-gray-700 text-gray-300",
  running: "bg-emerald-500/20 text-emerald-400 animate-pulse",
  paused: "bg-amber-500/20 text-amber-400",
  error: "bg-red-500/20 text-red-400",
  disabled: "bg-gray-800 text-gray-500",
  pending: "bg-blue-500/20 text-blue-400",
  success: "bg-emerald-500/20 text-emerald-400",
  failed: "bg-red-500/20 text-red-400",
  cancelled: "bg-gray-700 text-gray-400",
};

export default function StatusBadge(props: { status: string }) {
  return (
    <span class={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colors[props.status] ?? colors.idle}`}>
      {props.status}
    </span>
  );
}
