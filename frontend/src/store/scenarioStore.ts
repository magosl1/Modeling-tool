import { create } from 'zustand'

/**
 * Tracks the currently active scenario across the app.
 *
 * Scoped per-project: switching projects resets the active scenario so we
 * never accidentally apply Project A's "Upside" id to Project B's queries.
 *
 * `null` means "Base scenario" (the legacy NULL bucket on the backend).
 */
interface ScenarioState {
  projectId: string | null
  activeScenarioId: string | null
  setActiveScenario: (projectId: string, scenarioId: string | null) => void
}

export const useScenarioStore = create<ScenarioState>((set) => ({
  projectId: null,
  activeScenarioId: null,
  setActiveScenario: (projectId, scenarioId) => set({ projectId, activeScenarioId: scenarioId }),
}))

export function useActiveScenarioId(projectId: string): string | null {
  const state = useScenarioStore()
  // If the store still references a different project, treat as base until
  // ScenarioManager (or whoever) explicitly sets it for this project.
  return state.projectId === projectId ? state.activeScenarioId : null
}
