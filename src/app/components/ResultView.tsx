import { Download, RefreshCw, CheckCircle2, Copy } from 'lucide-react';
import { Button } from './ui/button';
import { useState } from 'react';

interface ResultViewProps {
  notes: string;
  fileCount: number;
  onStartOver: () => void;
}

export function ResultView({ notes, fileCount, onStartOver }: ResultViewProps) {
  const [copied, setCopied] = useState(false);

  const handleDownloadPDF = () => {
    // Create a blob with the notes content
    const blob = new Blob([notes], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `ai-notes-${new Date().toISOString().split('T')[0]}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(notes);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-5xl mx-auto">
        <div className="bg-white rounded-2xl shadow-xl overflow-hidden">
          {/* Header */}
          <div className="bg-gradient-to-r from-blue-600 to-indigo-600 p-8 text-white">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 bg-white/20 rounded-full flex items-center justify-center">
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <div>
                <h2 className="text-3xl">Notes Generated Successfully!</h2>
                <p className="text-blue-100 mt-1">
                  Processed {fileCount} {fileCount === 1 ? 'document' : 'documents'}
                </p>
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <Button
                onClick={handleDownloadPDF}
                className="bg-white text-blue-600 hover:bg-blue-50"
              >
                <Download className="w-4 h-4 mr-2" />
                Download Notes
              </Button>
              <Button
                onClick={handleCopy}
                className="bg-white/10 text-white hover:bg-white/20 border border-white/30"
              >
                <Copy className="w-4 h-4 mr-2" />
                {copied ? 'Copied!' : 'Copy to Clipboard'}
              </Button>
              <Button
                onClick={onStartOver}
                className="bg-white/10 text-white hover:bg-white/20 border border-white/30 ml-auto"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Process New Documents
              </Button>
            </div>
          </div>

          {/* Notes Content */}
          <div className="p-8">
            <div className="prose prose-blue max-w-none">
              <div className="bg-gray-50 rounded-lg p-8 border border-gray-200">
                <pre className="whitespace-pre-wrap font-sans text-gray-800 leading-relaxed">
                  {notes}
                </pre>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="border-t border-gray-200 px-8 py-6 bg-gray-50">
            <div className="flex items-center justify-between text-sm text-gray-600">
              <p>
                💡 Tip: Review and supplement these AI-generated notes with your own insights
              </p>
              <button
                onClick={onStartOver}
                className="text-blue-600 hover:text-blue-700 hover:underline"
              >
                Create more notes →
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
