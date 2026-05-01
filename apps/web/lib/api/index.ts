/**
 * Praetor API client.
 *
 * Shape matches the REST surface in master plan §2.3. This implementation
 * Uses an explicit data source:
 * - NEXT_PUBLIC_DATA_SOURCE=fixtures: frontend-only demo data, no API calls.
 * - NEXT_PUBLIC_DATA_SOURCE=api: production API only, no fixture fallbacks.
 * - NEXT_PUBLIC_DATA_SOURCE=hybrid: API with fixture fallback for local demos.
 *
 * The client is intentionally narrow — every page in this app calls through
 * a named export here, so swapping in real I/O is one diff.
 */

import {
  alerts as fxAlerts,
  approvals as fxApprovals,
  assets as fxAssets,
  auditPackets as fxAuditPackets,
  controls as fxControls,
  corpora as fxCorpora,
  documentChunks as fxChunks,
  evidenceRecords as fxEvidence,
  events as fxEvents,
  findings as fxFindings,
  hookCalls as fxHookCalls,
  hooks as fxHooks,
  obligations as fxObligations,
  policyDecisions as fxPolicy,
  praetorDocuments as fxDocs,
  proposedChanges as fxProposals,
  sandboxRuns as fxSandboxes,
  workflowRuns as fxRuns,
  workflows as fxWorkflows
} from "./fixtures";

import type {
  AgentEvent,
  Alert,
  Approval,
  Asset,
  AuditPacket,
  Control,
  Corpus,
  DocumentChunk,
  EvidenceRecord,
  Finding,
  Hook,
  HookCall,
  JsonStackCatalogEntry,
  JsonStackManifest,
  JsonStackOpenApiImportRequest,
  JsonStackOpenApiImportResult,
  JsonStackPersistResult,
  JsonStackPreviewRequest,
  JsonStackPreviewResult,
  ModelStreamEvent,
  ModelStreamRequest,
  JsonStackValidateResult,
  Obligation,
  PolicyDecision,
  PraetorDocument,
  ProposedChange,
  SandboxRun,
  StepRun,
  Workflow,
  WorkflowRun
} from "./types";

const LATENCY_MS = 80;
const sleep = (ms = LATENCY_MS) => new Promise<void>((r) => setTimeout(r, ms));

// Browser fetches go to NEXT_PUBLIC_API_BASE (e.g. http://localhost:8000 from
// the host). Server-side fetches inside Docker hit a different name —
// INTERNAL_API_BASE (e.g. http://api:8000 via the compose network).
const PUBLIC_BASE = process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "");
const INTERNAL_BASE = process.env.INTERNAL_API_BASE?.replace(/\/$/, "");
const DATA_SOURCE = (
  process.env.NEXT_PUBLIC_DATA_SOURCE ??
  (process.env.NEXT_PUBLIC_PRAETOR_DATA_MODE === "demo" ? "fixtures" : "api")
).toLowerCase();
const API_BASE =
  typeof window === "undefined"
    ? (INTERNAL_BASE ?? PUBLIC_BASE)
    : PUBLIC_BASE;
const API_TOKEN = process.env.NEXT_PUBLIC_API_TOKEN ?? process.env.NEXT_PUBLIC_DEV_BEARER ?? "dev";
const USE_API = DATA_SOURCE === "api" || DATA_SOURCE === "hybrid";
const USE_FIXTURES = DATA_SOURCE === "fixtures";
const ALLOW_FIXTURE_FALLBACK = DATA_SOURCE === "hybrid";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!API_BASE) throw new Error("NEXT_PUBLIC_API_BASE is not configured");
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${API_TOKEN}`,
      ...(init.headers ?? {})
    }
  });
  if (!response.ok) {
    throw new Error(`Praetor API ${response.status}: ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

async function streamRequest(
  path: string,
  body: unknown,
  onEvent: (event: ModelStreamEvent) => void
): Promise<void> {
  if (!API_BASE) throw new Error("NEXT_PUBLIC_API_BASE is not configured");
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      Authorization: `Bearer ${API_TOKEN}`
    },
    body: JSON.stringify(body)
  });
  if (!response.ok || !response.body) {
    throw new Error(`Praetor API ${response.status}: ${await response.text()}`);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const dataLine = frame.split("\n").find((line) => line.startsWith("data:"));
      if (!dataLine) continue;
      onEvent(JSON.parse(dataLine.slice(5)) as ModelStreamEvent);
    }
  }
}

async function backendOrFixture<T>(path: string, fixture: () => Promise<T>): Promise<T> {
  if (USE_FIXTURES) return fixture();
  if (!USE_API || !API_BASE) {
    if (ALLOW_FIXTURE_FALLBACK) return fixture();
    throw new Error("Praetor API mode requires NEXT_PUBLIC_API_BASE");
  }
  try {
    return await request<T>(path);
  } catch {
    if (ALLOW_FIXTURE_FALLBACK) return fixture();
    throw new Error(`Praetor API request failed for ${path}`);
  }
}

