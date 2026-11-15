import type { TutorialCheckpoint } from './scenario';

export type TutorialTarget =
  | { type: 'element'; selector: string }
  | { type: 'map-location'; locationId: string };

export interface TutorialStep<Result = unknown> {
  id: string;
  title: string;
  explanation: string;
  story: string;
  target: TutorialTarget;
  targetLabel: string;
  requiredAction: string;
  unlocksAfter?: string[];
  hint?: string;
  feedback: string;
  validate: (result: Result) => boolean;
  formatResult?: (result: Result) => string;
}

type TutorialCallbacks = {
  resolveMapTarget: (locationId: string) => DOMRect | null;
  focusMapTarget: (locationId: string | null) => void;
  persist: (missionId: string, checkpoint: TutorialCheckpoint) => void;
  onMessage: (message: string) => void;
  onStepChanged: (step: TutorialStep | null) => void;
};

/** Guided, action-validated instruction layer. Progress is persisted by CampaignProgress. */
export class GuidedTutorial {
  private readonly layer: HTMLDivElement;
  private readonly spotlight: HTMLDivElement;
  private readonly bubble: HTMLElement;
  private readonly title: HTMLElement;
  private readonly explanation: HTMLElement;
  private readonly counter: HTMLElement;
  private readonly hintText: HTMLElement;
  private readonly feedback: HTMLElement;
  private readonly nextButton: HTMLButtonElement;
  private readonly backButton: HTMLButtonElement;
  private readonly hintButton: HTMLButtonElement;
  private readonly skipButton: HTMLButtonElement;
  private stepDefinitions: TutorialStep[] = [];
  private missionId: string | null = null;
  private checkpoint: TutorialCheckpoint = { stepId: null, completedStepIds: [], results: {}, skipped: false };
  private targetElement: HTMLElement | null = null;
  private tracking = false;
  private hintOpen = false;
  private available = true;

  constructor(private readonly callbacks: TutorialCallbacks) {
    this.layer = document.createElement('div');
    this.layer.className = 'guided-tutorial-layer';
    this.layer.hidden = true;
    this.layer.setAttribute('aria-live', 'polite');
    this.layer.innerHTML = `
      <div class="tutorial-spotlight" aria-hidden="true"></div>
      <section class="tutorial-bubble" role="dialog" aria-modal="false" aria-labelledby="tutorial-title">
        <div class="tutorial-bubble-head"><span class="tutorial-counter"></span><button class="tutorial-skip" type="button">SKIP GUIDE</button></div>
        <h2 id="tutorial-title"></h2><p class="tutorial-explanation"></p>
        <p class="tutorial-feedback" hidden></p><p class="tutorial-hint" hidden></p>
        <div class="tutorial-controls"><button class="tutorial-back" type="button">BACK</button><button class="tutorial-hint-button" type="button">HINT</button><button class="tutorial-next" type="button" disabled>NEXT</button></div>
      </section>`;
    document.body.append(this.layer);
    this.spotlight = this.layer.querySelector('.tutorial-spotlight')!;
    this.bubble = this.layer.querySelector('.tutorial-bubble')!;
    this.title = this.layer.querySelector('#tutorial-title')!;
    this.explanation = this.layer.querySelector('.tutorial-explanation')!;
    this.counter = this.layer.querySelector('.tutorial-counter')!;
    this.feedback = this.layer.querySelector('.tutorial-feedback')!;
    this.hintText = this.layer.querySelector('.tutorial-hint')!;
    this.nextButton = this.layer.querySelector('.tutorial-next')!;
    this.backButton = this.layer.querySelector('.tutorial-back')!;
    this.hintButton = this.layer.querySelector('.tutorial-hint-button')!;
    this.skipButton = this.layer.querySelector('.tutorial-skip')!;

    this.nextButton.addEventListener('click', () => this.next());
    this.backButton.addEventListener('click', () => this.back());
    this.hintButton.addEventListener('click', () => this.toggleHint());
    this.skipButton.addEventListener('click', () => this.skip());
    window.addEventListener('resize', () => this.position());
    window.addEventListener('scroll', () => this.position(), true);
  }

