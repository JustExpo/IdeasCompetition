import { expect, test } from "@playwright/test";

import {
  after,
  browserContextFor,
  castVote,
  createContest,
  loginOrganizer,
  moveClockTo,
  registerEmployee,
  submitIdea,
  uniqueSuffix,
} from "../support/api";
import { dashboardNumber, voteButton } from "../support/ui";

const REALTIME_MS = 2_000; // «сразу» из ТЗ: не дольше 2 с

test.describe("голосование в реальном времени", () => {
  test("П5: две вкладки одного человека дают один голос, вторая вкладка видит его сразу", async ({
    browser,
  }) => {
    const organizer = await loginOrganizer();
    const author = await registerEmployee("author");
    const voter = await registerEmployee("voter");
    const contest = await createContest(organizer, `Две вкладки ${uniqueSuffix()}`);
    const title = `Идея ${uniqueSuffix()}`;
    const ideaId = await submitIdea(author, contest.id, title);
    await moveClockTo(after(contest.submissionDeadline, 1_000));

    const context = await browserContextFor(browser, voter);
    const tabA = await context.newPage();
    const tabB = await context.newPage();
    await tabA.goto(`/contests/${String(contest.id)}`);
    await tabB.goto(`/contests/${String(contest.id)}`);
    await expect(voteButton(tabA, title)).toHaveText("Проголосовать");
    await expect(voteButton(tabB, title)).toHaveText("Проголосовать");

    await voteButton(tabA, title).click();
    await expect(voteButton(tabA, title)).toHaveText("Отозвать голос");
    await expect(voteButton(tabB, title)).toHaveText("Отозвать голос", { timeout: REALTIME_MS });

    // Параллельные повторы голоса не создают второй: ограничение держит БД.
    const repeats = await Promise.all(
      [1, 2, 3].map(() => voter.api.put(`/api/ideas/${ideaId}/vote`)),
    );
    expect(repeats.map((r) => r.status())).toEqual([204, 204, 204]);
    const dashboard = await organizer.api.get(
      `/api/organizer/contests/${String(contest.id)}/dashboard`,
    );
    const body = (await dashboard.json()) as { voters_count: number; results: { votes: number }[] };
    expect(body.voters_count).toBe(1);
    expect(body.results[0]?.votes).toBe(1);
    await context.close();
  });

  test("П11: идея, удалённая автором во время голосования, исчезает у остальных сразу", async ({
    browser,
  }) => {
    const organizer = await loginOrganizer();
    const author = await registerEmployee("author");
    const other = await registerEmployee("other");
    const contest = await createContest(organizer, `Удаление ${uniqueSuffix()}`);
    const title = `Удаляемая ${uniqueSuffix()}`;
    await submitIdea(author, contest.id, title);
    await submitIdea(other, contest.id, `Остальная ${uniqueSuffix()}`);
    await moveClockTo(after(contest.submissionDeadline, 1_000));

    const authorContext = await browserContextFor(browser, author);
    const otherContext = await browserContextFor(browser, other);
    const authorPage = await authorContext.newPage();
    const otherPage = await otherContext.newPage();
    await authorPage.goto(`/contests/${String(contest.id)}`);
    await otherPage.goto(`/contests/${String(contest.id)}`);
    await expect(otherPage.getByRole("heading", { name: title })).toBeVisible();
    await castVote(other, await ideaIdOf(other, contest.id, title));

    const item = authorPage.locator("li.idea-item", { hasText: title });
    await item.getByRole("button", { name: "Удалить" }).click();
    await item.getByRole("button", { name: "Да, удалить" }).click();

    await expect(otherPage.getByRole("heading", { name: title })).toHaveCount(0, {
      timeout: REALTIME_MS,
    });
    await authorContext.close();
    await otherContext.close();
  });

  test("П7: цифры на экране организатора меняются без обновления страницы", async ({ browser }) => {
    const organizer = await loginOrganizer();
    const author = await registerEmployee("author");
    const voter = await registerEmployee("voter");
    const contest = await createContest(organizer, `Организатор ${uniqueSuffix()}`);
    const title = `Идея ${uniqueSuffix()}`;
    const ideaId = await submitIdea(author, contest.id, title);

    const context = await browserContextFor(browser, organizer);
    const page = await context.newPage();
    await page.goto(`/contests/${String(contest.id)}`);
    await expect(dashboardNumber(page, "Идей подано")).toHaveText("1");
    await expect(dashboardNumber(page, "Проголосовало")).toHaveText("0");

    // Чужую идею в фазе подачи организатор не видит, но счётчик растёт.
    await submitIdea(voter, contest.id, `Вторая ${uniqueSuffix()}`);
    await expect(dashboardNumber(page, "Идей подано")).toHaveText("2", { timeout: REALTIME_MS });

    await moveClockTo(after(contest.submissionDeadline, 1_000));
    await page.reload();
    await castVote(voter, ideaId);
    await expect(dashboardNumber(page, "Проголосовало")).toHaveText("1", { timeout: REALTIME_MS });
    await context.close();
  });
});

async function ideaIdOf(
  person: Awaited<ReturnType<typeof registerEmployee>>,
  contestId: number,
  title: string,
): Promise<string> {
  const response = await person.api.get(`/api/contests/${String(contestId)}/ideas`);
  const body = (await response.json()) as { items: { id: string; title: string }[] };
  const found = body.items.find((idea) => idea.title === title);
  expect(found).toBeDefined();
  return found!.id;
}
