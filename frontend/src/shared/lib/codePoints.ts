/**
 * Длина текста так, как её считает сервер: в кодовых точках после NFC и обрезки пробелов
 * (CLAUDE.md §8.1). `length` строки считает UTF-16 единицы, и эмодзи на границе лимита
 * показал бы неверный остаток.
 */
export function countCodePoints(text: string): number {
  // `Array.from` обходит строку по кодовым точкам, а не по единицам UTF-16.
  return Array.from(text.normalize("NFC").trim()).length;
}
