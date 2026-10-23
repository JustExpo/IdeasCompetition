import { expect, test } from "@playwright/test";

import {
  after,
  browserContextFor,
  castVote,
  loginOrganizer,
  moveClockTo,
  registerEmployee,
  serverNow,
  submitIdea,
  uniqueSuffix,
} from "../support/api";
import { mailsTo, readText } from "../support/mailpit";
import { dashboardNumber, fillIdeaForm, toLocalInput, voteButton } from "../support/ui";

// Ф1–Ф5, П1, П8, П10: подача → голосование → финал → письма, глазами людей.
test("полный цикл конкурса: подача, голосование, итоги и письма", async ({ browser }) => {
  const suffix = uniqueSuffix();
  const topic = `Цикл ${suffix}`;
  const organizer = await loginOrganizer();
  const alice = await registerEmployee("alice");
  const bob = await registerEmployee("bob");
  const carol = await registerEmployee("carol");

  // Организатор создаёт конкурс через форму.
  const organizerContext = await browserContextFor(browser, organizer);
  const organizerPage = await organizerContext.newPage();
  await organizerPage.goto("/");
  const now = await serverNow(organizer);
  const submissionDeadline = after(now, 3_600_000);
  const votingDeadline = after(now, 7_200_000);
  await organizerPage.getByRole("button", { name: "Создать конкурс" }).click();
  await organizerPage.getByLabel("Тема").fill(topic);
  await organizerPage.getByLabel("Приём идей закрывается").fill(toLocalInput(submissionDeadline));
  await organizerPage.getByLabel("Голосование закрывается").fill(toLocalInput(votingDeadline));
  await organizerPage
    .getByRole("form", { name: "Новый конкурс" })
    .getByRole("button", { name: "Создать конкурс" })
    .click();
  await organizerPage.getByRole("link", { name: topic }).click();
  await expect(organizerPage.getByRole("heading", { name: topic })).toBeVisible();
  const contestId = Number(organizerPage.url().split("/").pop());
  expect(contestId).toBeGreaterThan(0);
  // П10: правило ничьей видно с фазы подачи.
  await expect(organizerPage.getByText("Правило ничьей:")).toBeVisible();

  // Алиса подаёт идею через форму; Боб — позже (при ничьей победит Алиса, П10).
  const aliceContext = await browserContextFor(browser, alice);
  const alicePage = await aliceContext.newPage();
  await alicePage.goto(`/contests/${String(contestId)}`);
  const aliceTitle = `Идея Алисы ${suffix}`;
  await fillIdeaForm(alicePage, aliceTitle, "Кофемашина на каждом этаже");
  await alicePage.getByRole("button", { name: "Предложить идею" }).click();
  await expect(alicePage.getByRole("heading", { name: aliceTitle })).toBeVisible();
  const bobTitle = `Идея Боба ${suffix}`;
  await submitIdea(bob, contestId, bobTitle);

  // П3: Боб в фазе подачи не видит чужих идей, организатор видит только счётчик.
  const bobContext = await browserContextFor(browser, bob);
  const bobPage = await bobContext.newPage();
  await bobPage.goto(`/contests/${String(contestId)}`);
  await expect(bobPage.getByRole("heading", { name: bobTitle })).toBeVisible();
  await expect(bobPage.getByText(aliceTitle)).toHaveCount(0);

  // Раунд подачи закрывается сам по времени (П1).
  await moveClockTo(after(submissionDeadline, 1_000));
  await alicePage.reload();
  await bobPage.reload();
  // П4: идеи без авторов; за свою голосовать нельзя.
  await expect(alicePage.getByText("Это ваша идея")).toBeVisible();
  await expect(alicePage.getByText(bob.name)).toHaveCount(0);
  await voteButton(alicePage, bobTitle).click();
  await expect(voteButton(alicePage, bobTitle)).toHaveText("Отозвать голос");
  await voteButton(bobPage, aliceTitle).click();
  await expect(voteButton(bobPage, aliceTitle)).toHaveText("Отозвать голос");
  await castVote(carol, await findIdeaId(carol, contestId, bobTitle));

  // Ф5: организатор видит число идей и проголосовавших без перезагрузки.
  await organizerPage.reload();
  await expect(dashboardNumber(organizerPage, "Идей подано")).toHaveText("2");
  await expect(dashboardNumber(organizerPage, "Проголосовало")).toHaveText("3");

  // П8: до финала сотрудник итогов не видит.
  const earlyResults = await bob.api.get(`/api/contests/${String(contestId)}/results`);
  expect(earlyResults.status()).toBe(403);

  // Голосование закрывается: 2 голоса за идею Боба, 1 за идею Алисы → побеждает Боб.
  await moveClockTo(after(votingDeadline, 1_000));
  await alicePage.reload();
  const table = alicePage.getByRole("region", { name: "Итоги конкурса" });
  await expect(table).toBeVisible();
  await expect(table.locator("tr.winner")).toContainText(bobTitle);
  await expect(table.locator("tr.winner")).toContainText(bob.name);

  // Ф4: победителю, проигравшему и только голосовавшему — каждому своё письмо.
  await expect
    .poll(async () => (await mailsTo(bob.email, topic)).map((m) => m.Subject), { timeout: 30_000 })
    .toContainEqual(`Вы победили в конкурсе «${topic}»`);
  await expect
    .poll(async () => (await mailsTo(alice.email, topic)).map((m) => m.Subject))
    .toContainEqual(`Ваша идея не прошла: конкурс «${topic}»`);
  await expect
    .poll(async () => (await mailsTo(carol.email, topic)).map((m) => m.Subject))
    .toContainEqual(`Итоги конкурса «${topic}»`);
  const [winnerMail] = await mailsTo(bob.email, topic);
  expect(await readText(winnerMail!.ID)).toContain(bobTitle);

  await organizerContext.close();
  await aliceContext.close();
  await bobContext.close();
});

async function findIdeaId(
  person: Awaited<ReturnType<typeof registerEmployee>>,
  contestId: number,
  title: string,
): Promise<string> {
  const response = await person.api.get(`/api/contests/${String(contestId)}/ideas`);
  const body = (await response.json()) as { items: { id: string; title: string }[] };
  const found = body.items.find((idea) => idea.title === title);
  expect(found, "идея в списке голосования").toBeDefined();
  return found!.id;
}
