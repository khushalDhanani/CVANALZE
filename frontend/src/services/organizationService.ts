import { apiClient } from './apiClient';
import {
  BusinessGroupItem,
  CompanyItem,
  DepartmentItem,
  DesignationItem,
  HierarchyValidationResult,
  LocationItem,
  MainDepartmentItem,
  OrganizationSelection,
} from '@/types/api';

export const organizationService = {
  getBusinessGroups: (): Promise<BusinessGroupItem[]> => {
    return apiClient.get<BusinessGroupItem[]>('/api/organization/business-groups');
  },

  getCompanies: (businessGroupId?: number | null): Promise<CompanyItem[]> => {
    const params = businessGroupId != null ? { business_group_id: businessGroupId } : undefined;
    return apiClient.get<CompanyItem[]>('/api/organization/companies', { params });
  },

  getLocations: (companyId?: number | null): Promise<LocationItem[]> => {
    const params = companyId != null ? { company_id: companyId } : undefined;
    return apiClient.get<LocationItem[]>('/api/organization/locations', { params });
  },

  getMainDepartments: (): Promise<MainDepartmentItem[]> => {
    return apiClient.get<MainDepartmentItem[]>('/api/organization/main-departments');
  },

  getDepartments: (
    companyId?: number | null,
    mainDepartmentId?: number | null
  ): Promise<DepartmentItem[]> => {
    const params: Record<string, number> = {};
    if (companyId != null) params.company_id = companyId;
    if (mainDepartmentId != null) params.main_department_id = mainDepartmentId;
    return apiClient.get<DepartmentItem[]>('/api/organization/departments', { params });
  },

  getDesignations: (
    companyId?: number | null,
    departmentId?: number | null,
    mainDepartmentId?: number | null
  ): Promise<DesignationItem[]> => {
    const params: Record<string, number> = {};
    if (companyId != null) params.company_id = companyId;
    if (departmentId != null) params.department_id = departmentId;
    if (mainDepartmentId != null) params.main_department_id = mainDepartmentId;
    return apiClient.get<DesignationItem[]>('/api/organization/designations', { params });
  },

  getHierarchy: (): Promise<any> => {
    return apiClient.get<any>('/api/organization/hierarchy');
  },

  validateHierarchy: (selection: OrganizationSelection): Promise<HierarchyValidationResult> => {
    return apiClient.post<HierarchyValidationResult>('/api/organization/validate', selection);
  },
};