  configure(missionId: string, steps: TutorialStep[], saved?: TutorialCheckpoint) {
    if (this.missionId === missionId && this.stepDefinitions === steps) {
      this.available = !this.checkpoint.skipped;
      if (this.checkpoint.skipped || this.isFinished()) this.hide(); else this.show();
      return;
    }
    this.missionId = missionId;
    this.stepDefinitions = steps;
    const validIds = new Set(steps.map(step => step.id));
    const savedCompletions = saved?.completedStepIds.filter(id => validIds.has(id)) ?? [];
    this.checkpoint = saved ? {
      stepId: saved.stepId === null && savedCompletions.length === steps.length
        ? null : saved.stepId && validIds.has(saved.stepId) ? saved.stepId : steps[0]?.id ?? null,
      completedStepIds: savedCompletions,
      results: Object.fromEntries(Object.entries(saved.results).filter(([id]) => validIds.has(id))),
      skipped: saved.skipped,
    } : { stepId: steps[0]?.id ?? null, completedStepIds: [], results: {}, skipped: false };
    if (!this.checkpoint.stepId && this.checkpoint.completedStepIds.length < steps.length) {
      this.checkpoint.stepId = steps[0]?.id ?? null;
    }
    this.available = !this.checkpoint.skipped;
    this.persist();
    this.checkpoint.skipped || this.isFinished() ? this.hide() : this.show(true);
  }

  setAvailable(available: boolean) {
    this.available = available;
    if (!available) this.hide();
    else if (!this.checkpoint.skipped && this.stepDefinitions.length) this.show();
  }

  completeAction<Result>(action: string, result: Result): boolean {
    if (!this.available) return false;
    const step = this.currentStep();
    if (!step || step.requiredAction !== action || !step.validate(result)) return false;
    this.checkpoint = {
      ...this.checkpoint,
      completedStepIds: [...new Set([...this.checkpoint.completedStepIds, step.id])],
      results: { ...this.checkpoint.results, [step.id]: step.formatResult?.(result) ?? (typeof result === 'string' ? result : '') },
    };
    this.persist();
    this.callbacks.onMessage(step.feedback);
    this.render();
    return true;
  }

  getCurrentStepId() { return this.checkpoint.stepId; }
  isSkipped() { return this.checkpoint.skipped; }

  replay() {
    if (!this.missionId || !this.stepDefinitions.length) return;
    this.available = true;
    this.checkpoint = { stepId: this.stepDefinitions[0].id, completedStepIds: [], results: {}, skipped: false };
    this.hintOpen = false;
    this.persist();
    this.show(true);
  }

  hide() {
    this.layer.hidden = true;
    this.layer.classList.remove('tutorial-finished');
    this.layer.classList.remove('tutorial-action-complete');
    document.body.classList.remove('tutorial-active');
    this.targetElement?.classList.remove('guided-tutorial-target');
    this.targetElement = null;
    this.callbacks.focusMapTarget(null);
    this.tracking = false;
  }

  private show(announce = false) {
    if (!this.stepDefinitions.length) return;
    this.layer.hidden = false;
    document.body.classList.add('tutorial-active');
    this.tracking = true;
    this.render();
    if (announce) this.callbacks.onMessage(this.currentStep()?.story ?? 'This mission guide is complete.');
    this.trackTarget();
  }

  private currentStep() {
    return this.stepDefinitions.find(step => step.id === this.checkpoint.stepId) ?? null;
  }

  private stepIndex() {
    return this.stepDefinitions.findIndex(step => step.id === this.checkpoint.stepId);
  }

  private isComplete(step: TutorialStep) { return this.checkpoint.completedStepIds.includes(step.id); }

  private isFinished() {
    return this.checkpoint.stepId === null && this.checkpoint.completedStepIds.length === this.stepDefinitions.length;
  }

  private isUnlocked(step: TutorialStep) {
    return (step.unlocksAfter ?? []).every(id => this.checkpoint.completedStepIds.includes(id));
  }

