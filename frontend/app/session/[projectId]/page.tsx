import Workspace from "@/components/Workspace";

export default async function SessionPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  return <Workspace initialProjectId={projectId} />;
}
