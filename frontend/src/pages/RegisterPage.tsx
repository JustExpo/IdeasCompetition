import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { RegisterForm, resolveReturnPath, useSession } from "../features/auth";

export function RegisterPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const session = useSession();
  const returnPath = resolveReturnPath(location.state);

  if (session.data) {
    return <Navigate to={returnPath} replace />;
  }
  return (
    <main className="page page-narrow">
      <h1>Регистрация</h1>
      <RegisterForm
        onSuccess={() => {
          void navigate(returnPath, { replace: true });
        }}
      />
      <p>
        Уже есть учётная запись? <Link to="/login">Войдите</Link>
      </p>
    </main>
  );
}