  private next() {
    const step = this.currentStep();
    if (!step && this.checkpoint.completedStepIds.length === this.stepDefinitions.length) {
      this.hide();
      return;
    }
    if (step && (!this.isComplete(step) || !this.isUnlocked(step))) return;
    const index = this.stepIndex();
    if (index < 0 || index >= this.stepDefinitions.length - 1) {
      this.checkpoint = { ...this.checkpoint, stepId: null };
      this.persist();
      this.render();
      return;
    }
    this.checkpoint = { ...this.checkpoint, stepId: this.stepDefinitions[index + 1].id };
    this.hintOpen = false;
    this.persist();
    this.render();
    this.callbacks.onMessage(this.currentStep()?.story ?? 'This mission guide is complete.');
  }

  private back() {
    const index = this.stepIndex();
    if (index <= 0) return;
    const previous = this.stepDefinitions[index - 1];
    const removed = new Set(this.stepDefinitions.slice(index - 1).map(step => step.id));
    this.checkpoint = {
      stepId: previous.id,
      completedStepIds: this.checkpoint.completedStepIds.filter(id => !removed.has(id)),
      results: Object.fromEntries(Object.entries(this.checkpoint.results).filter(([id]) => !removed.has(id))),
      skipped: false,
    };
    this.hintOpen = false;
    this.persist();
    this.render();
  }

  private toggleHint() {
    this.hintOpen = !this.hintOpen;
    this.render();
  }

  private skip() {
    // Skipping dismisses guidance only; it never completes campaign objectives.
    this.checkpoint = { ...this.checkpoint, skipped: true };
    this.available = false;
    this.persist();
    this.hide();
    this.callbacks.onStepChanged(null);
  }

  private persist() {
    if (this.missionId) this.callbacks.persist(this.missionId, this.checkpoint);
  }

  private render() {
    const step = this.currentStep();
    const finished = !step && !this.checkpoint.skipped;
    this.layer.classList.toggle('tutorial-finished', finished);
    if (finished) {
      this.callbacks.focusMapTarget(null);
      this.targetElement?.classList.remove('guided-tutorial-target');
      this.targetElement = null;
      this.spotlight.style.display = 'none';
      this.counter.textContent = 'MISSION GUIDE · COMPLETE';
      this.title.textContent = 'You’re ready for Eastbank';
      this.explanation.textContent = this.missionId === 'save-novara'
        ? 'The final report reflects the storm, city conditions and resources you deployed. Continue exploring Eastbank or replay the campaign.'
        : this.missionId === 'first-drop'
          ? 'The six-hour station record and its Python-calculated average are available in the mission panel. Continue exploring the city.'
          : 'You completed this mission guide. Continue exploring Eastbank or replay the campaign.';
      this.feedback.hidden = true;
      this.hintText.hidden = true;
      this.nextButton.textContent = 'DONE';
      this.nextButton.disabled = false;
      this.backButton.disabled = false;
      this.skipButton.textContent = 'CLOSE';
      this.callbacks.onStepChanged(null);
      this.position();
      return;
    }
    if (!step) return;
    this.layer.classList.toggle('tutorial-action-complete', this.isComplete(step));
    this.counter.textContent = `STEP ${this.stepIndex() + 1} OF ${this.stepDefinitions.length}`;
    this.title.textContent = step.title;
    this.explanation.textContent = step.explanation;
    const result = this.checkpoint.results[step.id];
    this.feedback.textContent = this.isComplete(step) ? `${step.feedback}${result ? ` ${result}` : ''}` : '';
    this.feedback.hidden = !this.isComplete(step);
    this.hintText.textContent = step.hint ?? 'Look closely at the highlighted part of Eastbank.';
    this.hintText.hidden = !this.hintOpen;
    this.nextButton.textContent = this.stepIndex() === this.stepDefinitions.length - 1 ? 'FINISH' : 'NEXT';
    this.nextButton.disabled = !this.isComplete(step) || !this.isUnlocked(step);
    this.backButton.disabled = this.stepIndex() <= 0;
    this.skipButton.textContent = 'SKIP GUIDE';
    this.targetElement?.classList.remove('guided-tutorial-target');
    this.targetElement = null;
    if (step.target.type === 'element') {
      this.targetElement = document.querySelector<HTMLElement>(step.target.selector);
      this.targetElement?.classList.add('guided-tutorial-target');
      this.callbacks.focusMapTarget(null);
    } else {
      this.callbacks.focusMapTarget(step.target.locationId);
    }
    this.callbacks.onStepChanged(step);
    this.position();
  }

