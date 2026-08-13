import type { CVUploadResponse } from '@/types/api';

export interface CandidateReanalysisAction {
  scanId: string;
  reanalyze: (scanId: string) => Promise<CVUploadResponse>;
  commit: (candidate: CVUploadResponse) => void;
  isCurrent?: () => boolean;
}

export async function reanalyzeCandidateAndCommit(action: CandidateReanalysisAction): Promise<CVUploadResponse> {
  const updatedCandidate = await action.reanalyze(action.scanId);
  if (!action.isCurrent || action.isCurrent()) action.commit(updatedCandidate);
  return updatedCandidate;
}
