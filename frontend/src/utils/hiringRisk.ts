import { HiringRisk } from '@/types/api';

export interface HiringRiskPresentation {
  key: string;
  title: string;
  category: string;
  source: string;
  evidence: string[];
}

export const getHiringRiskPresentation = (risk: HiringRisk): HiringRiskPresentation => {
  const evidence = Array.from(new Set((risk.evidence || []).map((item) => item.trim()).filter(Boolean)));
  return {
    key: risk.risk_code || `${risk.category}:${risk.title}`,
    title: risk.title?.trim() || risk.risk_code,
    category: risk.category?.trim() || 'Requirements',
    source: risk.source?.trim() || 'Deterministic evaluation',
    evidence,
  };
};
