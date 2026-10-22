import { useLogout } from "./session";

export function LogoutButton() {
  const logout = useLogout();
  return (
    <button
      type="button"
      className="button button-secondary"
      disabled={logout.isPending}
      onClick={() => {
        logout.mutate();
      }}
    >
      Выйти
    </button>
  );
}
