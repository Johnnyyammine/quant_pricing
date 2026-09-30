import type { MetaResponse, PriceRequest, PriceResponse } from "./types";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface ErrorBody {
  detail?: string | { loc: (string | number)[]; msg: string }[];
}

function describe(body: ErrorBody, status: number): string {
  const d = body.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d.length > 0) {
    return d.map((e) => `${e.loc.slice(1).join(".")}: ${e.msg}`).join("; ");
  }
  return `HTTP ${status}`;
}

async function request<T>(path: string, init: Omit<RequestInit, "headers"> = {}): Promise<T> {
  const res = await fetch(path, { ...init, headers: { "Content-Type": "application/json" } });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as ErrorBody;
    throw new ApiError(res.status, describe(body, res.status));
  }
  return (await res.json()) as T;
}

export interface Timed<T> {
  data: T;
  roundTripMs: number;
}

export async function postPrice(req: PriceRequest, signal?: AbortSignal): Promise<Timed<PriceResponse>> {
  const t0 = performance.now();
  const data = await request<PriceResponse>("/api/price", {
    method: "POST",
    body: JSON.stringify(req),
    ...(signal ? { signal } : {}),
  });
  return { data, roundTripMs: performance.now() - t0 };
}

export function getMeta(signal?: AbortSignal): Promise<MetaResponse> {
  return request<MetaResponse>("/api/meta", signal ? { signal } : {});
}
