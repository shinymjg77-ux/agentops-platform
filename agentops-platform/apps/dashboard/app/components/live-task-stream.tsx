"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

export default function LiveTaskStream() {
  const router = useRouter();
  const refreshTimerRef = useRef<number | null>(null);

  useEffect(() => {
    const eventSource = new EventSource("/api/stream/tasks");

    const scheduleRefresh = () => {
      if (refreshTimerRef.current !== null) {
        window.clearTimeout(refreshTimerRef.current);
      }
      refreshTimerRef.current = window.setTimeout(() => {
        router.refresh();
      }, 300);
    };

    eventSource.addEventListener("task_update", scheduleRefresh);

    return () => {
      eventSource.removeEventListener("task_update", scheduleRefresh);
      eventSource.close();
      if (refreshTimerRef.current !== null) {
        window.clearTimeout(refreshTimerRef.current);
      }
    };
  }, [router]);

  return null;
}
