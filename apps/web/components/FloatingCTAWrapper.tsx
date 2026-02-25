"use client";

import dynamic from "next/dynamic";

const FloatingCTA = dynamic(() => import("./FloatingCTA"), {
  ssr: false,
});

export default function FloatingCTAWrapper() {
  return <FloatingCTA />;
}
