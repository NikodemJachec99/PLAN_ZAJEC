import { ChangeEvent, useMemo, useState } from "react";
import { Loader2, Upload, X } from "lucide-react";

import type { RuntimeSettings } from "../types";

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
  settings?: RuntimeSettings;
  adminToken: string;
  onAdminTokenChange: (value: string) => void;
  exactGroupsText: string;
  onExactGroupsTextChange: (value: string) => void;
  prefixesText: string;
  onPrefixesTextChange: (value: string) => void;
  onSaveRules: () => Promise<void>;
  onUploadMainFile: (file: File) => Promise<void>;
  onUploadPracticalFile: (file: File) => Promise<void>;
  busy: boolean;
  message: string | null;
}

function formatSelected(file: File | null): string {
  if (!file) {
    return "Nie wybrano pliku";
  }
  return `${file.name} (${Math.round(file.size / 1024)} KB)`;
}

export function SettingsModal({
  open,
  onClose,
  settings,
  adminToken,
  onAdminTokenChange,
  exactGroupsText,
  onExactGroupsTextChange,
  prefixesText,
  onPrefixesTextChange,
  onSaveRules,
  onUploadMainFile,
  onUploadPracticalFile,
  busy,
  message,
}: SettingsModalProps) {
  const [mainFile, setMainFile] = useState<File | null>(null);
  const [practicalFile, setPracticalFile] = useState<File | null>(null);

  const canSubmit = useMemo(() => adminToken.trim().length > 0 && !busy, [adminToken, busy]);

  if (!open) {
    return null;
  }

  const handleMainChange = (event: ChangeEvent<HTMLInputElement>) => {
    setMainFile(event.target.files?.[0] ?? null);
  };

  const handlePracticalChange = (event: ChangeEvent<HTMLInputElement>) => {
    setPracticalFile(event.target.files?.[0] ?? null);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end bg-black/35 p-3 backdrop-blur-sm md:items-center md:justify-center md:p-6">
      <div className="w-full max-w-3xl rounded-3xl border border-black/10 bg-white p-4 shadow-panel md:p-6">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h3 className="font-heading text-2xl font-extrabold tracking-tight text-ink">Ustawienia danych</h3>
            <p className="mt-1 text-sm text-black/65">Podmieniaj pliki Excel i reguly filtra Magdalenki.</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-black/15 text-black/70 hover:bg-black/5"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4">
          <section className="rounded-2xl border border-black/10 bg-white/70 p-3">
            <p className="text-xs font-semibold uppercase tracking-[0.15em] text-black/45">Autoryzacja</p>
            <input
              type="password"
              placeholder="Wklej SETTINGS_ADMIN_TOKEN"
              className="mt-2 w-full rounded-xl border border-black/15 bg-white px-3 py-2 text-sm outline-none focus:border-moss"
              value={adminToken}
              onChange={(event) => onAdminTokenChange(event.target.value)}
            />
            {!settings?.admin_configured && (
              <p className="mt-2 text-xs font-semibold text-red-600">Backend nie ma ustawionego SETTINGS_ADMIN_TOKEN.</p>
            )}
          </section>

          <section className="grid gap-3 md:grid-cols-2">
            <div className="rounded-2xl border border-black/10 bg-white/70 p-3">
              <p className="text-sm font-bold text-ink">Plik planu zajec zwyklych</p>
              <p className="mt-1 text-xs text-black/60">Aktualny: {settings?.main_file ?? "-"}</p>
              <label className="mt-3 block">
                <input type="file" accept=".xlsx" className="w-full text-xs" onChange={handleMainChange} />
              </label>
              <p className="mt-2 text-xs text-black/55">{formatSelected(mainFile)}</p>
              <button
                type="button"
                disabled={!canSubmit || !mainFile}
                onClick={async () => {
                  if (!mainFile) return;
                  await onUploadMainFile(mainFile);
                  setMainFile(null);
                }}
                className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-xl border border-black/15 bg-white px-3 py-2 text-sm font-semibold text-black/75 disabled:cursor-not-allowed disabled:opacity-50 hover:bg-black/5"
              >
                <Upload className="h-4 w-4" /> Wgraj plik
              </button>
            </div>

            <div className="rounded-2xl border border-black/10 bg-white/70 p-3">
              <p className="text-sm font-bold text-ink">Plik planu praktyk</p>
              <p className="mt-1 text-xs text-black/60">Aktualny: {settings?.practical_file ?? "-"}</p>
              <label className="mt-3 block">
                <input type="file" accept=".xlsx" className="w-full text-xs" onChange={handlePracticalChange} />
              </label>
              <p className="mt-2 text-xs text-black/55">{formatSelected(practicalFile)}</p>
              <button
                type="button"
                disabled={!canSubmit || !practicalFile}
                onClick={async () => {
                  if (!practicalFile) return;
                  await onUploadPracticalFile(practicalFile);
                  setPracticalFile(null);
                }}
                className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-xl border border-black/15 bg-white px-3 py-2 text-sm font-semibold text-black/75 disabled:cursor-not-allowed disabled:opacity-50 hover:bg-black/5"
              >
                <Upload className="h-4 w-4" /> Wgraj plik
              </button>
            </div>
          </section>

          <section className="rounded-2xl border border-black/10 bg-white/70 p-3">
            <p className="text-sm font-bold text-ink">Reguly filtra Magdalenki</p>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <label className="block">
                <span className="text-xs font-semibold text-black/60">Exact groups (po przecinku lub nowej linii)</span>
                <textarea
                  rows={5}
                  className="mt-1 w-full rounded-xl border border-black/15 bg-white px-3 py-2 text-sm outline-none focus:border-moss"
                  value={exactGroupsText}
                  onChange={(event) => onExactGroupsTextChange(event.target.value)}
                />
              </label>
              <label className="block">
                <span className="text-xs font-semibold text-black/60">Prefixy</span>
                <textarea
                  rows={5}
                  className="mt-1 w-full rounded-xl border border-black/15 bg-white px-3 py-2 text-sm outline-none focus:border-moss"
                  value={prefixesText}
                  onChange={(event) => onPrefixesTextChange(event.target.value)}
                />
              </label>
            </div>
            <button
              type="button"
              disabled={!canSubmit}
              onClick={onSaveRules}
              className="mt-3 inline-flex items-center gap-2 rounded-xl border border-moss/35 bg-moss/10 px-4 py-2 text-sm font-semibold text-moss disabled:cursor-not-allowed disabled:opacity-50 hover:bg-moss/20"
            >
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Zapisz ustawienia
            </button>
          </section>

          {message && (
            <div className="rounded-xl border border-black/10 bg-white px-3 py-2 text-sm text-black/70">
              {message}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
