import "server-only";

import { cookies } from "next/headers";
import { notFound, redirect } from "next/navigation";

const API_URL = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
const SESSION_COOKIE = "condoos_session";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

/** Server-side call to the API, forwarding the user's session cookie. */
export async function apiGet<T>(path: string): Promise<T> {
  const store = await cookies();
  const session = store.get(SESSION_COOKIE)?.value;
  const res = await fetch(`${API_URL}${path}`, {
    headers: session ? { cookie: `${SESSION_COOKIE}=${session}` } : {},
    cache: "no-store",
  });
  if (res.status === 401) redirect("/login");
  // Other tenants' data and missing records look the same: "not found", nothing revealed.
  if (res.status === 404 || res.status === 403) notFound();
  if (!res.ok) throw new ApiError(res.status, `API ${res.status} em ${path}`);
  return (await res.json()) as T;
}
