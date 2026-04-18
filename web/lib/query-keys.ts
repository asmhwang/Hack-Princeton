export const queryKeys = {
  signals: ["signals"] as const,
  disruptions: (status = "active") => ["disruptions", status] as const,
  disruption: (id: string) => ["disruption", id] as const,
  impact: (disruptionId: string) => ["impact", disruptionId] as const,
  mitigations: (disruptionId: string) => ["mitigations", disruptionId] as const,
  drafts: (mitigationId: string) => ["drafts", mitigationId] as const,
  activity: ["activity"] as const,
  exposure: ["analytics", "exposure"] as const,
  analytics: ["analytics"] as const,
};