export const api = {
  models: {
    async stream(req: ModelStreamRequest, onEvent: (event: ModelStreamEvent) => void): Promise<void> {
      if (!USE_API) {
        const provider = req.provider ?? "openai";
        const model = req.model ?? "default";
        const text = `[dry-run:${provider}/${model}] ${req.prompt}`;
        onEvent({ type: "start", provider, model });
        for (let index = 0; index < text.length; index += 24) {
          onEvent({ type: "delta", provider, model, text: text.slice(index, index + 24) });
          await sleep(25);
        }
        onEvent({ type: "done", provider, model, text });
        return;
      }
      return streamRequest("/models:stream", req, onEvent);
    }
  },

  // ─── assets / inventory ───────────────────────────────────────────────
  assets: {
    async list(): Promise<Asset[]> {
      if (USE_API) return backendOrFixture<Asset[]>("/assets", async () => {
        await sleep();
        return fxAssets;
      });
      await sleep();
      return fxAssets;
    },
    async get(id: string): Promise<Asset | null> {
      if (USE_API) {
        try {
          return await request<Asset>(`/assets/${encodeURIComponent(id)}`);
        } catch {
          if (ALLOW_FIXTURE_FALLBACK) return fxAssets.find((a) => a.id === id || a.urn === id) ?? null;
          return null;
        }
      }
      await sleep();
      return fxAssets.find((a) => a.id === id || a.urn === id) ?? null;
    },
    async children(parentId: string): Promise<Asset[]> {
      if (USE_API) return backendOrFixture<Asset[]>(`/assets/${encodeURIComponent(parentId)}/children`, async () => {
        await sleep();
        return fxAssets.filter((a) => a.parent_asset_id === parentId);
      });
      await sleep();
      return fxAssets.filter((a) => a.parent_asset_id === parentId);
    }
  },

  // ─── events ───────────────────────────────────────────────────────────
  events: {
    async forAsset(assetId: string, limit = 200): Promise<AgentEvent[]> {
      if (USE_API) return request<AgentEvent[]>(`/events?asset_id=${encodeURIComponent(assetId)}&limit=${limit}`);
      await sleep();
      return fxEvents.filter((e) => e.asset_id === assetId).slice(-limit);
    },
    async forWorkflowRun(runId: string, limit = 200): Promise<AgentEvent[]> {
      if (USE_API) return request<AgentEvent[]>(`/events?workflow_run_id=${encodeURIComponent(runId)}&limit=${limit}`);
      await sleep();
      return fxEvents.filter((e) => e.workflow_run_id === runId).slice(-limit);
    },
    /** All events, newest last — used by the global alerts tray and the live dashboard. */
    async recent(limit = 50): Promise<AgentEvent[]> {
      if (USE_API) return request<AgentEvent[]>(`/events?limit=${limit}`);
      await sleep();
      return fxEvents.slice(-limit);
    }
  },

  // ─── obligations & controls ──────────────────────────────────────────
  obligations: {
    async list(): Promise<Obligation[]> {
      if (USE_API) return backendOrFixture<Obligation[]>("/obligations", async () => {
        await sleep();
        return fxObligations;
      });
      await sleep();
      return fxObligations;
    },
    async byUrn(urn: string): Promise<Obligation | null> {
      if (USE_API) {
        try {
          return await request<Obligation>(`/obligations/${encodeURIComponent(urn)}`);
        } catch {
          if (ALLOW_FIXTURE_FALLBACK) return fxObligations.find((o) => o.urn === urn) ?? null;
          return null;
        }
      }
      await sleep();
      return fxObligations.find((o) => o.urn === urn) ?? null;
    },
    async create(payload: Partial<Obligation> & { framework: string; citation: string; text: string }): Promise<Obligation> {
      if (!USE_API) throw new Error("Creating obligations requires the API data source.");
      return request<Obligation>("/obligations", { method: "POST", body: JSON.stringify(payload) });
    },
    async update(urn: string, patch: Partial<Obligation>): Promise<Obligation> {
      if (!USE_API) throw new Error("Editing obligations requires the API data source.");
      return request<Obligation>(`/obligations/${encodeURIComponent(urn)}`, { method: "PATCH", body: JSON.stringify(patch) });
    },
    async remove(urn: string): Promise<void> {
      if (!USE_API) throw new Error("Deleting obligations requires the API data source.");
      await request<void>(`/obligations/${encodeURIComponent(urn)}`, { method: "DELETE" });
    },
    async importYaml(yamlText: string, framework?: string): Promise<{ created: Obligation[]; updated: Obligation[]; skipped: number }> {
      if (!USE_API) throw new Error("YAML import requires the API data source.");
      return request("/obligations:import-yaml", {
        method: "POST",
        body: JSON.stringify({ yaml: yamlText, framework })
      });
    }
  },
  controls: {
    async list(): Promise<Control[]> {
      if (USE_API) return backendOrFixture<Control[]>("/controls", async () => {
        await sleep();
        return fxControls;
      });
      await sleep();
      return fxControls;
    }
  },

  // ─── workflows & runs ─────────────────────────────────────────────────
  workflows: {
    async list(): Promise<Workflow[]> {
      const rows = await backendOrFixture<Array<Record<string, unknown>>>("/workflows", async () => {
        await sleep();
        return fxWorkflows.map((row) => ({ ...row }));
      });
      return rows.map(normalizeWorkflow);
    },
    async get(id: string): Promise<Workflow | null> {
      if (USE_API) {
        try {
          const row = await request<Record<string, unknown>>(`/workflows/${encodeURIComponent(id)}`);
          return normalizeWorkflow(row);
        } catch {
          if (ALLOW_FIXTURE_FALLBACK) {
            const fixture = fxWorkflows.find((w) => w.id === id || w.urn === id);
            return fixture ? normalizeWorkflow({ ...fixture }) : null;
          }
          return null;
        }
      }
      await sleep();
      const fixture = fxWorkflows.find((w) => w.id === id || w.urn === id);
      return fixture ? normalizeWorkflow({ ...fixture }) : null;
    },
    async run(
      id: string,
      inputs: Record<string, unknown>,
      options: { execution_mode?: "sync" | "queued"; model_provider?: string; model?: string } = {}
    ): Promise<{ workflow_run_id: string }> {
      if (USE_API) {
        return request<{ workflow_run_id: string }>(`/workflows/${encodeURIComponent(id)}:run`, {
          method: "POST",
          body: JSON.stringify({ inputs, ...options })
        });
      }
      await sleep();
      // demo: returns the existing running run id
      return { workflow_run_id: "wfr_2026_04_28_001" };
    },
    async schedule(id: string, payload: {
      inputs: Record<string, unknown>;
      enabled: boolean;
      continuous_monitoring: boolean;
      recurrence: Record<string, unknown>;
      model_provider?: string;
      model?: string;
    }): Promise<Workflow> {
      if (!USE_API) throw new Error("Scheduling workflows requires the API data source.");
      const row = await request<Record<string, unknown>>(`/workflows/${encodeURIComponent(id)}:schedule`, {
        method: "POST",
        body: JSON.stringify(payload)
      });
      return normalizeWorkflow(row);
    },
    async create(payload: {
      name: string;
      id?: string;
      description?: string;
      trigger?: string;
      required_hooks?: string[];
      required_corpora?: string[];
      graph: { nodes: unknown[]; edges: unknown[] };
    }): Promise<Workflow> {
      if (!USE_API) throw new Error("Creating workflows requires the API data source.");
      const row = await request<Record<string, unknown>>("/workflows", { method: "POST", body: JSON.stringify(payload) });
      return normalizeWorkflow(row);
    },
    async update(id: string, patch: Record<string, unknown>): Promise<Workflow> {
      if (!USE_API) throw new Error("Editing workflows requires the API data source.");
      const row = await request<Record<string, unknown>>(`/workflows/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(patch) });
      return normalizeWorkflow(row);
    },
    async remove(id: string): Promise<void> {
      if (!USE_API) throw new Error("Deleting workflows requires the API data source.");
      await request<void>(`/workflows/${encodeURIComponent(id)}`, { method: "DELETE" });
    },
    async nodeCatalog(): Promise<Array<{
      type: string;
      phase: "pre" | "assess" | "post";
      label: string;
      summary: string;
      config_schema: Record<string, string>;
    }>> {
      if (!USE_API) {
        // Local fallback so the editor works in fixture mode too.
        return DEFAULT_NODE_CATALOG;
      }
      try {
        return await request("/workflows/nodes/catalog");
      } catch {
        return DEFAULT_NODE_CATALOG;
      }
    }
  },
  workflowRuns: {
    async list(): Promise<WorkflowRun[]> {
      if (USE_API) {
        try {
          const rows = await request<Array<Record<string, unknown>>>("/workflow-runs");
          return rows.map(normalizeWorkflowRun);
        } catch {
          if (!ALLOW_FIXTURE_FALLBACK) return [];
        }
      }
      await sleep();
      return fxRuns;
    },
    async get(id: string): Promise<WorkflowRun | null> {
      if (USE_API) {
        try {
          const row = await request<Record<string, unknown>>(`/workflow-runs/${encodeURIComponent(id)}`);
          return normalizeWorkflowRun(row);
        } catch {
          if (ALLOW_FIXTURE_FALLBACK) {
            const fixture = fxRuns.find((r) => r.id === id);
            return fixture ? normalizeWorkflowRun({ ...fixture }) : null;
          }
          return null;
        }
      }
      await sleep();
      const fixture = fxRuns.find((r) => r.id === id);
      return fixture ? normalizeWorkflowRun({ ...fixture }) : null;
    },
    async cancel(_id: string): Promise<void> {
      await sleep();
    },
    async resume(id: string, approved: boolean): Promise<WorkflowRun | null> {
      if (!USE_API) return null;
      try {
        const row = await request<Record<string, unknown>>(
          `/workflow-runs/${encodeURIComponent(id)}:resume`,
          {
            method: "POST",
            body: JSON.stringify({ approved, approver: "demo:reviewer" })
          }
        );
        return normalizeWorkflowRun(row);
      } catch {
        return null;
      }
    }
  },

  // ─── hooks ────────────────────────────────────────────────────────────
  hooks: {
    async list(): Promise<Hook[]> {
      return backendOrFixture<Hook[]>("/hooks", async () => {
        await sleep();
        return fxHooks;
      });
    },
    async calls(filter?: { workflow_run_id?: string; hook_id?: string }): Promise<HookCall[]> {
      if (USE_API) {
        const calls = await request<HookCall[]>("/hook-calls");
        return calls.filter((c) =>
          (!filter?.workflow_run_id || c.workflow_run_id === filter.workflow_run_id) &&
          (!filter?.hook_id || c.hook_id === filter.hook_id)
        );
      }
      await sleep();
      return fxHookCalls.filter((c) =>
        (!filter?.workflow_run_id || c.workflow_run_id === filter.workflow_run_id) &&
        (!filter?.hook_id || c.hook_id === filter.hook_id)
      );
    },
    async test(id: string): Promise<{ ok: boolean; resources_count: number; latency_ms: number }> {
      if (USE_API) return request(`/hooks/${encodeURIComponent(id)}:test`, { method: "POST" });
      await sleep(220);
      return { ok: true, resources_count: 12, latency_ms: 142 };
    },
    async catalog(): Promise<JsonStackCatalogEntry[]> {
      if (USE_API) return request<JsonStackCatalogEntry[]>("/hooks/json-stack/catalog");
      await sleep();
      return [];
    },
    async manifest(stackId: string): Promise<JsonStackManifest | null> {
      if (USE_API) {
        try {
          return await request<JsonStackManifest>(`/hooks/json-stack/catalog/${encodeURIComponent(stackId)}`);
        } catch {
          try {
            const hook = await request<Hook>(`/hooks/${encodeURIComponent(stackId)}`);
            return hook.json_stack ?? null;
          } catch {
            return null;
          }
        }
      }
      await sleep();
      return null;
    },
    async validate(spec: unknown): Promise<JsonStackValidateResult> {
      if (USE_API) {
        return request<JsonStackValidateResult>("/hooks/json-stack:validate", {
          method: "POST",
          body: JSON.stringify({ spec })
        });
      }
      await sleep();
      return { ok: false, errors: ["NEXT_PUBLIC_API_BASE not configured"] };
    },
    async preview(req: JsonStackPreviewRequest): Promise<JsonStackPreviewResult> {
      if (USE_API) {
        return request<JsonStackPreviewResult>("/hooks/json-stack:preview", {
          method: "POST",
          body: JSON.stringify(req)
        });
      }
      await sleep();
      return {
        ok: false,
        outputs: {
          mode: "unavailable",
          provider: "",
          operation: req.operation,
          request: { method: "GET", url: "", headers: {} }
        },
        latency_ms: 0,
        error: "NEXT_PUBLIC_API_BASE not configured"
      };
    },
    async persist(spec: JsonStackManifest, enabled = true): Promise<JsonStackPersistResult> {
      if (USE_API) {
        return request<JsonStackPersistResult>("/hooks/json-stack", {
          method: "POST",
          body: JSON.stringify({ spec, enabled })
        });
      }
      await sleep();
      return { ok: false, errors: ["NEXT_PUBLIC_API_BASE not configured"] };
    },
    async importOpenApi(req: JsonStackOpenApiImportRequest): Promise<JsonStackOpenApiImportResult> {
      if (USE_API) {
        return request<JsonStackOpenApiImportResult>("/hooks/json-stack:import-openapi", {
          method: "POST",
          body: JSON.stringify(req)
        });
      }
      await sleep();
      return {
        ok: false,
        manifest: {
          id: req.stack_id,
          name: req.stack_id,
          provider: req.provider,
          version: "unavailable",
          base_url: "https://api.example.com",
          auth: { kind: "none", auth_ref: null, scopes: [] },
          operations: {}
        },
        errors: ["NEXT_PUBLIC_API_BASE not configured"]
      };
    }
  },

  // ─── corpora & documents ─────────────────────────────────────────────
  corpora: {
    async create(payload: { name: string; kind?: string; description?: string; framework?: string; jurisdiction?: string; retention?: string; source_url?: string; id?: string }): Promise<Corpus> {
      if (!USE_API) throw new Error("Creating corpora requires the API data source.");
      const row = await request<Record<string, unknown>>("/corpora", { method: "POST", body: JSON.stringify(payload) });
      return normalizeCorpus(row);
    },
    async remove(id: string): Promise<void> {
      if (!USE_API) throw new Error("Deleting corpora requires the API data source.");
      await request<void>(`/corpora/${encodeURIComponent(id)}`, { method: "DELETE" });
    },
    async upload(corpusId: string, file: File): Promise<{ id: string; title: string; size_bytes?: number; media_type?: string; chunk_count: number }> {
      if (!USE_API || !API_BASE) throw new Error("Document upload requires the API data source.");
      const form = new FormData();
      form.append("file", file);
      const response = await fetch(`${API_BASE}/corpora/${encodeURIComponent(corpusId)}/documents:upload`, {
        method: "POST",
        cache: "no-store",
        headers: { Authorization: `Bearer ${API_TOKEN}` },
        body: form
      });
      if (!response.ok) throw new Error(`Upload failed: ${response.status} ${await response.text()}`);
      return response.json();
    },
    async list(): Promise<Corpus[]> {
      const rows = await backendOrFixture<Array<Record<string, unknown>>>("/corpora", async () => {
        await sleep();
        return fxCorpora.map((row) => ({ ...row }));
      });
      return rows.map(normalizeCorpus);
    },
    async get(id: string): Promise<Corpus | null> {
      if (USE_API) {
        try {
          const row = await request<Record<string, unknown>>(`/corpora/${encodeURIComponent(id)}`);
          return normalizeCorpus(row);
        } catch {
          if (!ALLOW_FIXTURE_FALLBACK) return null;
          const corpora = await this.list();
          return corpora.find((c) => c.id === id || c.urn === id) ?? null;
        }
      }
      await sleep();
      return fxCorpora.find((c) => c.id === id || c.urn === id) ?? null;
    },
    async documents(corpusId: string): Promise<PraetorDocument[]> {
      if (USE_API) {
        try {
          return await request<PraetorDocument[]>(`/corpora/${encodeURIComponent(corpusId)}/documents`);
        } catch {
          if (!ALLOW_FIXTURE_FALLBACK) return [];
          return fxDocs.filter((d) => d.corpus_id === corpusId);
        }
      }
      await sleep();
      return fxDocs.filter((d) => d.corpus_id === corpusId);
    },
    async search(corpusId: string, query: string, k = 8): Promise<DocumentChunk[]> {
      if (USE_API) {
        return request<DocumentChunk[]>(`/corpora/${encodeURIComponent(corpusId)}:search`, {
          method: "POST",
          body: JSON.stringify({ query, k })
        });
      }
      await sleep(140);
      const corpusDocIds = new Set(fxDocs.filter((d) => d.corpus_id === corpusId).map((d) => d.id));
      const q = query.toLowerCase();
      return fxChunks
        .filter((c) => corpusDocIds.has(c.document_id))
        .map((c) => ({
          ...c,
          score: scoreMatch(c.text + " " + c.citation_path, q)
        }))
        .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
        .slice(0, k);
    }
  },

  // ─── findings & proposed changes ─────────────────────────────────────
  findings: {
    async list(filter?: { workflow_run_id?: string; asset_id?: string }): Promise<Finding[]> {
      if (USE_API) {
        const findings = await request<Finding[]>("/findings");
        return findings.filter((f) =>
          (!filter?.workflow_run_id || f.workflow_run_id === filter.workflow_run_id) &&
          (!filter?.asset_id || f.asset_id === filter.asset_id)
        );
      }
      await sleep();
      return fxFindings.filter((f) =>
        (!filter?.workflow_run_id || f.workflow_run_id === filter.workflow_run_id) &&
        (!filter?.asset_id || f.asset_id === filter.asset_id)
      );
    },
    async get(id: string): Promise<Finding | null> {
      if (USE_API) {
        try {
          return await request<Finding>(`/findings/${encodeURIComponent(id)}`);
        } catch {
          if (!ALLOW_FIXTURE_FALLBACK) return null;
          return fixtureFinding(id);
        }
      }
      await sleep();
      return fixtureFinding(id);
    }
  },
  proposedChanges: {
    async list(): Promise<ProposedChange[]> {
      return backendOrFixture<ProposedChange[]>("/proposed-changes", async () => {
        await sleep();
        return fxProposals;
      });
    },
    async get(id: string): Promise<ProposedChange | null> {
      if (USE_API) {
        try {
          return await request<ProposedChange>(`/proposed-changes/${encodeURIComponent(id)}`);
        } catch {
          if (!ALLOW_FIXTURE_FALLBACK) return null;
          return fixtureProposal(id);
        }
      }
      await sleep();
      return fixtureProposal(id);
    },
    async approve(id: string): Promise<{ ok: boolean }> {
      if (USE_API) return request(`/proposed-changes/${encodeURIComponent(id)}:approve`, { method: "POST" });
      await sleep(180);
      return { ok: true };
    },
    async reject(_id: string): Promise<{ ok: boolean }> {
      await sleep(180);
      return { ok: true };
    }
  },

  // ─── sandbox runs ────────────────────────────────────────────────────
  sandboxRuns: {
    async list(): Promise<SandboxRun[]> {
      if (USE_API) return backendOrFixture<SandboxRun[]>("/sandbox-runs", async () => {
        await sleep();
        return fxSandboxes;
      });
      await sleep();
      return fxSandboxes;
    },
    async get(id: string): Promise<SandboxRun | null> {
      if (USE_API) {
        try {
          return await request<SandboxRun>(`/sandbox-runs/${encodeURIComponent(id)}`);
        } catch {
          if (ALLOW_FIXTURE_FALLBACK) return fxSandboxes.find((s) => s.id === id) ?? null;
          return null;
        }
      }
      await sleep();
      return fxSandboxes.find((s) => s.id === id) ?? null;
    }
  },

  // ─── policy decisions ────────────────────────────────────────────────
  policy: {
    async list(): Promise<PolicyDecision[]> {
      if (!USE_FIXTURES && !ALLOW_FIXTURE_FALLBACK) return [];
      await sleep();
      return fxPolicy;
    }
  },

  // ─── approvals ───────────────────────────────────────────────────────
  approvals: {
    async list(): Promise<Approval[]> {
      if (!USE_FIXTURES && !ALLOW_FIXTURE_FALLBACK) return [];
      await sleep();
      return fxApprovals;
    },
    async decide(_id: string, _outcome: "approved" | "rejected", _notes?: string): Promise<void> {
      await sleep(220);
    }
  },

  // ─── evidence & audit packets ────────────────────────────────────────
  evidence: {
    async list(): Promise<EvidenceRecord[]> {
      const rows = await backendOrFixture<Array<Record<string, unknown>>>("/evidence-records", async () => {
        await sleep();
        return fxEvidence.map((row) => ({ ...row }));
      });
      return rows.map(normalizeEvidenceRecord);
    }
  },
  auditPackets: {
    async list(): Promise<AuditPacket[]> {
      if (USE_API) {
        try {
          const rows = await request<Array<Record<string, unknown>>>("/audit-packets");
          return rows.map(normalizeAuditPacket);
        } catch {
          if (!ALLOW_FIXTURE_FALLBACK) return [];
        }
      }
      await sleep();
      return fxAuditPackets;
    },
    async get(id: string): Promise<AuditPacket | null> {
      if (USE_API) {
        try {
          const row = await request<Record<string, unknown>>(`/audit-packets/${encodeURIComponent(id)}`);
          return normalizeAuditPacket(row);
        } catch {
          if (!ALLOW_FIXTURE_FALLBACK) return null;
        }
      }
      await sleep();
      return fxAuditPackets.find((p) => p.id === id) ?? null;
    },
    async generate(payload: {
      label?: string;
      period_days?: number;
      surfaces?: string[];
      asset_ids?: string[];
      workflow_run_ids?: string[];
      obligation_urns?: string[];
    } = {}): Promise<{ packet_id: string; status: AuditPacket["status"] }> {
      if (USE_API) {
        const packet = await request<AuditPacket>("/audit-packets:generate", {
          method: "POST",
          body: JSON.stringify(payload)
        });
        return { packet_id: packet.id, status: packet.status ?? "ready" };
      }
      await sleep(400);
      return { packet_id: "ap_demo_pending", status: "generating" };
    },
    async download(id: string, kind: "pdf" | "sidecar"): Promise<void> {
      if (!USE_API || !API_BASE) throw new Error("Audit packet downloads require the API data source.");
      const response = await fetch(`${API_BASE}/audit-packets/${encodeURIComponent(id)}/${kind}`, {
        cache: "no-store",
        headers: { Authorization: `Bearer ${API_TOKEN}` }
      });
      if (!response.ok) {
        throw new Error(`Praetor API ${response.status}: ${await response.text()}`);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${id}.${kind === "pdf" ? "pdf" : "json"}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    }
  },

  // ─── alerts (UI-derived) ─────────────────────────────────────────────
  // The backend exposes /alerts which derives from open findings + proposed
  // changes awaiting approval — single round trip, no client-side fan-out.
  alerts: {
    async list(): Promise<Alert[]> {
      if (USE_API) {
        try {
          return await request<Alert[]>("/alerts");
        } catch {
          if (!ALLOW_FIXTURE_FALLBACK) return [];
        }
      }
      await sleep();
      return fxAlerts;
    }
  }
};

/**
 * Tiny ranking function — counts term hits + position bonus. We are not
 * pretending this is RRF; it is just enough to make the search box feel
 * responsive against fixture data.
 */
function scoreMatch(haystack: string, needle: string): number {
  if (!needle.trim()) return 0;
  const tokens = needle.split(/\s+/).filter(Boolean);
  const hay = haystack.toLowerCase();
  let score = 0;
  for (const t of tokens) {
    let pos = hay.indexOf(t);
    while (pos !== -1) {
      score += 1 - Math.min(0.6, pos / hay.length);
      pos = hay.indexOf(t, pos + t.length);
    }
  }
  return Math.min(1, score / 3);
}

function normalizeEvidenceRecord(row: Record<string, unknown>): EvidenceRecord {
  const obligationIds = Array.isArray(row.obligation_ids)
    ? row.obligation_ids
    : row.obligation_id
      ? [row.obligation_id]
      : [];
  const eventIds = Array.isArray(row.event_ids) ? row.event_ids : [];
  const decisionIds = Array.isArray(row.decision_ids) ? row.decision_ids : [];
  const ts =
    typeof row.ts === "string"
      ? row.ts
      : typeof row.created_at === "string"
        ? row.created_at
        : new Date().toISOString();
  const summary =
    typeof row.summary === "string"
      ? row.summary
      : `Evidence record linking ${eventIds.length} events and ${decisionIds.length} decisions.`;

  return {
    id: String(row.id ?? ""),
    obligation_ids: obligationIds.map(String),
    control_id: typeof row.control_id === "string" ? row.control_id : undefined,
    asset_id: typeof row.asset_id === "string" ? row.asset_id : undefined,
    workflow_run_id: typeof row.workflow_run_id === "string" ? row.workflow_run_id : undefined,
    event_ids: eventIds.map(String),
    decision_ids: decisionIds.map(String),
    hash: String(row.hash ?? ""),
    ts,
    summary
  };
}

const DEFAULT_NODE_CATALOG: Array<{
  type: string;
  phase: "pre" | "assess" | "post";
  label: string;
  summary: string;
  config_schema: Record<string, string>;
}> = [
  { type: "trigger.manual", phase: "pre", label: "Manual trigger", summary: "Workflow runs when a user instantiates it from the UI.", config_schema: {} },
  { type: "trigger.schedule", phase: "pre", label: "Schedule trigger", summary: "Runs on a cron-style schedule.", config_schema: { cron: "string", timezone: "string" } },
  { type: "trigger.webhook", phase: "pre", label: "Webhook trigger", summary: "Runs when an external service POSTs to a tenant URL.", config_schema: { path: "string" } },
  { type: "hook.in", phase: "pre", label: "Inbound hook", summary: "Pulls source data from a connected integration.", config_schema: { hook_id: "string", operation: "string", repo_url: "string" } },
  { type: "corpus.query", phase: "pre", label: "Corpus query", summary: "Retrieves obligation/policy excerpts.", config_schema: { query: "string", corpora: "list[string]", k: "number" } },
  { type: "transform", phase: "pre", label: "Transform", summary: "Deterministic data shaping.", config_schema: { expression: "string" } },
  { type: "agent", phase: "assess", label: "Agent step (sandboxed)", summary: "Runs the model agent in an isolated sandbox.", config_schema: { system_prompt_ref: "string", tool_budget: "number" } },
  { type: "model.complete", phase: "assess", label: "Single model call", summary: "One provider-neutral completion.", config_schema: { prompt: "string", provider: "string", model: "string" } },
  { type: "gate.policy", phase: "post", label: "Policy gate", summary: "OPA / policy-service decision.", config_schema: { policy_set: "string", severity: "string" } },
  { type: "gate.human", phase: "post", label: "Human approval", summary: "Pauses run until an approver decides.", config_schema: { role_required: "string", timeout_minutes: "number" } },
  { type: "sandbox.run", phase: "post", label: "Sandbox replay", summary: "Replays a proposed change in a container.", config_schema: { image: "string", command: "string" } },
  { type: "finding.emit", phase: "post", label: "Emit finding", summary: "Persists structured findings.", config_schema: {} },
  { type: "change.propose", phase: "post", label: "Propose change", summary: "Generates a patch/config/policy proposal.", config_schema: { target: "string", kind: "string" } },
  { type: "evidence.generate", phase: "post", label: "Generate evidence", summary: "Binds events into an evidence record.", config_schema: { obligation_urns: "list[string]" } },
  { type: "audit.packet", phase: "post", label: "Audit packet", summary: "Assembles signed audit material.", config_schema: { label: "string" } },
  { type: "hook.out", phase: "post", label: "Outbound hook", summary: "Sends approved output to a connected system.", config_schema: { hook_id: "string", operation: "string" } },
  { type: "notify", phase: "post", label: "Notify", summary: "Slack/Teams/email/webhook.", config_schema: { channel: "string", subject: "string" } }
];

function normalizeWorkflow(row: Record<string, unknown>): Workflow {
  const id = String(row.id ?? "");
  const fixture = fxWorkflows.find((workflow) => workflow.id === id || workflow.urn === row.urn);
  const now = new Date().toISOString();
  const trigger = row.trigger === "schedule" || row.trigger === "webhook" ? row.trigger : "manual";
  return {
    id,
    urn: typeof row.urn === "string" ? row.urn : fixture?.urn ?? `urn:praetor:workflow:demo:${id}`,
    created_at: typeof row.created_at === "string" ? row.created_at : fixture?.created_at ?? now,
    updated_at: typeof row.updated_at === "string" ? row.updated_at : fixture?.updated_at ?? now,
    created_by: typeof row.created_by === "string" ? row.created_by : fixture?.created_by ?? "praetor",
    version: Number(row.version ?? fixture?.version ?? 1),
    name: String(row.name ?? fixture?.name ?? id),
    description: String(row.description ?? fixture?.description ?? ""),
    definition: String(row.definition ?? fixture?.definition ?? ""),
    trigger,
    trigger_config: asRecord(row.trigger_config, fixture?.trigger_config),
    inputs_schema: asRecord(row.inputs_schema, fixture?.inputs_schema),
    outputs_schema: asRecord(row.outputs_schema, fixture?.outputs_schema),
    required_hooks: asStringArray(row.required_hooks, fixture?.required_hooks),
    required_corpora: asStringArray(row.required_corpora, fixture?.required_corpora),
    default_policy_set: String(row.default_policy_set ?? fixture?.default_policy_set ?? "praetor-demo"),
    template_origin: typeof row.template_origin === "string" ? row.template_origin : fixture?.template_origin,
    graph: resolveWorkflowGraph(row, fixture),
    steps: Array.isArray(row.steps) ? (row.steps as Workflow["steps"]) : undefined
  };
}

function resolveWorkflowGraph(row: Record<string, unknown>, fixture?: { definition?: string; required_corpora?: string[]; graph?: Workflow["graph"] }): Workflow["graph"] | undefined {
  if (row.graph && typeof row.graph === "object") return row.graph as Workflow["graph"];
  // Fallback: parse the fixture's YAML-ish `definition` block to derive a
  // minimal step list so the visual canvas renders identically in fixture
  // mode. Matches the backend's compile_steps_to_graph() phase mapping.
  const definition = typeof row.definition === "string" ? row.definition : fixture?.definition;
  if (typeof definition !== "string") return undefined;
  const steps = parseStepsFromYaml(definition).length
    ? parseStepsFromYaml(definition)
    : parseStepsFromArrowChain(definition);
  if (!steps.length && fixture?.graph) return fixture.graph;
  if (!steps.length) return undefined;
  return compileStepsToGraph(steps);
}

function parseStepsFromYaml(yaml: string): Array<{ id: string; type: string; depends_on?: string[]; with?: Record<string, unknown> }> {
  // Tiny ad-hoc parser — only used for fixtures. Looks for `- id: foo` blocks
  // followed by `type: bar` and optional `depends_on: [a, b]`. Robust enough
  // for the bundled fixture shapes; not a general YAML parser.
  const out: Array<{ id: string; type: string; depends_on?: string[] }> = [];
  const lines = yaml.split(/\r?\n/);
  let current: { id?: string; type?: string; depends_on?: string[] } | null = null;
  for (const line of lines) {
    const idMatch = line.match(/^\s*-\s*id:\s*(\S+)/);
    if (idMatch) {
      if (current?.id && current.type) out.push({ id: current.id, type: current.type, depends_on: current.depends_on });
      current = { id: idMatch[1].replace(/['"]/g, "") };
      continue;
    }
    if (!current) continue;
    const typeMatch = line.match(/^\s+type:\s*(\S+)/);
    if (typeMatch) current.type = typeMatch[1].replace(/['"]/g, "");
    const depMatch = line.match(/^\s+depends_on:\s*\[(.*?)\]/);
    if (depMatch) {
      current.depends_on = depMatch[1]
        .split(",")
        .map((s) => s.trim().replace(/['"]/g, ""))
        .filter(Boolean);
    }
  }
  if (current?.id && current.type) out.push({ id: current.id, type: current.type, depends_on: current.depends_on });
  return out;
}

function parseStepsFromArrowChain(definition: string): Array<{ id: string; type: string; depends_on?: string[] }> {
  if (!definition.includes("->")) return [];
  const ids = definition
    .split("->")
    .map((part) => part.trim())
    .filter(Boolean);
  return ids.map((id, index) => ({
    id,
    type: inferStepType(id),
    depends_on: index === 0 ? [] : [ids[index - 1]]
  }));
}

function inferStepType(id: string): string {
  const normalized = id.toLowerCase();
  if (normalized.includes("retrieve") || normalized.includes("controls") || normalized.includes("obligations")) return "corpus.query";
  if (normalized.includes("scan") || normalized.includes("analyze") || normalized.includes("classify") || normalized.includes("organize")) return "agent";
  if (normalized.includes("emit")) return "finding.emit";
  if (normalized.includes("propose")) return "change.propose";
  if (normalized.includes("policy_gate")) return "gate.policy";
  if (normalized.includes("human_gate") || normalized.includes("approve")) return "gate.human";
  if (normalized.includes("open_pr") || normalized.includes("dispatch") || normalized.includes("notify")) return "hook.out";
  if (normalized.includes("pull") || normalized.includes("load") || normalized.includes("read") || normalized.includes("intake")) return "hook.in";
  return "transform";
}

const PRE_TYPES = new Set(["trigger.manual", "trigger.schedule", "trigger.webhook", "trigger.event", "hook.in", "corpus.query"]);
const ASSESS_TYPES = new Set(["agent", "model.complete", "agent.run"]);
const POST_TYPES = new Set([
  "gate.policy", "gate.human", "sandbox.run", "finding.emit", "change.propose",
  "evidence.generate", "audit.packet", "notify", "hook.out"
]);

function compileStepsToGraph(steps: Array<{ id: string; type: string; depends_on?: string[] }>): Workflow["graph"] {
  let seenAssess = false;
  const phaseColumnX: Record<"pre" | "assess" | "post", number> = { pre: 80, assess: 380, post: 680 };
  const byPhase: Record<"pre" | "assess" | "post", string[]> = { pre: [], assess: [], post: [] };
  const nodes = steps.map((step) => {
    const phase: "pre" | "assess" | "post" = ASSESS_TYPES.has(step.type)
      ? "assess"
      : PRE_TYPES.has(step.type)
        ? "pre"
        : POST_TYPES.has(step.type)
          ? "post"
          : seenAssess ? "post" : "pre";
    if (phase === "assess") seenAssess = true;
    byPhase[phase].push(step.id);
    return {
      id: step.id,
      type: step.type,
      phase,
      label: step.id,
      config: {} as Record<string, unknown>,
      depends_on: step.depends_on,
      position: { x: 0, y: 0 }
    };
  });
  for (const node of nodes) {
    const indexInPhase = byPhase[node.phase].indexOf(node.id);
    node.position = { x: phaseColumnX[node.phase], y: 80 + indexInPhase * 140 };
  }
  const edges = nodes.flatMap((node) =>
    (node.depends_on ?? []).map((parent) => ({ id: `${parent}__${node.id}`, from: parent, to: node.id, kind: "control" as const }))
  );
  return { nodes, edges, phases: ["pre", "assess", "post"] };
}

function normalizeWorkflowRun(row: Record<string, unknown>): WorkflowRun {
  const id = String(row.id ?? "");
  const fixture = fxRuns.find((run) => run.id === id || run.urn === row.urn);
  const now = new Date().toISOString();
  const status = String(row.status ?? fixture?.status ?? "queued") as WorkflowRun["status"];
  const stepRows = Array.isArray(row.step_runs) ? row.step_runs : fixture?.step_runs ?? [];
  return {
    id,
    urn: typeof row.urn === "string" ? row.urn : fixture?.urn ?? `urn:praetor:workflow_run:production:${id}`,
    created_at: typeof row.created_at === "string" ? row.created_at : fixture?.created_at ?? now,
    updated_at: typeof row.updated_at === "string" ? row.updated_at : fixture?.updated_at ?? now,
    created_by: typeof row.created_by === "string" ? row.created_by : fixture?.created_by ?? "praetor",
    version: Number(row.version ?? fixture?.version ?? 1),
    workflow_id: String(row.workflow_id ?? fixture?.workflow_id ?? ""),
    asset_id: String(row.asset_id ?? fixture?.asset_id ?? ""),
    triggered_by: String(row.triggered_by ?? fixture?.triggered_by ?? "api"),
    triggered_at: String(row.triggered_at ?? fixture?.triggered_at ?? row.created_at ?? now),
    finished_at: typeof row.finished_at === "string" ? row.finished_at : fixture?.finished_at,
    status,
    inputs: asRecord(row.inputs, fixture?.inputs),
    outputs: asRecord(row.outputs, fixture?.outputs),
    step_runs: stepRows.map((step, index) => normalizeStepRun(step as Record<string, unknown>, id, index)),
    evidence_record_ids: asStringArray(row.evidence_record_ids, fixture?.evidence_record_ids)
  };
}

function normalizeStepRun(row: Record<string, unknown>, runId: string, index: number): StepRun {
  return {
    id: String(row.id ?? `${runId}:step:${index}`),
    workflow_run_id: String(row.workflow_run_id ?? runId),
    step_id: String(row.step_id ?? `step_${index + 1}`),
    step_type: String(row.step_type ?? "transform") as StepRun["step_type"],
    status: String(row.status ?? "pending") as StepRun["status"],
    started_at: typeof row.started_at === "string" ? row.started_at : undefined,
    finished_at: typeof row.finished_at === "string" ? row.finished_at : undefined,
    inputs_redacted: asRecord(row.inputs_redacted),
    outputs_redacted: asRecord(row.outputs_redacted),
    sandbox_run_id: typeof row.sandbox_run_id === "string" ? row.sandbox_run_id : undefined,
    hook_call_id: typeof row.hook_call_id === "string" ? row.hook_call_id : undefined,
    policy_decision_id: typeof row.policy_decision_id === "string" ? row.policy_decision_id : undefined,
    approval_id: typeof row.approval_id === "string" ? row.approval_id : undefined,
    emitted_finding_ids: asStringArray(row.emitted_finding_ids),
    emitted_proposal_ids: asStringArray(row.emitted_proposal_ids),
    depends_on: asStringArray(row.depends_on)
  };
}

function normalizeCorpus(row: Record<string, unknown>): Corpus {
  const id = String(row.id ?? "");
  const fixture = fxCorpora.find((corpus) => corpus.id === id || corpus.urn === row.urn);
  const now = new Date().toISOString();
  return {
    id,
    urn: typeof row.urn === "string" ? row.urn : fixture?.urn ?? `urn:praetor:corpus:demo:${id}`,
    created_at: typeof row.created_at === "string" ? row.created_at : fixture?.created_at ?? now,
    updated_at: typeof row.updated_at === "string" ? row.updated_at : fixture?.updated_at ?? now,
    created_by: typeof row.created_by === "string" ? row.created_by : fixture?.created_by ?? "praetor",
    version: Number(row.version ?? fixture?.version ?? 1),
    name: String(row.name ?? fixture?.name ?? id),
    description:
      typeof row.description === "string"
        ? row.description
        : fixture?.description ?? descriptionForCorpus(id, String(row.kind ?? "evidence_reference")),
    kind: normalizeCorpusKind(row.kind, fixture?.kind),
    framework: typeof row.framework === "string" ? row.framework : fixture?.framework,
    jurisdiction: typeof row.jurisdiction === "string" ? row.jurisdiction : fixture?.jurisdiction,
    parent_corpus_id:
      typeof row.parent_corpus_id === "string" ? row.parent_corpus_id : fixture?.parent_corpus_id,
    document_count: Number(row.document_count ?? fixture?.document_count ?? 0),
    indexed_at: typeof row.indexed_at === "string" ? row.indexed_at : fixture?.indexed_at ?? now,
    retention: typeof row.retention === "string" ? row.retention : fixture?.retention
  };
}

function asRecord(value: unknown, fallback?: Record<string, unknown>): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return fallback ?? {};
}

function asStringArray(value: unknown, fallback?: string[]): string[] {
  if (Array.isArray(value)) return value.map(String);
  return fallback ?? [];
}

function normalizeCorpusKind(value: unknown, fallback?: Corpus["kind"]): Corpus["kind"] {
  const allowed: Corpus["kind"][] = [
    "regulation",
    "standard",
    "internal_policy",
    "code_repo",
    "process_artefact",
    "evidence_reference"
  ];
  return allowed.includes(value as Corpus["kind"]) ? (value as Corpus["kind"]) : fallback ?? "evidence_reference";
}

function descriptionForCorpus(id: string, kind: string): string {
  if (id.includes("internal")) return "Internal policy corpus used for data minimisation, tool-use, and retention checks.";
  if (id.includes("iso")) return "Standards corpus with ISO-style AI management system control excerpts.";
  if (id.includes("gdpr")) return "Regulatory corpus for privacy, minimisation, and lawful processing obligations.";
  if (id.includes("owasp")) return "Application security corpus for agentic risk patterns and mitigations.";
  if (id.includes("eu")) return "Regulatory corpus for high-risk AI system obligations and governance evidence.";
  return `${kind.replace("_", " ")} corpus available for governed retrieval and citation.`;
}

function fixtureFinding(id: string): Finding | null {
  return fxFindings.find((finding) => finding.id === id || finding.urn === id) ?? null;
}

function fixtureProposal(id: string): ProposedChange | null {
  return fxProposals.find((proposal) => proposal.id === id || proposal.urn === id) ?? null;
}

function normalizeAuditPacket(row: Record<string, unknown>): AuditPacket {
  const scope = (row.scope && typeof row.scope === "object" && !Array.isArray(row.scope)
    ? (row.scope as Record<string, unknown>)
    : {}) as AuditPacket["scope"];
  return {
    id: String(row.id ?? ""),
    period_start: String(row.period_start ?? new Date().toISOString()),
    period_end: String(row.period_end ?? new Date().toISOString()),
    scope,
    status: (typeof row.status === "string" ? row.status : "ready") as AuditPacket["status"],
    pdf_path: typeof row.pdf_path === "string" ? row.pdf_path : undefined,
    json_sidecar_path: typeof row.json_sidecar_path === "string" ? row.json_sidecar_path : undefined,
    packet_hash: typeof row.packet_hash === "string" ? row.packet_hash : undefined,
    signature: typeof row.signature === "string" ? row.signature : undefined,
    pubkey_fingerprint: typeof row.pubkey_fingerprint === "string" ? row.pubkey_fingerprint : undefined,
    generated_at: typeof row.generated_at === "string" ? row.generated_at : undefined,
    counts: row.counts && typeof row.counts === "object" ? (row.counts as AuditPacket["counts"]) : undefined
  };
}

