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

    const { paper_uid, embedding, threshold, match_count } = body as {
      paper_uid?: string;
      embedding?: number[];
      threshold?: number;
      match_count?: number;
    };

    if (!paper_uid && !embedding) {
      return jsonResponse(
        { error: "Either paper_uid or embedding is required" },
        400
      );
    }

    const effectiveThreshold =
      typeof threshold === "number" ? threshold : 0.4;
    const effectiveMatchCount =
      typeof match_count === "number" && match_count > 0
        ? match_count
        : 20;
    const rpcMatchCount = effectiveMatchCount + 1; // over-fetch to drop self-match

    if (embedding !== undefined) {
      if (!Array.isArray(embedding)) {
        return jsonResponse({ error: "embedding must be an array" }, 400);
      }
      if (embedding.length !== 1536) {
        return jsonResponse(
          { error: `embedding length must be 1536, got ${embedding.length}` },
          400
        );
      }

      const { data, error } = await supabase.rpc("match_papers_by_embedding", {
        input_embedding: embedding,
        threshold: effectiveThreshold,
        match_count: rpcMatchCount,
      });

      if (error) {
        return jsonResponse({ error: error.message }, 500);
      }

      const filtered =
        Array.isArray(data)
          ? data
              .filter(
                (row) =>
                  !(
                    row &&
                    typeof (row as { distance?: unknown }).distance === "number" &&
                    (row as { distance?: number }).distance === 0
                  )
              )
              .slice(0, effectiveMatchCount)
          : data;

      return jsonResponse(filtered);
    }

    if (!paper_uid || typeof paper_uid !== "string" || !paper_uid.trim()) {
      return jsonResponse(
        { error: "paper_uid must be a non-empty string" },
        400
      );
    }

    const { data, error } = await supabase.rpc("match_papers_by_id", {
      input_paper_uid: paper_uid,
      threshold: effectiveThreshold,
      match_count: rpcMatchCount,
    });

    if (error) {
      return jsonResponse({ error: error.message }, 500);
    }

    const filtered =
      Array.isArray(data)
        ? data
            .filter(
              (row) =>
                !(
                  row &&
                  typeof (row as { distance?: unknown }).distance === "number" &&
                  (row as { distance?: number }).distance === 0
                )
            )
            .slice(0, effectiveMatchCount)
        : data;

    return jsonResponse(filtered);
  } catch (err) {
    return jsonResponse({ error: err.message }, 500);
  }
});
