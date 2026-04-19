"use client";

import type { z } from "zod";
import { z as zod } from "zod";
import type { paths } from "@/types/api";
import {
  activityItemSchema,
  analyticsSummarySchema,
  draftCommunicationSchema,
  disruptionSchema,
  exposureSummarySchema,
  impactReportSchema,
  mitigationOptionSchema,
  signalSchema,
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
