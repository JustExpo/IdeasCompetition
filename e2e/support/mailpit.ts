import { expect } from "@playwright/test";

import { MAILPIT_URL } from "./env";

export interface MailSummary {
  ID: string;
  Subject: string;
  To: { Address: string }[];
}

export async function listMessages(): Promise<MailSummary[]> {
  const response = await fetch(`${MAILPIT_URL}/api/v1/messages?limit=500`);
  expect(response.ok).toBe(true);
  return ((await response.json()) as { messages: MailSummary[] }).messages;
}

/** Письма получателю, в теме которых есть `topic` (Mailpit общий для всех тестов). */
export async function mailsTo(address: string, topic: string): Promise<MailSummary[]> {
  return (await listMessages()).filter(
    (mail) =>
      mail.Subject.includes(topic) &&
      mail.To.some((to) => to.Address.toLowerCase() === address.toLowerCase()),
  );
}

export async function readText(id: string): Promise<string> {
  const response = await fetch(`${MAILPIT_URL}/api/v1/message/${id}`);
  expect(response.ok).toBe(true);
  return ((await response.json()) as { Text: string }).Text;
}
