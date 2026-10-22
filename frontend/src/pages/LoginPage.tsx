import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { LoginForm, resolveReturnPath, useSession } from "../features/auth";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const session = useSession();
  const returnPath = resolveReturnPath(location.state);

  // Уже вошедшего с этой страницы уводим: иначе форма входа осталась бы при живой сессии.
  if (session.data) {
    return <Navigate to={returnPath} replace />;
  }
  return (
    <main className="page page-narrow">
      <h1>Вход</h1>
      <LoginForm
        onSuccess={() => {
          void navigate(returnPath, { replace: true });
        }}
      />
      <p>
        Нет учётной записи? <Link to="/register">Зарегистрируйтесь</Link>
      </p>
    </main>
  );
}
