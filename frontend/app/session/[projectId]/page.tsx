import type { Metadata } from "next";
import Workspace from "@/components/Workspace";
import { getProject } from "@/lib/api-client";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ projectId: string }>;
}): Promise<Metadata> {
  const { projectId } = await params;
  try {
    const state = await getProject(projectId);
    const title = state?.north_star?.title?.trim();
    if (title) return { title: `${title} · MyThinking` };
  } catch {
    // fall through to the default title
  }
  return { title: "MyThinking" };
}

export default async function SessionPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  return <Workspace initialProjectId={projectId} />;
}
