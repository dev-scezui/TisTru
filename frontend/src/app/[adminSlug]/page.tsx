import { notFound } from "next/navigation";
import { isAdminSlug } from "../../lib/adminPath";
import AdminDashboard from "./AdminDashboard";

type PageProps = {
  params: Promise<{ adminSlug: string }> | { adminSlug: string };
};

export default async function AdminSlugPage({ params }: PageProps) {
  const resolved = await Promise.resolve(params);
  if (!isAdminSlug(resolved.adminSlug)) {
    notFound();
  }
  return <AdminDashboard />;
}
