import type {
  CompareRequest,
  CompareResponse,
  HeatmapRequest,
  HeatmapResponse,
  ImpliedVolRequest,
  ImpliedVolResponse,
  MetaResponse,
  PriceRequest,
  PriceResponse,
  ProfileRequest,
  ProfileResponse,
} from "./types";

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

function post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(body), ...(signal ? { signal } : {}) });
}

export interface Timed<T> {
  data: T;
  roundTripMs: number;
}

export async function postPrice(req: PriceRequest, signal?: AbortSignal): Promise<Timed<PriceResponse>> {
  const t0 = performance.now();
  const data = await post<PriceResponse>("/api/price", req, signal);
  return { data, roundTripMs: performance.now() - t0 };
}

export const postProfile = (req: ProfileRequest, signal?: AbortSignal) =>
  post<ProfileResponse>("/api/profile", req, signal);

export const postHeatmap = (req: HeatmapRequest, signal?: AbortSignal) =>
  post<HeatmapResponse>("/api/heatmap", req, signal);

export const postCompare = (req: CompareRequest, signal?: AbortSignal) =>
  post<CompareResponse>("/api/compare", req, signal);

export const postImpliedVol = (req: ImpliedVolRequest, signal?: AbortSignal) =>
  post<ImpliedVolResponse>("/api/implied-vol", req, signal);

export function getMeta(signal?: AbortSignal): Promise<MetaResponse> {
  return request<MetaResponse>("/api/meta", signal ? { signal } : {});
}
