import { useState, type FormEvent } from "react";

import { describeError } from "../../api";
import { localInputToIso } from "../../shared/lib/dateTime";
import { Field } from "../../shared/ui/Field";
import { Notice } from "../../shared/ui/Notice";
import { useCreateContest } from "./queries";

type FieldName = "topic" | "description" | "submission_deadline" | "voting_deadline";
type FieldErrors = Partial<Record<FieldName, string>>;

// Совпадают с model сервера (contest/model/contest.py); окончательно проверяет сервер.
export const TOPIC_MAX_LENGTH = 200;
export const DESCRIPTION_MAX_LENGTH = 10_000;

interface CreateContestFormProps {
  onCreated: () => void;
  onCancel: () => void;
}

interface Values {
  topic: string;
  description: string;
  submissionDeadline: string;
  votingDeadline: string;
}

/** Проверка до отправки; возвращает ошибки или готовое тело запроса. */
function prepare(values: Values) {
  const errors: FieldErrors = {};
  const topic = values.topic.trim();
  if (topic === "") {
    errors.topic = "Введите тему конкурса.";
  } else if (topic.length > TOPIC_MAX_LENGTH) {
    errors.topic = `Тема не длиннее ${String(TOPIC_MAX_LENGTH)} символов.`;
  }
  if (values.description.length > DESCRIPTION_MAX_LENGTH) {
    errors.description = `Описание не длиннее ${String(DESCRIPTION_MAX_LENGTH)} символов.`;
  }
  const submission = localInputToIso(values.submissionDeadline);
  const voting = localInputToIso(values.votingDeadline);
  if (submission === null) {
    errors.submission_deadline = "Укажите существующие дату и время.";
  }
  if (voting === null) {
    errors.voting_deadline = "Укажите существующие дату и время.";
  }
  if (submission !== null && voting !== null && Date.parse(submission) >= Date.parse(voting)) {
    errors.voting_deadline = "Голосование должно закрываться позже, чем приём идей.";
  }
  if (Object.keys(errors).length > 0 || submission === null || voting === null) {
    return { errors, body: null };
  }
  return {
    errors,
    body: {
      topic,
      description: values.description.trim(),
      submission_deadline: submission,
      voting_deadline: voting,
    },
  };
}

export function CreateContestForm({ onCreated, onCancel }: CreateContestFormProps) {
  const [values, setValues] = useState<Values>({
    topic: "",
    description: "",
    submissionDeadline: "",
    votingDeadline: "",
  });
  const [local, setLocal] = useState<FieldErrors>({});
  const create = useCreateContest();
  const failure = create.error ? describeError(create.error) : null;
  const serverFields = (failure?.fieldErrors ?? {}) as FieldErrors;
  const showGeneral = failure !== null && Object.keys(serverFields).length === 0;
  const errorOf = (name: FieldName): string | undefined => local[name] ?? serverFields[name];
  const change = (patch: Partial<Values>): void => {
    setValues({ ...values, ...patch });
  };

  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const { errors, body } = prepare(values);
    setLocal(errors);
    if (body !== null) {
      create.mutate(body, { onSuccess: onCreated });
    }
  };

  return (
    <form className="card" onSubmit={submit} noValidate aria-label="Новый конкурс">
      <h2>Новый конкурс</h2>
      {showGeneral ? <Notice tone="error">{failure.message}</Notice> : null}
      <Field label="Тема" error={errorOf("topic")}>
        {(control) => (
          <input
            {...control}
            type="text"
            value={values.topic}
            onChange={(event) => {
              change({ topic: event.target.value });
            }}
          />
        )}
      </Field>
      <Field label="Описание" error={errorOf("description")}>
        {(control) => (
          <textarea
            {...control}
            rows={4}
            value={values.description}
            onChange={(event) => {
              change({ description: event.target.value });
            }}
          />
        )}
      </Field>
      <Field
        label="Приём идей закрывается"
        hint="Время указывается в часовом поясе вашего браузера."
        error={errorOf("submission_deadline")}
      >
        {(control) => (
          <input
            {...control}
            type="datetime-local"
            value={values.submissionDeadline}
            onChange={(event) => {
              change({ submissionDeadline: event.target.value });
            }}
          />
        )}
      </Field>
      <Field label="Голосование закрывается" error={errorOf("voting_deadline")}>
        {(control) => (
          <input
            {...control}
            type="datetime-local"
            value={values.votingDeadline}
            onChange={(event) => {
              change({ votingDeadline: event.target.value });
            }}
          />
        )}
      </Field>
      <div className="toolbar">
        <button type="submit" className="button" disabled={create.isPending}>
          {create.isPending ? "Создаём…" : "Создать конкурс"}
        </button>
        <button type="button" className="button button-secondary" onClick={onCancel}>
          Отмена
        </button>
      </div>
    </form>
  );
}
