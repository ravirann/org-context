import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";

/* ------------------------------- jsdom polyfills ------------------------------ */

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
vi.stubGlobal("ResizeObserver", ResizeObserverStub);

class IntersectionObserverStub {
  readonly root = null;
  readonly rootMargin = "";
  readonly thresholds: number[] = [];
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
}
vi.stubGlobal("IntersectionObserver", IntersectionObserverStub);

window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
Element.prototype.scrollIntoView = vi.fn();

/* --------------------------------- test hygiene ------------------------------- */

afterEach(() => {
  // Drop per-test fetch stubs (mockFetchRoutes/mockFetchOnce) but keep the
  // polyfills above (they were installed before this hook registers and are
  // re-stubbed here for safety).
  vi.unstubAllGlobals();
  vi.stubGlobal("ResizeObserver", ResizeObserverStub);
  vi.stubGlobal("IntersectionObserver", IntersectionObserverStub);

  // Reset persisted state and theme side effects between tests.
  window.localStorage.clear();
  document.documentElement.classList.remove("dark");
});
