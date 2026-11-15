export type GameMode = 'guided-campaign' | 'free-play';
export type ActivityMode = 'simulation' | 'analysis' | 'prediction' | 'response';
export type ContextActivity = 'location' | 'weather' | 'moving-average' | 'regression' | 'evaluation' | 'response';

export interface UiState {
  gameMode: GameMode;
  activityMode: ActivityMode;
  contextActivity: ContextActivity;
}

type Listener = (state: Readonly<UiState>) => void;

/** UI-only state. Backend simulation and analytics results remain authoritative. */
export function createUiStateStore(initial: UiState = {
  gameMode: 'guided-campaign',
  activityMode: 'simulation',
  contextActivity: 'location',
}) {
  let state: UiState = { ...initial };
  const listeners = new Set<Listener>();

  return {
    getState: () => state as Readonly<UiState>,
    setState: (update: Partial<UiState>) => {
      state = { ...state, ...update };
      listeners.forEach(listener => listener(state));
    },
    subscribe: (listener: Listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
