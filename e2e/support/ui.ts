import { expect, type Page } from "@playwright/test";

import { PASSWORD } from "./env";

export async function loginThroughForm(page: Page, email: string, password = PASSWORD) {
  await page.goto("/login");
  await page.getByLabel("E-mail").fill(email);
  await page.getByLabel("Пароль").fill(password);
  await page.getByRole("button", { name: "Войти" }).click();
  await expect(page.getByRole("button", { name: "Выйти" })).toBeVisible();
}

/** Значение для `datetime-local` в поясе браузера (в конфиге Playwright это UTC). */
export function toLocalInput(moment: Date): string {
  return moment.toISOString().slice(0, 16);
}

export async function fillIdeaForm(page: Page, title: string, description: string) {
  await page.getByLabel("Название").fill(title);
  await page.getByLabel("Описание").fill(description);
}

export function voteButton(page: Page, ideaTitle: string) {
  return page
    .locator("li.idea-item", { hasText: ideaTitle })
    .getByRole("button", { name: /Проголосовать|Отозвать голос/ });
}

export function dashboardNumber(page: Page, caption: "Идей подано" | "Проголосовало") {
  return page.locator("dl.stats > div", { hasText: caption }).locator("dd");
}
