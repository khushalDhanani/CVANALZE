export type HierarchyValidationState = 'VALID' | 'INVALID' | 'UNAVAILABLE';

export const getHierarchyValidationState = (isHierarchyValid: boolean | null | undefined): HierarchyValidationState => {
  if (isHierarchyValid === true) return 'VALID';
  if (isHierarchyValid === false) return 'INVALID';
  return 'UNAVAILABLE';
};
