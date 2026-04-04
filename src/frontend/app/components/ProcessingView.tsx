import { useEffect, useMemo, useState } from "react";
import { Loader2, Brain, FileText, Sparkles } from "lucide-react";
import { Progress } from "./ui/progress";

interface ProcessingViewProps {
  fileCount: number;
}

export function ProcessingView({ fileCount }: ProcessingViewProps) {
  const [progress, setProgress] = useState(8);

  const steps = useMemo(
    () => [
      { icon: FileText, label: "Reading documents" },
      { icon: Brain, label: "Analyzing content" },
      { icon: Sparkles, label: "Generating notes" },
    ],
    []
  );

  useEffect(() => {
    const timer = window.setInterval(() => {
      setProgress((prev) => {
        if (prev >= 92) return 92;

        let increment = 0.9;
        if (prev < 25) increment = 3.5;
        else if (prev < 60) increment = 1.4;
        else if (prev < 80) increment = 0.6;
        else increment = 0.2;

        return Math.min(92, prev + increment);
      });
    }, 120);

    return () => window.clearInterval(timer);
  }, []);

  const currentStep =
    progress < 33 ? 0 : progress < 66 ? 1 : 2;

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-2xl">
        <div className="rounded-2xl bg-white p-12 shadow-xl">
          <div className="mb-8 text-center">
            <div className="mb-6 flex justify-center">
              <div className="relative">
                <div className="flex h-20 w-20 items-center justify-center rounded-full bg-blue-100">
                  <Loader2 className="h-10 w-10 animate-spin text-blue-600" />
                </div>
                <div className="absolute -right-1 -top-1 flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-br from-blue-400 to-indigo-500">
                  <Sparkles className="h-3 w-3 text-white" />
                </div>
              </div>
            </div>

            <h2 className="mb-3 text-3xl text-gray-900">
              Processing Your Documents
            </h2>
            <p className="text-gray-600">
              Analyzing {fileCount} {fileCount === 1 ? "document" : "documents"} with AI...
            </p>
          </div>

          <div className="mb-8">
            <Progress value={progress} className="h-2" />
            <p className="mt-2 text-center text-sm text-gray-500">
              {Math.round(progress)}% complete
            </p>
          </div>

          <div className="space-y-4">
            {steps.map((step, index) => {
              const StepIcon = step.icon;
              const isActive = currentStep === index;
              const isComplete = currentStep > index;

              return (
                <div
                  key={index}
                  className={`flex items-center gap-4 rounded-lg border-2 p-4 transition-all ${
                    isActive
                      ? "border-blue-200 bg-blue-50"
                      : isComplete
                      ? "border-green-200 bg-green-50"
                      : "border-gray-200 bg-gray-50"
                  }`}
                >
                  <div
                    className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full ${
                      isActive
                        ? "bg-blue-600"
                        : isComplete
                        ? "bg-green-600"
                        : "bg-gray-400"
                    }`}
                  >
                    <StepIcon
                      className={`h-5 w-5 text-white ${
                        isActive ? "animate-pulse" : ""
                      }`}
                    />
                  </div>

                  <span
                    className={`${
                      isActive || isComplete ? "text-gray-900" : "text-gray-500"
                    }`}
                  >
                    {step.label}
                  </span>

                  {isActive && (
                    <Loader2 className="ml-auto h-4 w-4 animate-spin text-blue-600" />
                  )}

                  {isComplete && (
                    <div className="ml-auto flex h-4 w-4 items-center justify-center rounded-full bg-green-600">
                      <svg
                        className="h-3 w-3 text-white"
                        fill="none"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="2"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path d="M5 13l4 4L19 7"></path>
                      </svg>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
