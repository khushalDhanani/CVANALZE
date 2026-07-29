import { useCallback, useState } from 'react';
import { API_CONFIG } from '@/constants/config';
import { cvService } from '@/services/cvService';
import { matchService } from '@/services/matchService';
import {
  CVProcessingResponse,
  CVUploadResponse,
  EnrichedCandidateAnalysis,
} from '@/types/api';

export interface FilePickerAsset {
  uri: string;
  name: string;
  type: string;
  rawFile?: any;
}

export function useCvUpload() {
  const [uploading, setUploading] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [basicResult, setBasicResult] = useState<CVUploadResponse | null>(null);
  const [enrichedResult, setEnrichedResult] =
    useState<EnrichedCandidateAnalysis | null>(null);

  const pollCvStatus = useCallback(
    async (cvKey: string, isEnriched: boolean = false) => {
      let attempts = 0;
      const interval = setInterval(async () => {
        attempts++;
        if (attempts > API_CONFIG.MAX_POLL_RETRIES) {
          clearInterval(interval);
          setUploading(false);
          setError('Processing is taking longer than expected. The backend may still be working — please check the candidates list later.');
          return;
        }

        try {
          if (isEnriched) {
            const res = await matchService.getMatchStatus(cvKey);
            if ('scan_id' in res) {
              clearInterval(interval);
              setEnrichedResult(res as EnrichedCandidateAnalysis);
              setUploading(false);
              setStatusMessage('Enriched analysis complete!');
              setTimeout(() => setStatusMessage(null), 3000);
            } else {
              setStatusMessage(
                (res as CVProcessingResponse).message || 'Processing LLM match...'
              );
            }
          } else {
            const res = await cvService.getCvStatus(cvKey);
            if ('scan_id' in res) {
              clearInterval(interval);
              setBasicResult(res as CVUploadResponse);
              setUploading(false);
              setStatusMessage('CV parsing complete!');
              setTimeout(() => setStatusMessage(null), 3000);
            } else {
              setStatusMessage(
                (res as CVProcessingResponse).message || 'Parsing CV...'
              );
            }
          }
        } catch (err: any) {
          clearInterval(interval);
          setUploading(false);
          setError(err.message || 'Status check failed');
        }
      }, API_CONFIG.POLL_INTERVAL_MS);
    },
    []
  );

  const uploadAndProcess = useCallback(
    async (file: FilePickerAsset, enrichWithLlm: boolean = false) => {
      setUploading(true);
      setError(null);
      setBasicResult(null);
      setEnrichedResult(null);
      setStatusMessage('Starting upload...');

      try {
        if (enrichWithLlm) {
          const res = await matchService.uploadAndAnalyze(file);
          setStatusMessage(res.message);
          pollCvStatus(res.cv_key, true);
        } else {
          const res = await cvService.uploadCv(file);
          setStatusMessage(res.message);
          pollCvStatus(res.cv_key, false);
        }
      } catch (err: any) {
        setUploading(false);
        setError(err.message || 'Upload failed');
      }
    },
    [pollCvStatus]
  );

  return {
    uploading,
    statusMessage,
    error,
    basicResult,
    enrichedResult,
    uploadAndProcess,
  };
}
