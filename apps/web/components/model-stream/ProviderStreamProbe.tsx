"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { ModelStreamEvent } from "@/lib/api/types";
import { Button } from "@/components/primitives/Button";
import { Badge } from "@/components/primitives/Badge";
import { Play, Radio } from "lucide-react";

const PROVIDERS = [
  { id: "openai", model: "gpt-5.4-mini" },
  { id: "anthropic", model: "claude-sonnet-4-20250514" },
  { id: "google", model: "gemini-2.0-flash" }
];

export function ProviderStreamProbe() {
  const [provider, setProvider] = useState(PROVIDERS[0]);
  const [prompt, setPrompt] = useState("Summarize why external tool calls need approval evidence.");
  const [events, setEvents] = useState<ModelStreamEvent[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  const run = async () => {
    setBusy(true);
    setEvents([]);
    setText("");
    try {
      await api.models.stream(
        {
          provider: provider.id,
          model: provider.model,
          prompt,
          dry_run: true
        },
        (event) => {
          setEvents((prev) => [...prev, event]);
          if (event.type === "delta" && event.text) setText((prev) => prev + event.text);
          if (event.type === "done" && event.text) setText(event.text);
        }
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <div className="space-y-3">
        <div className="grid grid-cols-3 gap-2">
          {PROVIDERS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setProvider(item)}
              className={`border rounded-sm px-3 py-2 text-left text-[12px] transition-colors ${provider.id === item.id ? "border-gold text-paper bg-gold/10" : "border-rule text-paper-dim hover:text-paper"}`}
            >
              {item.id}
            </button>
          ))}
        </div>
        <textarea
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          rows={5}
          className="w-full bg-ink border border-rule rounded-sm px-3 py-2 text-[12px] leading-[1.5] text-paper outline-none focus:border-gold resize-y"
        />
        <Button onClick={run} disabled={busy || !prompt.trim()}>
          {busy ? <Radio size={13} strokeWidth={1.75} /> : <Play size={13} strokeWidth={1.75} />}
          {busy ? "Streaming" : "Stream dry run"}
        </Button>
      </div>
      <div className="border border-rule rounded-sm min-h-[180px] overflow-hidden">
        <div className="flex items-center justify-between border-b border-rule px-4 py-2">
          <span className="font-mono text-[11px] text-paper-fade">{provider.model}</span>
          <Badge tone={busy ? "info" : events.some((event) => event.type === "done") ? "ok" : "muted"}>
            {busy ? "live" : events.length ? "complete" : "idle"}
          </Badge>
        </div>
        <div className="p-4">
          <p className="min-h-[72px] whitespace-pre-wrap text-[13px] leading-[1.55] text-paper-dim">
            {text || "No streamed output yet."}
          </p>
          <div className="mt-4 flex flex-wrap gap-1.5">
            {events.map((event, index) => (
              <span key={`${event.type}-${index}`} className="font-mono text-[10.5px] border border-rule px-1.5 py-0.5 text-paper-fade">
                {event.type}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
