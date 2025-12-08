import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js";

const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
);

const CACHE_KEY = "filter_options";
const TTL_MS = 7 * 24 * 60 * 60 * 1000; // 1 week

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const sortStrings = (values: Iterable<string>) =>
  Array.from(new Set(values))
    .filter((v) => typeof v === "string" && v.trim().length > 0)
    .sort((a, b) => a.localeCompare(b));

const sortNumbers = (values: Iterable<number>) =>
  Array.from(new Set(values))
    .filter((v) => typeof v === "number" && !Number.isNaN(v))
    .sort((a, b) => a - b);

async function getCachedOptions() {
  const nowIso = new Date().toISOString();
  const { data, error } = await supabase
    .from("kv_store_ttl")
    .select("value, expires_at")
    .eq("key", CACHE_KEY)
    .or(`expires_at.is.null,expires_at.gt.${nowIso}`)
    .limit(1);

  if (error) {
    console.error("kv_store_ttl fetch error", error);
    return null;
  }

  const row = data?.[0];
  if (!row) return null;

  const raw = (row as { value?: unknown }).value;
  if (raw === undefined || raw === null) return null;

  try {
    return typeof raw === "string" ? JSON.parse(raw) : raw;
  } catch (err) {
    console.error("cache parse error", err);
    return null;
  }
}

async function computeOptions() {
  const { data, error } = await supabase
    .from("paper_embeddings")
    .select("conference, year, status, keywords");

  if (error) {
    throw new Error(`paper_embeddings query failed: ${error.message}`);
  }

  const conferences = new Set<string>();
  const years = new Set<number>();
  const statuses = new Set<string>();
  const keywords = new Set<string>();

  for (const row of data ?? []) {
    const r = row as {
      conference?: string;
      year?: number;
      status?: string | null;
      keywords?: string[] | null;
    };
    if (r.conference) conferences.add(r.conference);
    if (typeof r.year === "number") years.add(r.year);
    if (r.status) statuses.add(r.status);
    if (Array.isArray(r.keywords)) {
      for (const kw of r.keywords) {
        if (kw) keywords.add(kw);
      }
    }
  }

  return {
    conference: sortStrings(conferences),
    year: sortNumbers(years),
    status: sortStrings(statuses),
    keywords: sortStrings(keywords),
  };
}

async function cacheOptions(value: unknown) {
  const expiresAt = new Date(Date.now() + TTL_MS).toISOString();
  const payload: Record<string, unknown> = {
    key: CACHE_KEY,
    value,
    expires_at: expiresAt,
    updated_at: new Date().toISOString(),
  };

  const { error } = await supabase
    .from("kv_store_ttl")
    .upsert(payload, { onConflict: "key", returning: "minimal" });

  if (error) {
    throw new Error(`kv_store_ttl upsert failed: ${error.message}`);
  }
}

Deno.serve(async () => {
  try {
    const cached = await getCachedOptions();
    if (cached) {
      return jsonResponse({ data: cached });
    }

    const computed = await computeOptions();
    await cacheOptions(computed);
    return jsonResponse({ data: computed });
  } catch (err) {
    return jsonResponse({ error: (err as Error).message }, 500);
  }
});
