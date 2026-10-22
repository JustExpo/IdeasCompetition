import { useState, type FormEvent } from "react";

import { describeError, type User } from "../../api";
import { Field } from "../../shared/ui/Field";
import { Notice } from "../../shared/ui/Notice";
import { useRegister } from "./session";

interface RegisterFormProps {
  onSuccess: (user: User) => void;
}

type FieldName = "name" | "email" | "password";

// Совпадают с правилами сервера (CLAUDE.md §9.1); окончательно проверяет сервер.
const PASSWORD_MIN = 10;
const PASSWORD_MAX = 128;
const NAME_MAX = 100;

function validate(
  name: string,
  email: string,
  password: string,
): Partial<Record<FieldName, string>> {
  const problems: Partial<Record<FieldName, string>> = {};
  if (name.trim() === "") {
    problems.name = "Введите имя.";
  } else if (name.trim().length > NAME_MAX) {
    problems.name = `Имя не длиннее ${String(NAME_MAX)} символов.`;
  }
  if (email.trim() === "") {
    problems.email = "Введите e-mail.";
  }
  if (password.length < PASSWORD_MIN || password.length > PASSWORD_MAX) {
    problems.password = `Пароль — от ${String(PASSWORD_MIN)} до ${String(PASSWORD_MAX)} символов.`;
  }
  return problems;
}

export function RegisterForm({ onSuccess }: RegisterFormProps) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [local, setLocal] = useState<Partial<Record<FieldName, string>>>({});
  const register = useRegister();
  const failure = register.error ? describeError(register.error) : null;
  const serverFields = failure?.fieldErrors ?? {};
  // Ошибка без своего поля (429, 503, сеть) показывается над формой.
  const showGeneral = failure !== null && Object.keys(serverFields).length === 0;

  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const problems = validate(name, email, password);
    setLocal(problems);
    if (Object.keys(problems).length > 0) {
      return;
    }
    register.mutate({ name: name.trim(), email: email.trim(), password }, { onSuccess });
  };

  return (
    <form onSubmit={submit} noValidate aria-label="Регистрация">
      {showGeneral ? <Notice tone="error">{failure.message}</Notice> : null}
      <Field label="Имя" error={local.name ?? serverFields.name}>
        {(control) => (
          <input
            {...control}
            type="text"
            autoComplete="name"
            value={name}
            onChange={(event) => {
              setName(event.target.value);
            }}
          />
        )}
      </Field>
      <Field label="E-mail" error={local.email ?? serverFields.email}>
        {(control) => (
          <input
            {...control}
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => {
              setEmail(event.target.value);
            }}
          />
        )}
      </Field>
      <Field
        label="Пароль"
        hint={`От ${String(PASSWORD_MIN)} до ${String(PASSWORD_MAX)} символов.`}
        error={local.password ?? serverFields.password}
      >
        {(control) => (
          <input
            {...control}
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
            }}
          />
        )}
      </Field>
      <button type="submit" className="button" disabled={register.isPending}>
        {register.isPending ? "Регистрируем…" : "Зарегистрироваться"}
      </button>
    </form>
  );
}
