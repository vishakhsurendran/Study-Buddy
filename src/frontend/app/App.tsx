// src/frontend/app/App.tsx
import { useState } from "react";
import { FileUploader } from "./components/FileUploader";
import { ProcessingView } from "./components/ProcessingView";
import { ResultView } from "./components/ResultView";

const RAW_API_URL = import.meta.env.VITE_API_URL as string | undefined;
const API_URL = (RAW_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

type AppState = "upload" | "processing" | "result";

export default function App() {
  const [appState, setAppState] = useState<AppState>("upload");
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [generatedNotes, setGeneratedNotes] = useState<string>("");
  const [combinedPdfUrl, setCombinedPdfUrl] = useState<string | null>(null);
  const [pdfError, setPdfError] = useState<string | null>(null);

  const handleFilesSelected = async (files: File[]) => {
    setUploadedFiles(files);
    setAppState("processing");
    setCombinedPdfUrl(null);
    setPdfError(null);
    setGeneratedNotes("");

    try {
      const fd = new FormData();
      files.forEach((f) => fd.append("files", f));
      fd.append("output_format", "latex");

      const endpoint = `${API_URL}/process`;
      console.log("Posting to backend:", endpoint);

      const resp = await fetch(endpoint, {
        method: "POST",
        body: fd,
      });

      if (!resp.ok) {
        const txt = await resp.text();
        console.error("Server returned error:", resp.status, txt);
        setGeneratedNotes(`Error from server: ${resp.status} - ${txt}`);
        setAppState("result");
        return;
      }

      const data = await resp.json();

      setCombinedPdfUrl(data.combined_pdf_url ?? null);
      setPdfError(data.combined_pdf_error ?? null);

      const combined =
        data.combined_summary ||
        (data.per_file && data.per_file.length
          ? data.per_file.map((p: any) => p.summary).join("\n\n")
          : "");

      setGeneratedNotes(combined || "[No summary returned]");
      setAppState("result");
    } catch (err) {
      console.error("Failed to process files", err);
      setGeneratedNotes(`Failed to contact server: ${String(err)}`);
      setAppState("result");
    }
  };

  const handleStartOver = () => {
    setAppState("upload");
    setUploadedFiles([]);
    setGeneratedNotes("");
    setCombinedPdfUrl(null);
    setPdfError(null);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {appState === "upload" && (
        <FileUploader onFilesSelected={handleFilesSelected} />
      )}

      {appState === "processing" && (
        <ProcessingView fileCount={uploadedFiles.length} />
      )}

      {appState === "result" && (
        <ResultView
          notes={generatedNotes}
          fileCount={uploadedFiles.length}
          onStartOver={handleStartOver}
          pdfUrl={combinedPdfUrl}
          pdfError={pdfError}
        />
      )}
    </div>
  );
}
