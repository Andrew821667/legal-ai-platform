"use client";

import { useEffect, useState } from "react";

import ClientCases from "@/components/miniapp/pages/ClientCases";

import CabinetIntakeForm from "./CabinetIntakeForm";

type MeResponse = { signed_in: boolean; profile?: { username?: string | null } | null };

export default function CabinetHome() {
  const [prefillContact, setPrefillContact] = useState<string | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/client/me", { cache: "no-store" })
      .then((response) => (response.ok ? (response.json() as Promise<MeResponse>) : null))
      .then((data) => {
        const username = data?.profile?.username;
        if (!cancelled && username) setPrefillContact(`@${username}`);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <ClientCases
      variant="site"
      emptyState={(onCreated) => <CabinetIntakeForm prefillContact={prefillContact} onCreated={onCreated} />}
    />
  );
}
