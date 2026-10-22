import { useState, type FormEvent } from "react";

import { describeError, type User } from "../../api";
import { Field } from "../../shared/ui/Field";
import { Notice } from "../../shared/ui/Notice";
import { useLogin } from "./session";

interface LoginFormProps {
  onSuccess: (user: User) => void;
}

export function LoginForm({ onSuccess }: LoginFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [missing, setMissing] = useState<{ email?: string; password?: string }>({});
  const login = useLogin();
  const failure = login.error ? describeError(login.error) : null;

  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const problems: { email?: string; password?: string } = {};
    if (email.trim() === "") {
      problems.email = "Введите e-mail.";
    }
    if (password === "") {
      problems.password = "Введите пароль.";
    }
    setMissing(problems);
    if (Object.keys(problems).length > 0) {
      return;
    }
    login.mutate({ email: email.trim(), password }, { onSuccess });
  };

  return (
    <form onSubmit={submit} noValidate aria-label="Вход">
      {failure ? <Notice tone="error">{failure.message}</Notice> : null}
      <Field label="E-mail" error={missing.email}>
        {(control) => (
          <input
            {...control}
            type="email"
            autoComplete="username"
            value={email}
            onChange={(event) => {
              setEmail(event.target.value);
            }}
          />
        )}
      </Field>
      <Field label="Пароль" error={missing.password}>
        {(control) => (
          <input
            {...control}
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
            }}
          />
        )}
      </Field>
      <button type="submit" className="button" disabled={login.isPending}>
        {login.isPending ? "Входим…" : "Войти"}
      </button>
    </form>
  );
}
