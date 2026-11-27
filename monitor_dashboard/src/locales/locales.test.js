// The translations: every language has the same keys, and every key the code uses exists.
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';
import { getLanguageCode, getLocale } from '../i18nLocale';
import de from './de.json';
import en from './en.json';
import fr from './fr.json';

const SRC = join(import.meta.dirname, '..');

function flatten(object, prefix = '') {
  return Object.entries(object).flatMap(([key, value]) =>
    value && typeof value === 'object'
      ? flatten(value, `${prefix}${key}.`)
      : [[`${prefix}${key}`, value]],
  );
}

function keys(locale) {
  return flatten(locale)
    .map(([key]) => key)
    .sort();
}

function sourceFiles(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return sourceFiles(path);
    return /\.(jsx?|tsx?)$/.test(entry.name) && !/\.test\./.test(entry.name)
      ? [path]
      : [];
  });
}

/** Translation keys written in the source: t('a.b') calls and the *Key / key: 'a.b' fields MainGrid and the menu use. */
function keysUsedInSource() {
  const used = new Map();
  const pattern = /(?:\bt\(\s*|\b(?:\w*Key|key):\s*)'([a-zA-Z]+\.[\w.]+)'/g;
  for (const file of sourceFiles(SRC)) {
    for (const match of readFileSync(file, 'utf8').matchAll(pattern)) {
      used.set(match[1], relative(SRC, file));
    }
  }
  return used;
}

describe('translations', () => {
  it.each([
    ['fr', fr],
    ['de', de],
  ])('%s has exactly the English keys', (_name, locale) => {
    expect(keys(locale)).toEqual(keys(en));
  });

  it.each([
    ['en', en],
    ['fr', fr],
    ['de', de],
  ])('%s has no empty strings', (_name, locale) => {
    const empty = flatten(locale).filter(([, value]) => !String(value).trim());

    expect(empty).toEqual([]);
  });

  it.each([
    ['fr', fr],
    ['de', de],
  ])('%s keeps the English placeholders', (_name, locale) => {
    const placeholders = (value) =>
      [...String(value).matchAll(/{{\s*(\w+)\s*}}/g)].map((m) => m[1]).sort();
    const translated = Object.fromEntries(flatten(locale));

    const mismatched = flatten(en).filter(
      ([key, value]) =>
        JSON.stringify(placeholders(value)) !==
        JSON.stringify(placeholders(translated[key])),
    );
    expect(mismatched).toEqual([]);
  });

  it('defines every key the code uses', () => {
    const defined = new Set(keys(en));
    const used = keysUsedInSource();

    // The scan must find the keys, or this test would pass for nothing.
    expect(used.size).toBeGreaterThan(50);
    const missing = [...used].filter(([key]) => !defined.has(key));
    expect(missing).toEqual([]);
  });
});

describe('getLocale', () => {
  it.each([
    ['en', 'en-US'],
    ['fr', 'fr-FR'],
    ['de-CH', 'de-DE'],
    ['it', 'en-US'],
    [undefined, 'en-US'],
  ])('maps %s to %s', (language, locale) => {
    expect(getLocale(language)).toBe(locale);
  });

  it('uses the fallback for unknown languages', () => {
    expect(getLocale('it', 'it-IT')).toBe('it-IT');
  });

  it('reduces a language tag to its language', () => {
    expect(getLanguageCode('fr-CA')).toBe('fr');
    expect(getLanguageCode('')).toBe('en');
  });
});
