const FALLBACK = "/";
const AUTH_PATHS = new Set(["/login", "/register"]);

/**
 * Куда вернуть пользователя после входа. `state.from` кладёт `RequireAuth`; значение всё равно
 * проверяется: переходить можно только по пути своего сайта, не на чужой адрес (open redirect).
 */
export function resolveReturnPath(state: unknown): string {
  if (typeof state !== "object" || state === null || !("from" in state)) {
    return FALLBACK;
  }
  const from = state.from;
  if (typeof from !== "object" || from === null || !("pathname" in from)) {
    return FALLBACK;
  }
  const pathname = from.pathname;
  if (typeof pathname !== "string" || !/^\/(?![/\\])/.test(pathname) || AUTH_PATHS.has(pathname)) {
    return FALLBACK;
  }
  const search = "search" in from && typeof from.search === "string" ? from.search : "";
  const hash = "hash" in from && typeof from.hash === "string" ? from.hash : "";
  return `${pathname}${search}${hash}`;
}
