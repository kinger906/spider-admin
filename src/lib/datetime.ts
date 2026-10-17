/** Format DB timestamps for admin UI in Beijing time (UTC+8). */

const BEIJING = "Asia/Shanghai";

function parseDbTimestamp(input: string | Date): Date {
  if (input instanceof Date) return input;
  const s = String(input).trim();
  // Neon/pg often returns naive UTC "YYYY-MM-DD HH:mm:ss.sss" without Z.
  // JS would treat that as local time and show 8h behind in China.
  if (
    /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}/.test(s) &&
    !/[zZ]|[+-]\d{2}:?\d{2}$/.test(s)
  ) {
    return new Date(s.replace(" ", "T") + "Z");
  }
  return new Date(s);
}

export function formatBeijing(
  input: string | Date | null | undefined,
  fallback = "-"
): string {
  if (input == null || input === "") return fallback;
  const d = parseDbTimestamp(input);
  if (Number.isNaN(d.getTime())) return fallback;
  return d.toLocaleString("zh-CN", {
    timeZone: BEIJING,
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}
