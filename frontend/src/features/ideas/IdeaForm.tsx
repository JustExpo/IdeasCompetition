import { useState, type FormEvent } from "react";

import { describeError, type IdeaDraft } from "../../api";
import { countCodePoints } from "../../shared/lib/codePoints";
import { Field } from "../../shared/ui/Field";
import { Notice } from "../../shared/ui/Notice";

// Совпадают с model сервера (idea/model/idea.py); окончательно проверяет сервер.
export const TITLE_MAX_LENGTH = 200;
export const DESCRIPTION_MAX_LENGTH = 10_000;

interface IdeaFormProps {
  /** Заголовок формы и подпись кнопки зависят от того, создаём или правим идею. */
  heading: string;
  submitLabel: string;
  initial?: IdeaDraft;
  pending: boolean;
  /** Ошибка последней отправки; текст в полях остаётся, пока пользователь сам его не изменит. */
  error: unknown;
  onSubmit: (draft: IdeaDraft) => void;
  onCancel?: () => void;
}

/** Проверка до отправки; сервер повторяет её и остаётся последним словом. */
export function validateDraft(draft: IdeaDraft): { title?: string; description?: string } {
  const errors: { title?: string; description?: string } = {};
  const titleLength = countCodePoints(draft.title);
  const descriptionLength = countCodePoints(draft.description);
  if (titleLength === 0) {
    errors.title = "Введите название идеи.";
  } else if (titleLength > TITLE_MAX_LENGTH) {
    errors.title = `Название не длиннее ${String(TITLE_MAX_LENGTH)} символов.`;
  }
  if (descriptionLength === 0) {
    errors.description = "Опишите идею.";
  } else if (descriptionLength > DESCRIPTION_MAX_LENGTH) {
    errors.description = `Описание не длиннее ${String(DESCRIPTION_MAX_LENGTH)} символов.`;
  }
  return errors;
}

export function IdeaForm({
  heading,
  submitLabel,
  initial,
  pending,
  error,
  onSubmit,
  onCancel,
}: IdeaFormProps) {
  const [title, setTitle] = useState(initial?.title ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [local, setLocal] = useState<{ title?: string; description?: string }>({});
  const failure = error ? describeError(error) : null;
  const serverFields = failure?.fieldErrors ?? {};

  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (pending) {
      return; // двойной клик: второй submit не уходит, пока идёт первый
    }
    const draft = { title, description };
    const errors = validateDraft(draft);
    setLocal(errors);
    if (Object.keys(errors).length === 0) {
      onSubmit(draft);
    }
  };

  const titleLength = countCodePoints(title);
  const descriptionLength = countCodePoints(description);
  return (
    <form className="card" onSubmit={submit} noValidate aria-label={heading}>
      <h3>{heading}</h3>
      {failure ? <Notice tone="error">{failure.message}</Notice> : null}
      <Field
        label="Название"
        hint={`${String(titleLength)} из ${String(TITLE_MAX_LENGTH)}`}
        error={local.title ?? serverFields.title}
      >
        {(control) => (
          <input
            {...control}
            type="text"
            value={title}
            onChange={(event) => {
              setTitle(event.target.value);
            }}
          />
        )}
      </Field>
      <Field
        label="Описание"
        hint={`${String(descriptionLength)} из ${String(DESCRIPTION_MAX_LENGTH)}`}
        error={local.description ?? serverFields.description}
      >
        {(control) => (
          <textarea
            {...control}
            rows={5}
            value={description}
            onChange={(event) => {
              setDescription(event.target.value);
            }}
          />
        )}
      </Field>
      <div className="toolbar">
        <button type="submit" className="button" disabled={pending}>
          {pending ? "Сохраняем…" : submitLabel}
        </button>
        {onCancel ? (
          <button type="button" className="button button-secondary" onClick={onCancel}>
            Отмена
          </button>
        ) : null}
      </div>
    </form>
  );
}
