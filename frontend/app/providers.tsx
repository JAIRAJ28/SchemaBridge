"use client";

import { useEffect } from "react";
import { Provider } from "react-redux";
import { restoreWorkflow, store } from "../lib/store";

const STORAGE_KEY = "schemabridge-workflow-v2";
const TOKEN_KEY = "schemabridge-access-token";

export default function Providers({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        store.dispatch(restoreWorkflow({
          ...JSON.parse(saved),
          accessToken: sessionStorage.getItem(TOKEN_KEY),
        }));
      } catch {
        localStorage.removeItem(STORAGE_KEY);
      }
    }

    return store.subscribe(() => {
      const workflow = store.getState().workflow;
      const { accessToken, ...safeWorkflow } = workflow;
      localStorage.setItem(STORAGE_KEY, JSON.stringify(safeWorkflow));
      if (accessToken) sessionStorage.setItem(TOKEN_KEY, accessToken);
      else sessionStorage.removeItem(TOKEN_KEY);
    });
  }, []);

  return <Provider store={store}>{children}</Provider>;
}
