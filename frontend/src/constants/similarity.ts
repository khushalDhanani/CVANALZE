export const SIMILARITY_CONFIG = {
  defaultThreshold: 0.82,
  defaultLimit: 5,
  minThreshold: 0.0,
  maxThreshold: 1.0,
  minLimit: 1,
  maxLimit: 50,
  bands: {
    high: 0.9,
    medium: 0.8,
  },
  getTone: (score: number): 'success' | 'info' | 'warning' => {
    if (score >= 0.9) return 'success';
    if (score >= 0.8) return 'info';
    return 'warning';
  },
};
