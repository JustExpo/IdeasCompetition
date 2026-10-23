import { useSyncExternalStore } from "react";

import { isE2EMode, subscribeToBuildChange } from "../../api";

/** В тестовом стенде e2e (часы переводятся вручную) страница честно говорит, где открыта. */
export function E2EBadge() {
  const active = useSyncExternalStore(subscribeToBuildChange, isE2EMode);
  if (!active) {
    return null;
  }
  return (
    <p className="e2e-badge" role="status">
      E2E MODE
    </p>
  );
}
