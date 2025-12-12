import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js";

const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
);

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

Deno.serve(async (req) => {
  try {
    if (req.method !== "POST") {
      return jsonResponse({ error: "Method not allowed" }, 405);
    }

    const body = await req.json().catch(() => null);
    if (!body || typeof body !== "object") {
      return jsonResponse({ error: "Invalid JSON body" }, 400);
    }

    const {
      query,
      embedding,
      page,
      page_size,
      conference,
      year,
      status,
      keywords,
    } = body as {
      query?: string | null;
      embedding?: number[] | null;
      page?: number;
      page_size?: number;
      conference?: string[] | null;
      year?: number[] | null;
      status?: string[] | null;
      keywords?: string[] | null;
    };

    if (query !== undefined && query !== null && typeof query !== "string") {
      return jsonResponse({ error: "query must be a string" }, 400);
    }
    if (embedding !== undefined && embedding !== null && !Array.isArray(embedding)) {
      return jsonResponse({ error: "embedding must be an array of numbers" }, 400);
    }
    if (embedding && embedding.length !== 1536) {
      return jsonResponse(
        { error: `embedding length must be 1536, got ${embedding.length}` },
        400
      );
    }
    if (conference !== undefined && conference !== null && !Array.isArray(conference)) {
      return jsonResponse({ error: "conference must be an array of strings" }, 400);
    }
    if (year !== undefined && year !== null && !Array.isArray(year)) {
      return jsonResponse({ error: "year must be an array of numbers" }, 400);
    }
    if (status !== undefined && status !== null && !Array.isArray(status)) {
      return jsonResponse({ error: "status must be an array of strings" }, 400);
    }
    if (keywords !== undefined && keywords !== null && !Array.isArray(keywords)) {
      return jsonResponse({ error: "keywords must be an array of strings" }, 400);
    }

    const effectivePage =
      typeof page === "number" && page > 0 ? Math.floor(page) : 1;
    const effectivePageSize =
      typeof page_size === "number" && page_size > 0
        ? Math.floor(page_size)
        : 20;

    const from = (effectivePage - 1) * effectivePageSize;
    const to = from + effectivePageSize - 1;

    // Prefer embedding search when embedding is provided; otherwise use text search.
    if (embedding) {
      const { data, error } = await supabase.rpc("search_papers_by_embedding", {
        input_embedding: embedding,
        filter_conference: conference ?? null,
        filter_year: year ?? null,
        filter_status: status ?? null,
        filter_keywords: keywords ?? null,
        offset_rows: from,
        limit_rows: effectivePageSize,
      });

      if (error) {
        return jsonResponse({ error: error.message }, 500);
      }

      const rows = Array.isArray(data) ? data : [];
      const total = rows[0]?.total_count ?? rows.length ?? 0;

      return jsonResponse({
        data: rows.map((r) => {
          const { total_count, ...rest } = r as Record<string, unknown>;
          return rest;
        }),
        count: total,
        page: effectivePage,
        page_size: effectivePageSize,
      });
    }

    // Text search fallback.
    const trimmedQuery = typeof query === "string" ? query.trim() : "";
    const useQuery = trimmedQuery
      .replace(/[(),]/g, " ")
      .replace(/\s+/g, " ")
      .trim();

    let qb = supabase
      .from("paper_embeddings")
      .select(
        "id,paper_uid,conference,year,status,title,keywords,summary,raw_excerpt,data,created_at",
        { count: "exact" }
      );

    if (useQuery) {
      const pattern = `%${useQuery}%`;
      qb = qb.or(
        `title.ilike.${pattern},summary.ilike.${pattern},raw_excerpt.ilike.${pattern}`
      );
    }

    if (conference && conference.length > 0) {
      qb = qb.in("conference", conference);
    }
    if (year && year.length > 0) {
      qb = qb.in("year", year);
    }
    if (status && status.length > 0) {
      qb = qb.in("status", status);
    }
    if (keywords && keywords.length > 0) {
      qb = qb.overlaps("keywords", keywords);
    }

    qb = qb
      .order("year", { ascending: false })
      .order("created_at", { ascending: false })
      .range(from, to);

    const { data, error, count } = await qb;

    if (error) {
      return jsonResponse({ error: error.message }, 500);
    }

    return jsonResponse({
      data: data ?? [],
      count: count ?? 0,
      page: effectivePage,
      page_size: effectivePageSize,
    });
  } catch (err) {
    return jsonResponse({ error: (err as Error).message }, 500);
  }
});

/* To invoke locally:

  1. Run `supabase start` (see: https://supabase.com/docs/reference/cli/supabase-start)
  2. Make an HTTP request:

  curl -i --location --request POST 'http://127.0.0.1:54321/functions/v1/search_papers' \
    --header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0' \
    --header 'Content-Type: application/json' \
    --data '{
      "query": "diffusion",
      "page": 1,
      "page_size": 20,
      "conference": ["ICLR", "NeurIPS"],
      "year": [2023, 2024],
      "status": ["highlight"],
      "keywords": ["vision", "diffusion"]
    }'

*/
