import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, Text, View } from 'react-native';
import { CheckCircle, AlertTriangle, Building2, MapPin, Layers, Briefcase, Award } from 'lucide-react-native';
import { organizationService } from '@/services/organizationService';
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
import { COLORS } from '@/constants/colors';

interface OrganizationHierarchySelectorProps {
  value: OrganizationSelection;
  onChange: (newValue: OrganizationSelection) => void;
  disabled?: boolean;
  compact?: boolean;
  showLabels?: boolean;
}

export function OrganizationHierarchySelector({
  value,
  onChange,
  disabled = false,
  compact = false,
  showLabels = true,
}: OrganizationHierarchySelectorProps) {
  const [businessGroups, setBusinessGroups] = useState<BusinessGroupItem[]>([]);
  const [companies, setCompanies] = useState<CompanyItem[]>([]);
  const [locations, setLocations] = useState<LocationItem[]>([]);
  const [mainDepartments, setMainDepartments] = useState<MainDepartmentItem[]>([]);
  const [departments, setDepartments] = useState<DepartmentItem[]>([]);
  const [designations, setDesignations] = useState<DesignationItem[]>([]);

  const [loadingBg, setLoadingBg] = useState(false);
  const [loadingComp, setLoadingComp] = useState(false);
  const [loadingLoc, setLoadingLoc] = useState(false);
  const [loadingMd, setLoadingMd] = useState(false);
  const [loadingDept, setLoadingDept] = useState(false);
  const [loadingDesig, setLoadingDesig] = useState(false);

  const [validationResult, setValidationResult] = useState<HierarchyValidationResult | null>(null);

  // 1. Fetch Business Groups & Main Depts on mount
  useEffect(() => {
    setLoadingBg(true);
    organizationService
      .getBusinessGroups()
      .then(setBusinessGroups)
      .catch(() => setBusinessGroups([]))
      .finally(() => setLoadingBg(false));

    setLoadingMd(true);
    organizationService
      .getMainDepartments()
      .then(setMainDepartments)
      .catch(() => setMainDepartments([]))
      .finally(() => setLoadingMd(false));
  }, []);

  // 2. Fetch Companies when Business Group changes
  useEffect(() => {
    setLoadingComp(true);
    organizationService
      .getCompanies(value.business_group_id)
      .then(setCompanies)
      .catch(() => setCompanies([]))
      .finally(() => setLoadingComp(false));
  }, [value.business_group_id]);

  // 3. Fetch Locations when Company changes
  useEffect(() => {
    setLoadingLoc(true);
    organizationService
      .getLocations(value.company_id)
      .then(setLocations)
      .catch(() => setLocations([]))
      .finally(() => setLoadingLoc(false));
  }, [value.company_id]);

  // 4. Fetch Departments when Company or Main Department changes
  useEffect(() => {
    setLoadingDept(true);
    organizationService
      .getDepartments(value.company_id, value.main_department_id)
      .then(setDepartments)
      .catch(() => setDepartments([]))
      .finally(() => setLoadingDept(false));
  }, [value.company_id, value.main_department_id]);

  // 5. Fetch Designations when Company, Department, or Main Department changes
  useEffect(() => {
    setLoadingDesig(true);
    organizationService
      .getDesignations(value.company_id, value.department_id, value.main_department_id)
      .then(setDesignations)
      .catch(() => setDesignations([]))
      .finally(() => setLoadingDesig(false));
  }, [value.company_id, value.department_id, value.main_department_id]);

  // 6. Validate hierarchy whenever selection changes
  useEffect(() => {
    const hasSelection =
      value.business_group_id != null ||
      value.company_id != null ||
      value.location_id != null ||
      value.main_department_id != null ||
      value.department_id != null ||
      value.designation_id != null;

    if (!hasSelection) {
      setValidationResult(null);
      return;
    }

    organizationService
      .validateHierarchy(value)
      .then(setValidationResult)
      .catch(() => setValidationResult(null));
  }, [
    value.business_group_id,
    value.company_id,
    value.location_id,
    value.main_department_id,
    value.department_id,
    value.designation_id,
  ]);

  // Parent Change Handlers with Cascading Reset
  const handleBusinessGroupChange = (bgId: number | null) => {
    onChange({
      ...value,
      business_group_id: bgId,
      company_id: null,
      location_id: null,
      department_id: null,
      designation_id: null,
    });
  };

  const handleCompanyChange = (compId: number | null) => {
    onChange({
      ...value,
      company_id: compId,
      location_id: null,
      department_id: null,
      designation_id: null,
    });
  };

  const handleLocationChange = (locId: number | null) => {
    onChange({
      ...value,
      location_id: locId,
      // Location is a Company child context; changing location does NOT clear department or designation selections
    });
  };


  const handleMainDeptChange = (mdId: number | null) => {
    onChange({
      ...value,
      main_department_id: mdId,
      department_id: null,
      designation_id: null,
    });
  };

  const handleDepartmentChange = (deptId: number | null) => {
    onChange({
      ...value,
      department_id: deptId,
      designation_id: null,
    });
  };

  const handleDesignationChange = (desigId: number | null) => {
    onChange({
      ...value,
      designation_id: desigId,
    });
  };

  // Helper render method for cascading select rows
  const renderSelectorRow = (
    label: string,
    icon: React.ReactNode,
    options: { id: number; name: string }[],
    selectedValue: number | null | undefined,
    onSelect: (id: number | null) => void,
    isLoading: boolean
  ) => (
    <View className="mb-2.5">
      {showLabels && (
        <View className="flex-row items-center gap-1 mb-1">
          {icon}
          <Text className="text-[10px] font-sans-bold text-text-muted uppercase tracking-wider">
            {label}
          </Text>
          {isLoading && <ActivityIndicator size="small" color={COLORS.primary} />}
        </View>
      )}

      <View className="flex-row flex-wrap gap-1">
        <Pressable
          disabled={disabled}
          onPress={() => onSelect(null)}
          className={`px-2 py-1 rounded border ${
            selectedValue == null
              ? 'bg-primary/10 border-primary'
              : 'bg-surface border-border opacity-70'
          }`}
        >
          <Text
            className={`text-xs font-sans-medium ${
              selectedValue == null ? 'text-primary' : 'text-text-muted'
            }`}
          >
            All
          </Text>
        </Pressable>

        {options.slice(0, 10).map((opt) => {
          const isSelected = selectedValue === opt.id;
          return (
            <Pressable
              key={opt.id}
              disabled={disabled}
              onPress={() => onSelect(isSelected ? null : opt.id)}
              className={`px-2 py-1 rounded border ${
                isSelected
                  ? 'bg-primary border-primary'
                  : 'bg-surface border-border active:bg-background'
              }`}
            >
              <Text
                className={`text-xs font-sans-medium ${
                  isSelected ? 'text-white font-sans-semibold' : 'text-text-primary'
                }`}
                numberOfLines={1}
              >
                {opt.name}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );

  return (
    <View className="bg-surface border border-border rounded-lg p-3">
      <Text className="text-xs font-sans-bold text-text-primary uppercase tracking-wider mb-2">
        Organization Hierarchy
      </Text>

      {/* 1. Business Group */}
      {renderSelectorRow(
        'Business Group',
        <Building2 size={12} color={COLORS.primary} />,
        businessGroups,
        value.business_group_id,
        handleBusinessGroupChange,
        loadingBg
      )}

      {/* 2. Company */}
      {renderSelectorRow(
        'Company',
        <Building2 size={12} color={COLORS.info} />,
        companies,
        value.company_id,
        handleCompanyChange,
        loadingComp
      )}

      {/* 3. Location */}
      {renderSelectorRow(
        'Location',
        <MapPin size={12} color={COLORS.warning} />,
        locations,
        value.location_id,
        handleLocationChange,
        loadingLoc
      )}

      {/* 4. Main Department */}
      {renderSelectorRow(
        'Main Department',
        <Layers size={12} color={COLORS.secondary} />,
        mainDepartments,
        value.main_department_id,
        handleMainDeptChange,
        loadingMd
      )}

      {/* 5. Department */}
      {renderSelectorRow(
        'Department',
        <Briefcase size={12} color={COLORS.success} />,
        departments,
        value.department_id,
        handleDepartmentChange,
        loadingDept
      )}

      {/* 6. Designation */}
      {renderSelectorRow(
        'Designation',
        <Award size={12} color={COLORS.accent} />,
        designations,
        value.designation_id,
        handleDesignationChange,
        loadingDesig
      )}

      {/* Validation Status Indicator */}
      {validationResult && (
        <View
          className={`mt-2 p-2 rounded flex-row items-center gap-1.5 border ${
            validationResult.is_valid
              ? 'bg-success/10 border-success/30'
              : 'bg-danger/10 border-danger/30'
          }`}
        >
          {validationResult.is_valid ? (
            <CheckCircle size={14} color={COLORS.success} />
          ) : (
            <AlertTriangle size={14} color={COLORS.danger} />
          )}
          <Text
            className={`text-xs font-sans-medium ${
              validationResult.is_valid ? 'text-success' : 'text-danger'
            }`}
          >
            {validationResult.is_valid
              ? 'Valid Organization Hierarchy Selection'
              : validationResult.errors.join(' | ')}
          </Text>
        </View>
      )}
    </View>
  );
}
