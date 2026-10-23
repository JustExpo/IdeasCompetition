import { expect, test } from "@playwright/test";

import {
  after,
  browserContextFor,
  createContest,
  loginOrganizer,
  moveClockTo,
  registerEmployee,
  submitIdea,
  uniqueSuffix,
} from "../support/api";
import { fillIdeaForm, voteButton } from "../support/ui";

// П2: страница открыта, срок прошёл — сервер отклоняет запись, пользователь видит понятный текст.
test.describe("запись после дедлайна при открытой странице", () => {
  test("подача идеи", async ({ browser }) => {
    const organizer = await loginOrganizer();
    const employee = await registerEmployee("late");
    const contest = await createContest(organizer, `Поздняя подача ${uniqueSuffix()}`);
    const context = await browserContextFor(browser, employee);
    const page = await context.newPage();
    await page.goto(`/contests/${String(contest.id)}`);
    await fillIdeaForm(page, "Опоздавшая идея", "Форма была открыта до дедлайна");

    await moveClockTo(after(contest.submissionDeadline, 1_000));
    await page.getByRole("button", { name: "Предложить идею" }).click();

    await expect(page.getByText("Приём идей закрыт.")).toBeVisible();
    const ideas = await employee.api.get(`/api/contests/${String(contest.id)}/ideas`);
    expect(JSON.stringify(await ideas.json())).not.toContain("Опоздавшая идея");
    await context.close();
  });

  test("правка идеи", async ({ browser }) => {
    const organizer = await loginOrganizer();
    const employee = await registerEmployee("editor");
    const contest = await createContest(organizer, `Поздняя правка ${uniqueSuffix()}`);
    const title = `Идея ${uniqueSuffix()}`;
    await submitIdea(employee, contest.id, title);
    const context = await browserContextFor(browser, employee);
    const page = await context.newPage();
    await page.goto(`/contests/${String(contest.id)}`);
    await page.getByRole("button", { name: "Править" }).click();
    await page
      .getByRole("form", { name: "Правка идеи" })
      .getByLabel("Название")
      .fill(`${title} (правка)`);

    await moveClockTo(after(contest.submissionDeadline, 1_000));
    await page.getByRole("button", { name: "Сохранить" }).click();

    await expect(page.getByText("Приём идей закрыт.")).toBeVisible();
    await context.close();
  });

  test("голос", async ({ browser }) => {
    const organizer = await loginOrganizer();
    const author = await registerEmployee("author");
    const voter = await registerEmployee("late-voter");
    const contest = await createContest(organizer, `Поздний голос ${uniqueSuffix()}`);
    const title = `Идея ${uniqueSuffix()}`;
    const ideaId = await submitIdea(author, contest.id, title);
    await moveClockTo(after(contest.submissionDeadline, 1_000));
    const context = await browserContextFor(browser, voter);
    const page = await context.newPage();
    await page.goto(`/contests/${String(contest.id)}`);
    await expect(voteButton(page, title)).toHaveText("Проголосовать");

    await moveClockTo(after(contest.votingDeadline, 1_000));
    await voteButton(page, title).click();

    await expect(page.getByText("Голосование закрыто.")).toBeVisible();
    const response = await voter.api.put(`/api/ideas/${ideaId}/vote`);
    expect(response.status()).toBe(409);
    await context.close();
  });
});
