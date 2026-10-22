import { Navigate, Outlet, useLocation } from "react-router-dom";

import { describeError } from "../../api";
import { Notice } from "../../shared/ui/Notice";
import { useSession } from "./session";

/** Защита маршрутов: без сессии — на вход с возвратом на исходный адрес после входа. */
export function RequireAuth() {
  const session = useSession();
  const location = useLocation();

  if (session.isPending) {
    return (
      <p className="page" role="status">
        Загрузка…
      </p>
    );
  }
  if (session.isError) {
    // Не 401 (его `fetchCurrentUser` превращает в `null`): сервер недоступен или сломан.
    return (
      <div className="page">
        <Notice tone="error" onRetry={() => void session.refetch()}>
          {describeError(session.error).message}
        </Notice>
      </div>
    );
  }
  if (session.data === null) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return <Outlet />;
}
