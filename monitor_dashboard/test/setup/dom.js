// Setup for the tests that render in jsdom.
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, beforeAll } from 'vitest';

// jsdom has no layout engine. MUI X charts and the data grid measure their container with
// ResizeObserver, and MUI reads media queries, so both get inert stand-ins.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub;

if (!window.matchMedia) {
  window.matchMedia = (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener() {},
    removeListener() {},
    addEventListener() {},
    removeEventListener() {},
    dispatchEvent: () => false,
  });
}

// The device page scrolls its live table to the newest row.
Element.prototype.scrollIntoView ??= function scrollIntoView() {};

let i18n;

beforeAll(async () => {
  ({ default: i18n } = await import('../../src/i18n'));
  await i18n.changeLanguage('en');
});

afterEach(async () => {
  cleanup();
  window.localStorage.clear();
  // A test that switches the language must not change it for the next one.
  if (i18n.language !== 'en') {
    await i18n.changeLanguage('en');
  }
});
