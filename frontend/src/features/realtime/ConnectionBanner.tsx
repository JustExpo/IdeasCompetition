import type { ConnectionStatus } from "../../api";
import { Notice } from "../../shared/ui/Notice";

/** Пока связи нет, данные на экране могут устареть; после восстановления они перечитаются сами. */
export function ConnectionBanner({ status }: { status: ConnectionStatus }) {
  if (status !== "offline") {
    return null;
  }
  return (
    <Notice tone="error">
      Нет связи с сервером: показанные данные могут устареть. Подключаемся заново…
    </Notice>
  );
}