  private trackTarget() {
    if (!this.tracking || this.layer.hidden) return;
    this.position();
    requestAnimationFrame(() => this.trackTarget());
  }

  private position() {
    if (this.layer.hidden) return;
    const step = this.currentStep();
    let rect: DOMRect | null = null;
    if (step?.target.type === 'element') {
      const target = document.querySelector<HTMLElement>(step.target.selector);
      if (target && !target.hidden && target.getClientRects().length) {
        rect = target.getBoundingClientRect();
        if (target !== this.targetElement) {
          this.targetElement?.classList.remove('guided-tutorial-target');
          this.targetElement = target;
          target.classList.add('guided-tutorial-target');
        }
      } else rect = document.querySelector('.meteo-card')?.getBoundingClientRect() ?? null;
    } else if (step?.target.type === 'map-location') {
      rect = this.callbacks.resolveMapTarget(step.target.locationId);
    }
    if (rect) {
      const pad = 7;
      this.spotlight.style.display = 'block';
      this.spotlight.style.left = `${Math.max(4, rect.left - pad)}px`;
      this.spotlight.style.top = `${Math.max(4, rect.top - pad)}px`;
      this.spotlight.style.width = `${Math.max(16, rect.width + pad * 2)}px`;
      this.spotlight.style.height = `${Math.max(16, rect.height + pad * 2)}px`;
      const bubbleRect = this.bubble.getBoundingClientRect();
      const belowTop = rect.bottom + 16;
      let top = belowTop + bubbleRect.height < window.innerHeight - 12
        ? belowTop : Math.max(12, rect.top - bubbleRect.height - 16);
      let left = Math.min(Math.max(12, rect.left), window.innerWidth - bubbleRect.width - 12);

      // Keep the guide clear of the workbench it is explaining. When a target is
      // inside the contextual drawer, use its free lower area instead of covering
      // the chart or the result beneath the highlighted control.
      if (step?.target.type === 'element') {
        const target = document.querySelector<HTMLElement>(step.target.selector);
        const panel = target?.closest<HTMLElement>('#context-panel');
        if (panel && !panel.hidden) {
          const panelRect = panel.getBoundingClientRect();
          const blockers = [...panel.querySelectorAll<HTMLElement>(
            '.context-heading, #station-current-readings, #weather-history-button, .lab-heading, .lab-briefing, #lab-chart-wrap, #lab-metrics, #lab-note, #forecast-controls, #lab-forecast-output, #mission-complete-summary, #scenario-actions, #reveal-trend, #show-average, #mission1-trend-action, #next-mission',
          )].filter(element => !element.hidden && getComputedStyle(element).display !== 'none')
            .map(element => element.getBoundingClientRect())
            .filter(bounds => bounds.width > 0 && bounds.height > 0);
          const panelLeft = panelRect.left + 8;
          const panelTop = panelRect.top + 8;
          const panelBottom = Math.min(panelRect.bottom, window.innerHeight) - bubbleRect.height - 8;
          let clearSpot: number | null = null;
          for (let candidate = panelBottom; candidate >= panelTop; candidate -= 8) {
            const overlaps = blockers.some(bounds => panelLeft < bounds.right && panelLeft + bubbleRect.width > bounds.left
              && candidate < bounds.bottom && candidate + bubbleRect.height > bounds.top);
            if (!overlaps) { clearSpot = candidate; break; }
          }
          if (clearSpot !== null && panelLeft + bubbleRect.width <= panelRect.right - 4) {
            left = panelLeft;
            top = clearSpot;
          }
        }
      }
      this.bubble.style.top = `${top}px`;
      this.bubble.style.left = `${left}px`;
    } else {
      this.spotlight.style.display = 'none';
      this.bubble.style.left = `${Math.max(12, window.innerWidth - 340)}px`;
      this.bubble.style.top = '118px';
    }
  }
}
