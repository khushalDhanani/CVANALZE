import { useCallback, useRef, useState } from 'react';
import { API_CONFIG } from '@/constants/config';
import { cvService } from '@/services/cvService';
import { matchService } from '@/services/matchService';
import {
  CVProcessingResponse,
  CVUploadResponse,
  EnrichedCandidateAnalysis,
} from '@/types/api';
import { StepState } from '@/components/ui/StepProgressCard';

export interface FilePickerAsset {
  uri: string;
  name: string;
  type: string;
  rawFile?: any;
}

const TOTAL_STEPS = 8;

export function useCvUpload() {
  const [uploading, setUploading] = useState<boolean>(false);
  const [isComplete, setIsComplete] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorDetails, setErrorDetails] = useState<string | null>(null);
  const [failedStepName, setFailedStepName] = useState<string | null>(null);
  const [basicResult, setBasicResult] = useState<CVUploadResponse | null>(null);
  const [enrichedResult, setEnrichedResult] =
    useState<EnrichedCandidateAnalysis | null>(null);

  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const [currentStepIndex, _setCurrentStepIndex] = useState<number>(0);
  const currentStepIndexRef = useRef<number>(0);
  
  const setCurrentStepIndex = useCallback((index: number) => {
    currentStepIndexRef.current = index;
    _setCurrentStepIndex(index);
  }, []);

  const [stepStates, setStepStates] = useState<StepState[]>([
    'pending',
    'pending',
    'pending',
    'pending',
    'pending',
    'pending',
    'pending',
    'pending',
  ]);

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startTimer = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    setElapsedSeconds(0);
    timerRef.current = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);
  }, []);

  const stopTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const updateStepState = useCallback((stepIdx: number, state: StepState, isLlmEnriched: boolean) => {
    setStepStates((prev) => {
      const next = [...prev];
      // Mark all previous steps as completed (unless skipped)
      for (let i = 0; i < stepIdx; i++) {
        if (i === 4 && !isLlmEnriched) {
          next[i] = 'skipped';
        } else if (next[i] !== 'skipped') {
          next[i] = 'completed';
        }
      }
      if (stepIdx === 4 && !isLlmEnriched) {
        next[4] = 'skipped';
      } else {
        next[stepIdx] = state;
      }
      return next;
    });
  }, []);

  const pollCvStatus = useCallback(
    async (cvKey: string, isEnriched: boolean = false) => {
      let attempts = 0;
      const interval = setInterval(async () => {
        attempts++;
        if (attempts > API_CONFIG.MAX_POLL_RETRIES) {
          clearInterval(interval);
          stopTimer();
          setUploading(false);
          setError('Processing is taking longer than expected. The backend may still be working — please check the candidates list later.');
          setStepStates((prev) => {
            const next = [...prev];
            next[currentStepIndexRef.current] = 'failed';
            return next;
          });
          return;
        }

        try {
          if (isEnriched) {
            const res = await matchService.getMatchStatus(cvKey);
            if ('status' in res && (res as CVProcessingResponse).status?.toUpperCase() === 'FAILED') {
              clearInterval(interval);
              stopTimer();
              setUploading(false);
              const failedRes = res as CVProcessingResponse;
              const errMsg = failedRes.message || 'CV processing failed.';
              setError(errMsg);
              setErrorDetails(failedRes.error_details || null);
              setFailedStepName(failedRes.failed_step || null);
              
              const stageMap: Record<string, number> = {
                 'parsing': 2,
                 'extraction': 3,
                 'ai_analysis': 4,
                 'matching': 5,
                 'complete': 7
              };
              let fIndex = currentStepIndexRef.current;
              if (failedRes.stage && stageMap[failedRes.stage] !== undefined) {
                  fIndex = stageMap[failedRes.stage];
              }
              if (fIndex === 4 && !isEnriched) fIndex = 5;
              
              setCurrentStepIndex(fIndex);
              setStepStates((prev) => {
                const next = [...prev];
                next[fIndex] = 'failed';
                return next;
              });
            } else if (
              'scan_id' in res ||
              'match_analysis' in res ||
              (res as any).status === 'COMPLETED' ||
              (res as any).status === 'NEW_CV' ||
              (res as any).status === 'REPROCESSED' ||
              (res as any).progress === 100 ||
              (res as any).is_complete === true
            ) {
              clearInterval(interval);
              stopTimer();
              if ('scan_id' in res || 'match_analysis' in res) {
                setEnrichedResult(res as EnrichedCandidateAnalysis);
              }
              setUploading(false);
              setIsComplete(true);
              setCurrentStepIndex(7);
              setStatusMessage('Candidate analysis & job matching complete!');
              setStepStates([
                'completed',
                'completed',
                'completed',
                'completed',
                isEnriched ? 'completed' : 'skipped',
                'completed',
                'completed',
                'completed',
              ]);
            } else {
              const procRes = res as CVProcessingResponse;
              const msg = procRes.message || 'Processing LLM match...';
              setStatusMessage(msg);

              const stageMap: Record<string, number> = {
                 'validation': 1,
                 'parsing': 2,
                 'extraction': 3,
                 'ai_analysis': 4,
                 'matching': 5,
                 'ranking': 6,
                 'complete': 7
              };
              let nextStep = currentStepIndexRef.current;
              if (procRes.stage && stageMap[procRes.stage] !== undefined) {
                  nextStep = stageMap[procRes.stage];
              } else {
                  const prog = procRes.progress || 0;
                  if (prog >= 90) nextStep = 6;
                  else if (prog >= 75) nextStep = 5;
                  else if (prog >= 50) nextStep = 4;
                  else if (prog >= 35) nextStep = 3;
                  else if (prog >= 20) nextStep = 2;
                  else if (prog >= 10) nextStep = 1;
              }

              if (nextStep === 4 && !isEnriched) {
                nextStep = 5;
              }

              setCurrentStepIndex(nextStep);
              updateStepState(nextStep, 'active', isEnriched);
            }
          } else {
            const res = await cvService.getCvStatus(cvKey);
            if ('status' in res && (res as CVProcessingResponse).status?.toUpperCase() === 'FAILED') {
              clearInterval(interval);
              stopTimer();
              setUploading(false);
              const failedRes = res as CVProcessingResponse;
              const errMsg = failedRes.message || 'CV processing failed.';
              setError(errMsg);
              setErrorDetails(failedRes.error_details || null);
              setFailedStepName(failedRes.failed_step || null);
              
              const stageMap: Record<string, number> = {
                 'validation': 1,
                 'parsing': 2,
                 'extraction': 3,
                 'ai_analysis': 4,
                 'matching': 5,
                 'ranking': 6,
                 'complete': 7
              };
              let fIndex = currentStepIndexRef.current;
              if (failedRes.stage && stageMap[failedRes.stage] !== undefined) {
                  fIndex = stageMap[failedRes.stage];
              }
              if (fIndex === 4 && !isEnriched) fIndex = 5;
              
              setCurrentStepIndex(fIndex);
              setStepStates((prev) => {
                const next = [...prev];
                next[fIndex] = 'failed';
                return next;
              });
            } else if (
              'scan_id' in res ||
              'match_analysis' in res ||
              (res as any).status === 'COMPLETED' ||
              (res as any).status === 'NEW_CV' ||
              (res as any).status === 'REPROCESSED' ||
              (res as any).progress === 100
            ) {
              clearInterval(interval);
              stopTimer();
              setBasicResult(res as CVUploadResponse);
              setUploading(false);
              setIsComplete(true);
              setCurrentStepIndex(7);
              setStatusMessage('CV parsing & job matching complete!');
              setStepStates([
                'completed',
                'completed',
                'completed',
                'completed',
                'skipped',
                'completed',
                'completed',
                'completed',
              ]);
            } else {
              const procRes = res as CVProcessingResponse;
              const msg = procRes.message || 'Parsing CV...';
              setStatusMessage(msg);

              const stageMap: Record<string, number> = {
                 'validation': 1,
                 'parsing': 2,
                 'extraction': 3,
                 'ai_analysis': 4,
                 'matching': 5,
                 'ranking': 6,
                 'complete': 7
              };
              let nextStep = currentStepIndexRef.current;
              if (procRes.stage && stageMap[procRes.stage] !== undefined) {
                  nextStep = stageMap[procRes.stage];
              } else {
                  const prog = procRes.progress || 0;
                  if (prog >= 90) nextStep = 6;
                  else if (prog >= 75) nextStep = 5;
                  else if (prog >= 50) nextStep = 5; // AI Analysis skipped
                  else if (prog >= 35) nextStep = 3;
                  else if (prog >= 20) nextStep = 2;
                  else if (prog >= 10) nextStep = 1;
              }

              setCurrentStepIndex(nextStep);
              updateStepState(nextStep, 'active', false);
            }
          }
        } catch (err: any) {
          clearInterval(interval);
          stopTimer();
          setUploading(false);
          setError(err.message || 'Status check failed');
          setStepStates((prev) => {
            const next = [...prev];
            next[currentStepIndexRef.current] = 'failed';
            return next;
          });
        }
      }, API_CONFIG.POLL_INTERVAL_MS);
    },
    [stopTimer, updateStepState, setCurrentStepIndex]
  );

  const uploadAndProcess = useCallback(
    async (file: FilePickerAsset, enrichWithLlm: boolean = true) => {
      setUploading(true);
      setIsComplete(false);
      setError(null);
      setErrorDetails(null);
      setFailedStepName(null);
      setBasicResult(null);
      setEnrichedResult(null);
      setStatusMessage('Uploading document to server...');
      startTimer();

      const initialStates: StepState[] = [
        'active',
        'pending',
        'pending',
        'pending',
        enrichWithLlm ? 'pending' : 'skipped',
        'pending',
        'pending',
        'pending',
      ];
      setStepStates(initialStates);
      setCurrentStepIndex(0);

      try {
        if (enrichWithLlm) {
          const res = await matchService.uploadAndAnalyze(file);
          setStatusMessage('Document uploaded. Validating format & parsing...');
          setCurrentStepIndex(1);
          setStepStates([
            'completed',
            'active',
            'pending',
            'pending',
            'pending',
            'pending',
            'pending',
            'pending',
          ]);
          pollCvStatus(res.cv_key, true);
        } else {
          const res = await cvService.uploadCv(file);
          setStatusMessage('Document uploaded. Validating format & parsing...');
          setCurrentStepIndex(1);
          setStepStates([
            'completed',
            'active',
            'pending',
            'pending',
            'skipped',
            'pending',
            'pending',
            'pending',
          ]);
          pollCvStatus(res.cv_key, false);
        }
      } catch (err: any) {
        stopTimer();
        setUploading(false);
        setError(err.message || 'Upload failed');
        setStepStates((prev) => {
          const next = [...prev];
          next[0] = 'failed';
          return next;
        });
      }
    },
    [pollCvStatus, startTimer, stopTimer]
  );

  return {
    uploading,
    isComplete,
    statusMessage,
    error,
    errorDetails,
    failedStepName,
    basicResult,
    enrichedResult,
    elapsedSeconds,
    currentStepIndex,
    stepStates,
    uploadAndProcess,
  };
}
