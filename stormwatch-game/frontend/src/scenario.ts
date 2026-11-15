export const campaignStages = [
  {
    id: 'first-drop', title: 'The First Drop', short: '01 · OBSERVE',
    objectiveIds: ['station', 'average'],
  },
  {
    id: 'hidden-pattern', title: 'The Hidden Flood Pattern', short: '02 · SMOOTH',
    objectiveIds: ['window-experiment', 'choose-window'],
  },
  {
    id: 'predict-flood', title: 'Predict the Flood', short: '03 · MODEL',
    objectiveIds: ['manual-line', 'best-fit', 'rainfall-forecast'],
  },
  {
    id: 'prediction-failure', title: 'The Prediction Failure', short: '04 · EVALUATE',
    objectiveIds: ['compare-errors', 'select-model'],
  },
  {
    id: 'save-novara', title: 'Save Novara', short: '05 · RESPOND',
    objectiveIds: ['start-storm', 'place-resource', 'advance-storm', 'evaluate-access'],
  },
] as const;

export type CampaignStageId = typeof campaignStages[number]['id'];
export type CampaignProgress = {
  stageId: CampaignStageId;
  completedStageIds: CampaignStageId[];
  objectives: Partial<Record<CampaignStageId, string[]>>;
  selectedModel: 'moving_average' | 'linear_regression' | null;
  chosenWindowSize: number | null;
  tutorialProgress: Partial<Record<CampaignStageId, TutorialCheckpoint>>;
};

export type TutorialCheckpoint = {
  stepId: string | null;
  completedStepIds: string[];
  results: Record<string, string>;
  skipped: boolean;
};

const STORAGE_KEY = 'stormwatch.eastbank.campaign.v1';
export const createEmptyCampaignProgress = (): CampaignProgress => ({
  stageId: campaignStages[0].id,
  completedStageIds: [],
  objectives: {},
  selectedModel: null,
  chosenWindowSize: null,
  tutorialProgress: {},
});

/** Clear saved campaign progress and return a clean first mission state. */
export function resetCampaignProgress(): CampaignProgress {
  const progress = createEmptyCampaignProgress();
  saveCampaignProgress(progress);
  return progress;
}

export function loadCampaignProgress(): CampaignProgress {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return createEmptyCampaignProgress();
    const value = JSON.parse(raw) as Partial<CampaignProgress>;
    const validIds = campaignStages.map(stage => stage.id);
    const completedStageIds = (value.completedStageIds ?? []).filter((id): id is CampaignStageId => validIds.includes(id as CampaignStageId));
    const objectiveMap: CampaignProgress['objectives'] = {};
    for (const stage of campaignStages) {
      const done = value.objectives?.[stage.id];
      if (Array.isArray(done)) objectiveMap[stage.id] = done.filter(id => stage.objectiveIds.includes(id as never));
    }
    const tutorialProgress: CampaignProgress['tutorialProgress'] = {};
    for (const stage of campaignStages) {
      const saved = value.tutorialProgress?.[stage.id];
      if (!saved || typeof saved !== 'object') continue;
      tutorialProgress[stage.id] = {
        stepId: typeof saved.stepId === 'string' ? saved.stepId : null,
        completedStepIds: Array.isArray(saved.completedStepIds) ? saved.completedStepIds.filter((id): id is string => typeof id === 'string') : [],
        results: saved.results && typeof saved.results === 'object'
          ? Object.fromEntries(Object.entries(saved.results).filter((entry): entry is [string, string] => typeof entry[1] === 'string'))
          : {},
        skipped: saved.skipped === true,
      };
    }
    const unlockedIndex = Math.min(campaignStages.length - 1, completedStageIds.length);
    const requestedStage = validIds.includes(value.stageId as CampaignStageId) ? value.stageId as CampaignStageId : campaignStages[unlockedIndex].id;
    const requestedIndex = campaignStages.findIndex(stage => stage.id === requestedStage);
    return {
      stageId: requestedIndex <= unlockedIndex ? requestedStage : campaignStages[unlockedIndex].id,
      completedStageIds,
      objectives: objectiveMap,
      selectedModel: value.selectedModel === 'moving_average' || value.selectedModel === 'linear_regression' ? value.selectedModel : null,
      chosenWindowSize: Number.isInteger(value.chosenWindowSize) ? value.chosenWindowSize! : null,
      tutorialProgress,
    };
  } catch {
    return createEmptyCampaignProgress();
  }
}

export function saveCampaignProgress(progress: CampaignProgress): void {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(progress)); } catch { /* storage can be disabled; campaign remains playable */ }
}

export function isStageUnlocked(progress: CampaignProgress, stageId: CampaignStageId): boolean {
  const index = campaignStages.findIndex(stage => stage.id === stageId);
  return index === 0 || progress.completedStageIds.includes(campaignStages[index - 1].id);
}

export function markCampaignObjective(progress: CampaignProgress, objectiveId: string): CampaignProgress {
  const stage = campaignStages.find(item => item.id === progress.stageId)!;
  if (!stage.objectiveIds.includes(objectiveId as never)) return progress;
  const current = progress.objectives[stage.id] ?? [];
  if (current.includes(objectiveId)) return progress;
  const objectives = { ...progress.objectives, [stage.id]: [...current, objectiveId] };
  const complete = stage.objectiveIds.every(id => objectives[stage.id]?.includes(id));
  const completedStageIds = complete && !progress.completedStageIds.includes(stage.id)
    ? [...progress.completedStageIds, stage.id]
    : progress.completedStageIds;
  const next: CampaignProgress = { ...progress, objectives, completedStageIds };
  saveCampaignProgress(next);
  return next;
}

export function selectCampaignStage(progress: CampaignProgress, stageId: CampaignStageId): CampaignProgress {
  if (!isStageUnlocked(progress, stageId)) return progress;
  const next = { ...progress, stageId };
  saveCampaignProgress(next);
  return next;
}

export function resetCampaignStageProgress(progress: CampaignProgress, stageId: CampaignStageId): CampaignProgress {
  const objectives = { ...progress.objectives };
  delete objectives[stageId];
  const tutorialProgress = { ...progress.tutorialProgress };
  delete tutorialProgress[stageId];
  const next = {
    ...progress,
    stageId,
    objectives,
    completedStageIds: progress.completedStageIds.filter(id => id !== stageId),
    tutorialProgress,
  };
  saveCampaignProgress(next);
  return next;
}

export function saveTutorialCheckpoint(
  progress: CampaignProgress,
  stageId: CampaignStageId,
  checkpoint: TutorialCheckpoint,
): CampaignProgress {
  const next: CampaignProgress = {
    ...progress,
    tutorialProgress: { ...progress.tutorialProgress, [stageId]: checkpoint },
  };
  saveCampaignProgress(next);
  return next;
}

export function saveWindowChoice(progress: CampaignProgress, windowSize: number): CampaignProgress {
  const next = { ...progress, chosenWindowSize: windowSize };
  saveCampaignProgress(next);
  return next;
}

export function saveModelChoice(progress: CampaignProgress, model: 'moving_average' | 'linear_regression'): CampaignProgress {
  const next = { ...progress, selectedModel: model };
  saveCampaignProgress(next);
  return next;
}
