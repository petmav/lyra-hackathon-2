"use client";

import { useRef, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/primitives/Button";
import { Loader2, Upload } from "lucide-react";

/**
 * File upload control for a single corpus. Stores binaries on disk; text
 * content is extracted at ingest time for hybrid retrieval. Binary documents
 * (PDF/etc.) are still attached to workflow runs at sandbox execution time.
 */
export function DocumentUploader({
  corpusId,
  onUploaded
}: {
  corpusId: string;
  onUploaded: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [last, setLast] = useState<{ title: string; size_bytes?: number; chunk_count: number } | null>(null);

  const onPick = () => inputRef.current?.click();

  const onChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!files.length) return;
    setError(null);
    setLast(null);
    for (const file of files) {
      setBusy(file.name);
      try {
        const result = await api.corpora.upload(corpusId, file);
        setLast({ title: result.title, size_bytes: result.size_bytes, chunk_count: result.chunk_count });
      } catch (e) {
        setError(`${file.name}: ${e instanceof Error ? e.message : String(e)}`);
        break;
      }
    }
    setBusy(null);
    onUploaded();
  };

  return (
    <div className="border border-rule rounded-sm p-4 bg-ink-2">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="min-w-0">
          <div className="text-[12px] font-medium uppercase tracking-[0.08em] text-paper-fade">
            Upload documents
          </div>
          <p className="mt-1 text-[12px] text-paper-dim leading-snug max-w-md">
            PDFs, markdown, or text files. Binary uploads are kept whole and forwarded
            to the agent sandbox when a workflow selects this corpus; text-encoded
            files are also chunked for hybrid retrieval.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <input
            ref={inputRef}
            type="file"
            multiple
            onChange={onChange}
            className="hidden"
            accept=".pdf,.md,.txt,.markdown,.csv,.json,.yaml,.yml"
          />
          <Button onClick={onPick} variant="primary" disabled={busy !== null}>
            {busy ? <Loader2 size={13} strokeWidth={1.75} className="animate-spin" /> : <Upload size={13} strokeWidth={1.75} />}
            {busy ? `Uploading ${busy}` : "Choose files"}
          </Button>
        </div>
      </div>

      {error && (
        <div className="mt-3 border border-crit/40 bg-crit/5 text-crit px-3 py-2 text-[12px] rounded-sm">
          {error}
        </div>
      )}
      {last && !error && (
        <div className="mt-3 border border-ok/40 bg-ok/5 text-ok px-3 py-2 text-[12px] rounded-sm">
          Uploaded · <span className="font-mono">{last.title}</span>
          {typeof last.size_bytes === "number" && <> · {formatBytes(last.size_bytes)}</>}
          {last.chunk_count > 0 && <> · {last.chunk_count} chunks indexed</>}
        </div>
      )}
    </div>
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
