"use client";

import { usePathname } from "next/navigation";
import React from "react";
import { trackPageview } from "../lib/pageview";

export default function PageviewBeacon() {
  const pathname = usePathname();

  React.useEffect(() => {
    if (!pathname) return;
    trackPageview(pathname);
  }, [pathname]);

  return null;
}
