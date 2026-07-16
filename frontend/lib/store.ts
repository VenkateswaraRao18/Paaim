'use client';

import { create } from 'zustand';
import type { Decision, Event } from './api-client';

interface DashboardState {
  // UI State
  selectedFactoryId: string;
  selectedDecisionId: string | null;
  activeTab: 'incidents' | 'scenarios' | 'decisions' | 'audit';

  // Data
  incidents: Event[];
  decisions: Decision[];
  activeDecision: Decision | null;

  // Filters
  filterEventType: string | null;
  filterRiskLevel: string | null;
  dateRange: { start: Date; end: Date } | null;

  // Real-time
  isLiveUpdating: boolean;

  // Actions
  setSelectedFactory: (id: string) => void;
  setSelectedDecision: (id: string | null) => void;
  setActiveTab: (tab: 'incidents' | 'scenarios' | 'decisions' | 'audit') => void;
  setIncidents: (incidents: Event[]) => void;
  setDecisions: (decisions: Decision[]) => void;
  setActiveDecision: (decision: Decision | null) => void;
  addDecision: (decision: Decision) => void;
  setFilterEventType: (type: string | null) => void;
  setFilterRiskLevel: (level: string | null) => void;
  setDateRange: (range: { start: Date; end: Date } | null) => void;
  setLiveUpdating: (updating: boolean) => void;
  clearFilters: () => void;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  selectedFactoryId: 'factory_001',
  selectedDecisionId: null,
  activeTab: 'incidents',
  incidents: [],
  decisions: [],
  activeDecision: null,
  filterEventType: null,
  filterRiskLevel: null,
  dateRange: null,
  isLiveUpdating: true,

  setSelectedFactory: (id) => set({ selectedFactoryId: id }),
  setSelectedDecision: (id) => set({ selectedDecisionId: id }),
  setActiveTab: (tab: 'incidents' | 'scenarios' | 'decisions' | 'audit') => set({ activeTab: tab }),
  setIncidents: (incidents) => set({ incidents }),
  setDecisions: (decisions) => set({ decisions }),
  setActiveDecision: (decision) => set({ activeDecision: decision }),

  addDecision: (decision) =>
    set((state) => ({
      decisions: [decision, ...state.decisions],
      activeDecision: decision,
    })),

  setFilterEventType: (type) => set({ filterEventType: type }),
  setFilterRiskLevel: (level) => set({ filterRiskLevel: level }),
  setDateRange: (range) => set({ dateRange: range }),
  setLiveUpdating: (updating) => set({ isLiveUpdating: updating }),

  clearFilters: () =>
    set({
      filterEventType: null,
      filterRiskLevel: null,
      dateRange: null,
    }),
}));

// Selector hooks for better performance
export const useSelectedFactory = () =>
  useDashboardStore((state) => state.selectedFactoryId);

export const useActiveTab = () =>
  useDashboardStore((state) => state.activeTab);

export const useActiveDecision = () =>
  useDashboardStore((state) => state.activeDecision);

export const useFilters = () =>
  useDashboardStore((state) => ({
    eventType: state.filterEventType,
    riskLevel: state.filterRiskLevel,
    dateRange: state.dateRange,
  }));

export const useLiveUpdating = () =>
  useDashboardStore((state) => state.isLiveUpdating);
