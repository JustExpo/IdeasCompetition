import { useEffect, useState } from "react";

import { serverClock, type ServerClock } from "../../shared/lib/serverTime";

interface CountdownProps {
  submissionDeadline: string;
  votingDeadline: string;
  clock?: ServerClock;
}

/** «1 д 2 ч 03 мин 04 с» до момента; не больше трёх старших единиц, секунды видны всегда. */
export function formatRemaining(ms: number): string {
  const totalSeconds = Math.max(0, Math.ceil(ms / 1000));
  const days = Math.floor(totalSeconds / 86_400);
  const hours = Math.floor((totalSeconds % 86_400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const parts: string[] = [];
  if (days > 0) {
    parts.push(`${String(days)} д`);
  }
  if (days > 0 || hours > 0) {
    parts.push(`${String(hours)} ч`);
  }
  if (days > 0 || hours > 0 || minutes > 0) {
    parts.push(`${String(minutes).padStart(2, "0")} мин`);
  }
  parts.push(`${String(seconds).padStart(2, "0")} с`);
  return parts.join(" ");
}

/** Что осталось до ближайшего дедлайна, по серверным часам (часы пользователя могут врать). */
export function Countdown({
  submissionDeadline,
  votingDeadline,
  clock = serverClock,
}: CountdownProps) {
  const [, setTick] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => {
      setTick((tick) => tick + 1);
    }, 1000);
    return () => {
      window.clearInterval(timer);
    };
  }, []);

  const now = clock.now();
  const untilSubmission = Date.parse(submissionDeadline) - now;
  const untilVoting = Date.parse(votingDeadline) - now;
  if (untilSubmission > 0) {
    return <p className="countdown">До закрытия приёма идей: {formatRemaining(untilSubmission)}</p>;
  }
  if (untilVoting > 0) {
    return <p className="countdown">До закрытия голосования: {formatRemaining(untilVoting)}</p>;
  }
  return <p className="countdown">Конкурс завершён.</p>;
}
