import { useState } from 'react';
import { FileUploader } from './components/FileUploader';
import { ProcessingView } from './components/ProcessingView';
import { ResultView } from './components/ResultView';

type AppState = 'upload' | 'processing' | 'result';

export default function App() {
  const [appState, setAppState] = useState<AppState>('upload');
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [generatedNotes, setGeneratedNotes] = useState<string>('');

  const handleFilesSelected = async (files: File[]) => {
  setUploadedFiles(files);
  setAppState('processing');

  try {
    const fd = new FormData();
    files.forEach((f) => fd.append('files', f)); // backend expects files[] named "files"
    // optional: ask for latex or markdown
    fd.append('output_format', 'markdown');

    const resp = await fetch('http://localhost:8000/process', {
      method: 'POST',
      body: fd,
    });

    if (!resp.ok) {
      const txt = await resp.text();
      console.error('Server returned error:', resp.status, txt);
      setGeneratedNotes(`Error from server: ${resp.status} - ${txt}`);
      setAppState('result');
      return;
    }

    const data = await resp.json();
    // prefer combined_summary if available
    const combined = data.combined_summary || (data.per_file && data.per_file.length ? data.per_file.map((p:any) => p.summary).join('\n\n') : '');
    setGeneratedNotes(combined || "[No summary returned]");
    setAppState('result');
  } catch (err) {
    console.error('Failed to process files', err);
    setGeneratedNotes(`Failed to contact server: ${String(err)}`);
    setAppState('result');
  }
};

  const handleStartOver = () => {
    setAppState('upload');
    setUploadedFiles([]);
    setGeneratedNotes('');
  };

  const generateMockNotes = (files: File[]): string => {
    return `# AI-Generated Study Notes

## Documents Processed
${files.map(file => `- ${file.name}`).join('\n')}

---

## Summary

This document contains comprehensive notes extracted and synthesized from your uploaded materials. The AI has analyzed the content and organized key information into digestible sections.

## Key Concepts

### Concept 1: Introduction to the Topic
- Main point: Understanding the foundational elements
- Supporting details: Core principles and definitions
- Application: Practical use cases and examples

### Concept 2: Advanced Principles
- Main point: Building on fundamental knowledge
- Supporting details: Complex interactions and relationships
- Application: Real-world implementation strategies

### Concept 3: Critical Analysis
- Main point: Evaluating different perspectives
- Supporting details: Comparative analysis and contrasts
- Application: Decision-making frameworks

## Important Definitions

**Term 1**: A fundamental concept that describes the basic building blocks of the subject matter.

**Term 2**: An advanced principle that combines multiple elements to create comprehensive understanding.

**Term 3**: A practical application that demonstrates real-world usage and benefits.

## Key Takeaways

1. Understanding the core concepts is essential for building advanced knowledge
2. Practical application reinforces theoretical understanding
3. Critical analysis helps in making informed decisions
4. Continuous learning and review solidify comprehension

## Practice Questions

1. What are the fundamental principles discussed in the materials?
2. How do the advanced concepts build upon the foundational knowledge?
3. What are the practical applications of these concepts?
4. How can you apply this knowledge in real-world scenarios?

---

*Generated on ${new Date().toLocaleDateString()} at ${new Date().toLocaleTimeString()}*
*Source files: ${files.length} document(s)*
`;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {appState === 'upload' && (
        <FileUploader onFilesSelected={handleFilesSelected} />
      )}
      
      {appState === 'processing' && (
        <ProcessingView fileCount={uploadedFiles.length} />
      )}
      
      {appState === 'result' && (
        <ResultView 
          notes={generatedNotes} 
          fileCount={uploadedFiles.length}
          onStartOver={handleStartOver}
        />
      )}
    </div>
  );
}
