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
    const body = await req.json().catch(() => null);
    if (!body || typeof body !== "object") {
      return jsonResponse({ error: "Invalid JSON body" }, 400);
    }

    const {
      user_id,
      page,
      page_size,
      alpha,
      beta,
      conference,
      year,
      status,
      keywords,
    } = body as {
      user_id?: string;
      page?: number;
      page_size?: number;
      alpha?: number;
      beta?: number;
      conference?: string[] | null;
      year?: number[] | null;
      status?: string[] | null;
      keywords?: string[] | null;
    };

    if (!user_id || typeof user_id !== "string" || !user_id.trim()) {
      return jsonResponse({ error: "user_id is required" }, 400);
    }

    const effectivePage = typeof page === "number" && page > 0 ? page : 1;
    const effectivePageSize =
      typeof page_size === "number" && page_size > 0 ? page_size : 20;
    const effectiveAlpha = typeof alpha === "number" ? alpha : 0.85;
    const effectiveBeta = typeof beta === "number" ? beta : 0.15;

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

    const hasFilters =
      (conference?.length ?? 0) > 0 ||
      (year?.length ?? 0) > 0 ||
      (status?.length ?? 0) > 0 ||
      (keywords?.length ?? 0) > 0;

    const rpcName = hasFilters
      ? "recommend_papers_hybrid"
      : "recommend_papers_hybrid_no_filter";

    const payload = hasFilters
      ? {
          uid: user_id,
          page: effectivePage,
          page_size: effectivePageSize,
          alpha: effectiveAlpha,
          beta: effectiveBeta,
          filter_conference: conference ?? null,
          filter_year: year ?? null,
          filter_status: status ?? null,
          filter_keywords: keywords ?? null,
        }
      : {
          uid: user_id,
          page: effectivePage,
          page_size: effectivePageSize,
          alpha: effectiveAlpha,
          beta: effectiveBeta,
        };

    const { data, error } = await supabase.rpc(rpcName, payload);

    if (error) {
      return jsonResponse({ error: error.message }, 500);
    }

    return jsonResponse(data);
  } catch (err) {
    return jsonResponse({ error: err.message }, 500);
  }
});


/* To invoke locally:

  1. Run `supabase start` (see: https://supabase.com/docs/reference/cli/supabase-start)
  2. Make an HTTP request:

  curl -i --location --request POST 'http://127.0.0.1:54321/functions/v1/recommend_papers' \
    --header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0' \
    --header 'Content-Type: application/json' \
    --data '{"name":"Functions"}'

*/
