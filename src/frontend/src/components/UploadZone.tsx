/**
 * UploadZone — drag-and-drop + click file picker.
 * Validates accepted MIME types, calls onFile when a valid file is chosen.
 */
import { useRef, useState } from "react";

interface UploadZoneProps {
  accept: string;            // e.g. ".csv,.json"
  hint: string;              // helper text shown under the icon
  onFile: (file: File) => void;
  disabled?: boolean;
}

export function UploadZone({ accept, hint, onFile, disabled }: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [chosen, setChosen] = useState<File | null>(null);

  function handleFile(file: File) {
    setChosen(file);
    onFile(file);
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    if (disabled) return;
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }

  return (
    <div
      className={`sr-upload-zone${dragOver ? " drag-over" : ""}`}
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      role="button"
      aria-label="Upload file"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && !disabled && inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        onChange={handleChange}
        disabled={disabled}
        aria-hidden="true"
      />
      <svg width="36" height="36" viewBox="0 0 24 24" fill="none" aria-hidden="true" style={{ color: "var(--accent)", margin: "0 auto" }}>
        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
        <polyline points="17,8 12,3 7,8" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
        <line x1="12" y1="3" x2="12" y2="15" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
      </svg>
      <div className="sr-upload-zone-label">
        {chosen ? "Replace file" : "Click or drag a file here"}
      </div>
      {chosen ? (
        <div className="sr-upload-file-name">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" stroke="currentColor" strokeWidth="2" /><polyline points="14,2 14,8 20,8" stroke="currentColor" strokeWidth="2" /></svg>
          {chosen.name}
        </div>
      ) : (
        <div className="sr-upload-zone-hint">{hint}</div>
      )}
    </div>
  );
}
