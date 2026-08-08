import React from 'react';
import { Home, Search, Users, Briefcase, Layers, BarChart3, GitBranch, BookOpen, Database, Settings } from 'lucide-react-native';

export interface NavItem {
  name: string;
  route: string;
  icon: React.ElementType;
  description?: string;
}

export const NAV_ITEMS: NavItem[] = [
  { name: 'Home', route: '/', icon: Home, description: 'Dashboard & System Health' },
  { name: 'Match', route: '/cv-match', icon: Search, description: 'CV Parsing & Semantic Job Matching' },
  { name: 'Candidates', route: '/candidates', icon: Users, description: 'Candidate Directory & Scored Profiles' },
  { name: 'Jobs', route: '/vacancies', icon: Briefcase, description: 'Job Openings & Requirement Hierarchy' },
  { name: 'Batch', route: '/batch', icon: Layers, description: 'Batch CV Ingestion & Processing' },
  { name: 'Analytics', route: '/analytics', icon: BarChart3, description: 'Pipeline Telemetry & Performance SLOs' },
  { name: 'Knowledge Graph', route: '/knowledge-graph', icon: GitBranch, description: 'Entity Relationships & Taxonomy' },
  { name: 'Domain Explorer', route: '/domain-explorer', icon: BookOpen, description: 'Domain Hierarchies & Mappings' },
  { name: 'Training Data', route: '/training-data', icon: Database, description: 'HR Feedback & Calibration Records' },
  { name: 'Config', route: '/config', icon: Settings, description: 'Match Engine Weights & Thresholds' },
];
