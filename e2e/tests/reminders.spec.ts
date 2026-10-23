import { expect, test } from "@playwright/test";

import {
  after,
  createContest,
  loginOrganizer,
  moveClockTo,
  registerEmployee,
  submitIdea,
  uniqueSuffix,
} from "../support/api";
import { mailsTo } from "../support/mailpit";

// П9: за сутки до закрытия раунда — одно напоминание тем, кто не участвовал.
test("напоминание о подаче приходит один раз и только не участвовавшим", async () => {
  const organizer = await loginOrganizer();
  const idle = await registerEmployee("idle");
  const active = await registerEmployee("active");
  const topic = `Напоминание ${uniqueSuffix()}`;
  // Дедлайн через час: окно «за сутки» уже открыто, напоминание уходит на ближайшем тике.
  const contest = await createContest(organizer, topic);
  await submitIdea(active, contest.id, `Идея ${uniqueSuffix()}`);

  await expect
    .poll(async () => (await mailsTo(idle.email, topic)).length, { timeout: 40_000 })
    .toBe(1);
  const [reminder] = await mailsTo(idle.email, topic);
  expect(reminder?.Subject).toContain("Завтра закрывается приём идей");

  // Ещё тики (перевод часов запускает тик сразу) новых писем не добавляют.
  await moveClockTo(after(contest.submissionDeadline, -1_800_000));
  await moveClockTo(after(contest.submissionDeadline, -900_000));
  expect(
    (await mailsTo(idle.email, topic)).filter((m) => m.Subject.includes("приём")),
  ).toHaveLength(1);
  expect(await mailsTo(active.email, topic)).toHaveLength(0);
});
