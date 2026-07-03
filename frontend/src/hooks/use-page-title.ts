import { useEffect } from "react";

const APP_NAME = "Org Context";

/** Sets `document.title` to "<title> · Org Context" while mounted. */
export function usePageTitle(title?: string): void {
  useEffect(() => {
    document.title = title ? `${title} · ${APP_NAME}` : APP_NAME;
    return () => {
      document.title = APP_NAME;
    };
  }, [title]);
}
