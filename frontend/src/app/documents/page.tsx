import React from "react";
import { Files, UploadCloud, ShieldAlert, CheckCircle2 } from "lucide-react";

export default function DocumentsPage() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col space-y-1.5">
        <h2 className="text-2xl font-bold text-white tracking-tight">
          Document Corpus & Approvals
        </h2>
        <p className="text-xs text-gray-400">
          Upload enterprise Markdown, text, and PDF policies. Protected by automated prompt-injection detection (N8)
          and Human-in-the-Loop approval gates on document deletion (F17).
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2 rounded-xl border border-gray-800 bg-gray-900/60 p-6 space-y-4">
          <h3 className="text-xs font-mono font-semibold text-gray-400 uppercase">
            Ingested Document Library
          </h3>
          <div className="rounded-lg border border-gray-800 bg-gray-950 p-4 text-xs text-gray-400 text-center">
            15 curated enterprise documents indexed into vector and relational stores.
          </div>
        </div>

        <div className="rounded-xl border border-dashed border-gray-700 bg-gray-900/40 p-6 flex flex-col items-center justify-center text-center space-y-3">
          <div className="p-3 rounded-full bg-blue-600/10 text-blue-400 border border-blue-500/20">
            <UploadCloud size={24} />
          </div>
          <div className="space-y-1">
            <p className="text-xs font-semibold text-gray-200">
              Upload Document Corpus
            </p>
            <p className="text-[11px] text-gray-500">
              .md, .txt, .pdf up to 5MB (N7)
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
