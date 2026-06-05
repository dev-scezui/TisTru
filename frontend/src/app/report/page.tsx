import { Suspense } from "react";
import ReportClient from "./[id]/ReportClient";

export default function ReportPage() {
  return (
    <Suspense fallback={<div className="shell">Loading...</div>}>
      <ReportClient />
    </Suspense>
  );
}
