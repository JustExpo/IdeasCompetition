import { Link, Outlet } from "react-router-dom";

import { LogoutButton, useSession } from "../features/auth";
import { E2EBadge } from "../features/environment";
import { NewVersionBanner } from "../features/realtime";

/** Общая рамка защищённых экранов: заголовок, имя пользователя, выход. */
export function AppShell() {
  const session = useSession();
  return (
    <div className="page">
      <header className="app-header">
        <h1>
          <Link to="/">Конкурс идей</Link>
        </h1>
        {session.data ? (
          <div className="user">
            <span>{session.data.name}</span>
            <LogoutButton />
          </div>
        ) : null}
      </header>
      <E2EBadge />
      <NewVersionBanner />
      <main>
        <Outlet />
      </main>
    </div>
  );
}
