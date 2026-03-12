import { Loader2, Brain, FileText, Sparkles } from 'lucide-react';
import { Progress } from './ui/progress';
import { useEffect, useState } from 'react';

interface ProcessingViewProps {
  fileCount: number;
}

export function ProcessingView({ fileCount }: ProcessingViewProps) {
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState(0);

  const steps = [
    { icon: FileText, label: 'Reading documents', duration: 1000 },
    { icon: Brain, label: 'Analyzing content', duration: 1200 },
    { icon: Sparkles, label: 'Generating notes', duration: 800 },
  ];

  useEffect(() => {
    const totalDuration = 3000;
    const interval = 30;
    const increment = 100 / (totalDuration / interval);

    const timer = setInterval(() => {
      setProgress(prev => {
        if (prev >= 100) {
          clearInterval(timer);
          return 100;
        }
        return Math.min(prev + increment, 100);
      });
    }, interval);

    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const stepTimers = [
      setTimeout(() => setCurrentStep(1), 1000),
      setTimeout(() => setCurrentStep(2), 2200),
    ];

    return () => stepTimers.forEach(timer => clearTimeout(timer));
  }, []);

  return (
    <div className="flex items-center justify-center min-h-screen p-6">
      <div className="w-full max-w-2xl">
        <div className="bg-white rounded-2xl shadow-xl p-12">
          <div className="text-center mb-8">
            <div className="flex justify-center mb-6">
              <div className="relative">
                <div className="w-20 h-20 bg-blue-100 rounded-full flex items-center justify-center">
                  <Loader2 className="w-10 h-10 text-blue-600 animate-spin" />
                </div>
                <div className="absolute -top-1 -right-1 w-6 h-6 bg-gradient-to-br from-blue-400 to-indigo-500 rounded-full flex items-center justify-center">
                  <Sparkles className="w-3 h-3 text-white" />
                </div>
              </div>
            </div>
            
            <h2 className="text-3xl mb-3 text-gray-900">
              Processing Your Documents
            </h2>
            <p className="text-gray-600">
              Analyzing {fileCount} {fileCount === 1 ? 'document' : 'documents'} with AI...
            </p>
          </div>

          <div className="mb-8">
            <Progress value={progress} className="h-2" />
            <p className="text-sm text-gray-500 text-center mt-2">
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
                  className={`flex items-center gap-4 p-4 rounded-lg transition-all ${
                    isActive
                      ? 'bg-blue-50 border-2 border-blue-200'
                      : isComplete
                      ? 'bg-green-50 border-2 border-green-200'
                      : 'bg-gray-50 border-2 border-gray-200'
                  }`}
                >
                  <div
                    className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
                      isActive
                        ? 'bg-blue-600'
                        : isComplete
                        ? 'bg-green-600'
                        : 'bg-gray-400'
                    }`}
                  >
                    <StepIcon
                      className={`w-5 h-5 text-white ${
                        isActive ? 'animate-pulse' : ''
                      }`}
                    />
                  </div>
                  <span
                    className={`${
                      isActive || isComplete
                        ? 'text-gray-900'
                        : 'text-gray-500'
                    }`}
                  >
                    {step.label}
                  </span>
                  {isActive && (
                    <Loader2 className="w-4 h-4 text-blue-600 animate-spin ml-auto" />
                  )}
                  {isComplete && (
                    <div className="w-4 h-4 bg-green-600 rounded-full ml-auto flex items-center justify-center">
                      <svg
                        className="w-3 h-3 text-white"
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
