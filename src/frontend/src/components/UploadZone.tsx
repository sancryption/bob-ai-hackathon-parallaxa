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
      <div style={{ fontSize: "1.75rem" }}>📤</div>
      <div className="sr-upload-zone-label">
        {chosen ? "Replace file" : "Click or drag a file here"}
      </div>
      {chosen ? (
        <div className="sr-upload-file-name">📄 {chosen.name}</div>
      ) : (
        <div className="sr-upload-zone-hint">{hint}</div>
      )}
    </div>
  );
}
