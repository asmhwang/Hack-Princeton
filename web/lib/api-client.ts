"use client";

import type { z } from "zod";
import { z as zod } from "zod";
import type { paths } from "@/types/api";
import {
  activeRouteSchema,
  activityItemSchema,
  analyticsSummarySchema,
  draftCommunicationSchema,
  disruptionSchema,
  exposureSummarySchema,
  impactReportSchema,
  mitigationOptionSchema,
  signalSchema,
  type ActiveRoute,
  type ActivityItem,
  type AnalyticsSummary,
  type DraftCommunication,
  type Disruption,
  type ExposureSummary,
  type ImpactReport,
  type MitigationOption,
  type Signal,
} from "@/types/schemas";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// Stream 1 dev fallback. Remove once Stream 2 ships /api/disruptions/active/routes.
const MOCK_ACTIVE_ROUTES: ActiveRoute[] = [
  {
    id: "MOCK-TYPH-1",
    disruption_id: "00000000-0000-0000-0000-000000000001",
    disruption_category: "weather",
    from: [22.54, 114.06],
    to: [34.05, -118.24],
    origin_name: "Shenzhen",
    destination_name: "Los Angeles",
    mode: "ocean",
    status: "blocked",
    exposure: "840000",
    transit_days: 14,
    carrier: "COSCO",
  },
  {
    id: "MOCK-BUSA-1",
    disruption_id: "00000000-0000-0000-0000-000000000002",
    disruption_category: "logistics",
    from: [35.1, 129.03],
    to: [47.61, -122.33],
    origin_name: "Busan",
    destination_name: "Seattle",
    mode: "ocean",
    status: "watch",
    exposure: "610000",
    transit_days: 11,
    carrier: "HMM",
  },
  {
    id: "MOCK-REDS-1",
    disruption_id: "00000000-0000-0000-0000-000000000003",
    disruption_category: "policy",
    from: [1.35, 103.82],
    to: [51.92, 4.48],
    origin_name: "Singapore",
    destination_name: "Rotterdam",
    mode: "ocean",
    status: "blocked",
    exposure: "1500000",
    transit_days: 28,
    carrier: "Maersk",
  },
  {
    id: "MOCK-LUXS-1",
    disruption_id: "00000000-0000-0000-0000-000000000004",
    disruption_category: "news",
    from: [31.39, 120.93],
    to: [22.32, 114.17],
    origin_name: "Kunshan",
    destination_name: "Hong Kong",
    mode: "truck",
    status: "watch",
    exposure: "1060000",
    transit_days: 2,
    carrier: "XPO Logistics",
  },
  {
    id: "MOCK-CBAM-1",
    disruption_id: "00000000-0000-0000-0000-000000000005",
    disruption_category: "policy",
    from: [31.23, 121.47],
    to: [51.92, 4.48],
    origin_name: "Shanghai",
    destination_name: "Rotterdam",
    mode: "rail",
    status: "good",
    exposure: "520000",
    transit_days: 18,
    carrier: "UTLC ERA",
  },
];

type HealthResponse =
  paths["/health"]["get"]["responses"]["200"]["content"]["application/json"];

class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  fallback: T,
  init?: RequestInit,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        // Bypass ngrok free-tier browser interstitial. No-op when the backend
        // isn't behind ngrok — safe to keep on every request.
        "ngrok-skip-browser-warning": "true",
        ...init?.headers,
      },
    });
  } catch (error) {
    if (error instanceof TypeError) {
      return fallback;
    }
    throw error;
  }

  if (response.status === 404) {
    return fallback;
  }

  if (!response.ok) {
    throw new ApiError(`Request failed: ${path}`, response.status);
  }

  return schema.parse(await response.json());
}

export const apiClient = {
  async health(): Promise<HealthResponse> {
    return request("/health", zod.record(zod.string(), zod.string()), {
      status: "unavailable",
    });
  },

  listSignals(): Promise<Signal[]> {
    return request("/api/signals", signalSchema.array(), []);
  },

  listDisruptions(status = "active"): Promise<Disruption[]> {
    return request(`/api/disruptions?status=${encodeURIComponent(status)}`, disruptionSchema.array(), []);
  },

  getDisruption(id: string): Promise<Disruption | null> {
    return request(`/api/disruptions/${id}`, disruptionSchema.nullable(), null);
  },

  getImpact(disruptionId: string): Promise<ImpactReport | null> {
    return request(`/api/disruptions/${disruptionId}/impact`, impactReportSchema.nullable(), null);
  },

  getMitigations(disruptionId: string): Promise<MitigationOption[]> {
    return request(`/api/disruptions/${disruptionId}/mitigations`, mitigationOptionSchema.array(), []);
  },

  // Stream 1 contract — Stream 2 backend adds the real endpoint.
  // While the endpoint is missing (returns 404 and our `request` helper falls
  // back to `[]`) we hand-roll a small list so the globe renders real-shaped
  // data during dev. TODO: remove the mock fallback once
  // GET /api/disruptions/active/routes ships.
  async getActiveRoutes(): Promise<ActiveRoute[]> {
    const real = await request(
      "/api/disruptions/active/routes",
      activeRouteSchema.array(),
      [] as ActiveRoute[],
    );
    return real.length > 0 ? real : MOCK_ACTIVE_ROUTES;
  },

  getDrafts(mitigationId: string): Promise<DraftCommunication[]> {
    return request(`/api/mitigations/${mitigationId}/drafts`, draftCommunicationSchema.array(), []);
  },

  getActivityFeed(): Promise<ActivityItem[]> {
    return request("/api/activity/feed", activityItemSchema.array(), []);
  },

  getExposureSummary(): Promise<ExposureSummary> {
    return request("/api/analytics/exposure/summary", exposureSummarySchema, {
      active_count: 0,
      total_exposure: "0",
    });
  },

  getAnalytics(): Promise<AnalyticsSummary> {
    return request("/api/analytics/exposure/breakdown", analyticsSummarySchema, {
      by_customer: [],
      by_sku: [],
      by_quarter: [],
    });
  },

  async deleteDisruption(disruptionId: string): Promise<void> {
    await request(
      `/api/disruptions/${disruptionId}`,
      zod.object({}).passthrough(),
      {},
      { method: "DELETE" },
    );
  },

  async approveMitigation(mitigationId: string): Promise<void> {
    await request(
      `/api/mitigations/${mitigationId}/approve`,
      zod.object({}).passthrough(),
      {},
      { method: "POST", body: JSON.stringify({}) },
    );
  },

  async simulate(scenario: string): Promise<void> {
    await request(
      "/api/dev/simulate",
      zod.object({ ok: zod.boolean().optional() }).passthrough(),
      {},
      {
        method: "POST",
        body: JSON.stringify({ scenario }),
      },
    );
  },
};

export { ApiError };
