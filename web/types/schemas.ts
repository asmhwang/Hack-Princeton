import { z } from "zod";

const decimalString = z.union([z.string(), z.number()]).transform((value) => String(value));

export const sourceCategorySchema = z.enum([
  "news",
  "weather",
  "policy",
  "logistics",
  "macro",
  "industrial",
]);

export const signalSchema = z
  .object({
    id: z.string(),
    source_category: sourceCategorySchema,
    title: z.string(),
    region: z.string(),
    severity: z.number().int().min(1).max(5),
    detected_at: z.string().optional(),
    first_seen_at: z.string().optional(),
    source_url: z.string().url().optional().nullable(),
  })
  .strict();

export const disruptionSchema = z
  .object({
    id: z.string(),
    title: z.string(),
    category: sourceCategorySchema,
    region: z.string(),
    severity: z.number().int().min(1).max(5),
    status: z.enum(["active", "monitoring", "resolved"]).default("active"),
    detected_at: z.string().optional(),
    first_seen_at: z.string().optional(),
    last_seen_at: z.string().optional(),
    summary: z.string().optional().nullable(),
    total_exposure: decimalString.default("0"),
    affected_shipments_count: z.number().int().nonnegative().default(0),
    lat: z.number().optional().nullable(),
    lng: z.number().optional().nullable(),
    radius_km: decimalString.optional().nullable(),
  })
  .strict();

export const affectedShipmentSchema = z
  .object({
    shipment_id: z.string(),
    sku: z.string(),
    customer_name: z.string(),
    po_number: z.string(),
    origin: z.string(),
    destination: z.string(),
    exposure: decimalString,
    eta: z.string().optional().nullable(),
    days_to_sla_breach: z.number().optional().nullable(),
    status: z.string(),
    origin_lat: z.number().optional().nullable(),
    origin_lng: z.number().optional().nullable(),
    destination_lat: z.number().optional().nullable(),
    destination_lng: z.number().optional().nullable(),
  })
  .strict();

export const impactReportSchema = z
  .object({
    id: z.string(),
    disruption_id: z.string(),
    total_exposure: decimalString,
    units_at_risk: z.number().int().nonnegative(),
    cascade_depth: z.number().int().optional().default(1),
    generated_sql: z.string().optional().nullable(),
    sql_executed: z.string().optional().nullable(),
    reasoning_trace: z.record(z.string(), z.unknown()).optional().nullable(),
    affected_shipments: z.array(affectedShipmentSchema).default([]),
    created_at: z.string().optional(),
    generated_at: z.string().optional(),
  })
  .strict();

export const mitigationOptionSchema = z
  .object({
    id: z.string(),
    impact_report_id: z.string(),
    option_type: z.enum([
      "reroute",
      "alternate_supplier",
      "expedite",
      "hold",
      "accept_delay",
      "switch_compliant_supplier",
    ]),
    title: z.string().optional(),
    description: z.string(),
    incremental_cost: decimalString.optional(),
    delta_cost: decimalString.optional(),
    days_saved: z.number().optional(),
    delta_days: z.number().optional(),
    confidence: z.number().min(0).max(1),
    rationale: z.string().optional(),
    status: z.enum(["pending", "approved", "rejected", "dismissed"]).default("pending"),
  })
  .strict();

export const draftCommunicationSchema = z
  .object({
    id: z.string(),
    mitigation_id: z.string(),
    recipient_type: z.enum(["supplier", "customer", "internal"]),
    recipient_contact: z.string(),
    subject: z.string(),
    body: z.string(),
    created_at: z.string(),
    sent_at: z.string().nullable(),
  })
  .strict();

export const activityItemSchema = z
  .object({
    id: z.string(),
    agent: z.enum(["Scout", "Analyst", "Strategist", "System"]),
    message: z.string(),
    created_at: z.string(),
    severity: z.enum(["info", "warning", "critical", "success"]).default("info"),
  })
  .strict();

export const exposureSummarySchema = z
  .object({
    active_count: z.number().int().nonnegative(),
    total_exposure: decimalString,
  })
  .strict();

export const analyticsPointSchema = z
  .object({
    label: z.string(),
    exposure: decimalString,
    count: z.number().int().nonnegative().optional().default(0),
  })
  .strict();

export const analyticsSummarySchema = z
  .object({
    by_customer: z.array(analyticsPointSchema).default([]),
    by_sku: z.array(analyticsPointSchema).default([]),
    by_quarter: z.array(analyticsPointSchema).default([]),
  })
  .strict();

export const wsEventSchema = z.discriminatedUnion("channel", [
  z
    .object({
      channel: z.literal("new_signal"),
      payload: z.object({ id: z.string(), source_category: z.string() }).strict(),
    })
    .strict(),
  z
    .object({
      channel: z.literal("new_disruption"),
      payload: z.object({ id: z.string(), severity: z.number().int() }).strict(),
    })
    .strict(),
  z
    .object({
      channel: z.literal("new_impact"),
      payload: z
        .object({ id: z.string(), disruption_id: z.string(), total_exposure: decimalString })
        .strict(),
    })
    .strict(),
  z
    .object({
      channel: z.literal("new_mitigation"),
      payload: z.object({ id: z.string(), impact_report_id: z.string() }).strict(),
    })
    .strict(),
  z
    .object({
      channel: z.literal("new_approval"),
      payload: z.object({ id: z.string(), mitigation_id: z.string() }).strict(),
    })
    .strict(),
]);

export type SourceCategory = z.infer<typeof sourceCategorySchema>;
export type Signal = z.infer<typeof signalSchema>;
export type Disruption = z.infer<typeof disruptionSchema>;
export type AffectedShipment = z.infer<typeof affectedShipmentSchema>;
export type ImpactReport = z.infer<typeof impactReportSchema>;
export type MitigationOption = z.infer<typeof mitigationOptionSchema>;
export type DraftCommunication = z.infer<typeof draftCommunicationSchema>;
export type ActivityItem = z.infer<typeof activityItemSchema>;
export type ExposureSummary = z.infer<typeof exposureSummarySchema>;
export type AnalyticsPoint = z.infer<typeof analyticsPointSchema>;
export type AnalyticsSummary = z.infer<typeof analyticsSummarySchema>;
export type WsEvent = z.infer<typeof wsEventSchema>;
