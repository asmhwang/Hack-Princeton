import { DisruptionDetailView } from "@/components/disruption/DisruptionDetailView";

type DisruptionPageProps = {
  params: Promise<{ id: string }>;
};

export default async function DisruptionPage({ params }: DisruptionPageProps) {
  const { id } = await params;
  return <DisruptionDetailView disruptionId={id} />;
}
