import type { ContestPhase } from "../../api";

/** Подпись фазы; `switch` исчерпывающий: новая фаза на сервере сломает сборку, а не экран. */
export function phaseLabel(phase: ContestPhase): string {
  switch (phase) {
    case "submission":
      return "Приём идей";
    case "voting":
      return "Голосование";
    case "finished":
      return "Завершён";
  }
}
