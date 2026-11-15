import Phaser from 'phaser';
import { EastbankScene } from './EastbankScene';
import { advanceGame, calculateMovingAverage, calculateStatistics, fitRegression, newGame, placeResource, startFloodScenario } from './api';
import type { GameState, MapCell, Resource } from './types';
import { AmbientAudio } from './AmbientAudio';
import './style.css';

type Phase = 'signal' | 'model' | 'deploy' | 'storm' | 'report';
type RoundResult = { guessRain: number; actualRain: number; predictedDepth: number; actualDepth: number; error: number };
const app = document.querySelector<HTMLDivElement>('#app')!;
app.innerHTML = `
  <header class="topbar">
    <a class="brand"><b>-</b><span>STORMWATCH<small>EASTBANK FLOOD RESPONSE</small></span></a>
    <div class="top-stat"><span>STORM TIME</span><b id="clock">00:00</b></div>
    <div class="top-stat"><span>HOSPITAL ROAD</span><b id="access">OPEN</b></div>
    <div class="top-stat"><span>WATER PEAK</span><b id="depth">0 mm</b></div>
    <div class="top-stat"><span>RESPONSE FUND</span><b id="budget">500 CR</b></div>
    <button class="maya-help" id="maya-help" type="button" aria-haspopup="dialog">ASK MAYA</button>
    <button class="sound-toggle" id="sound" type="button" aria-pressed="false">- AUDIO OFF</button>
    <button class="restart" id="restart" type="button" title="Restart from the beginning">- NEW RUN</button>
  </header>
  <nav class="phase-nav" aria-label="Game progress">
    <button data-phase="signal"><i>01</i><span><b>READ THE RAIN</b><small>SMOOTH A NOISY SIGNAL</small></span></button>
    <button data-phase="model"><i>02</i><span><b>BUILD A MODEL</b><small>FIT & TEST A LINE</small></span></button>
    <button data-phase="deploy"><i>03</i><span><b>PREPARE THE CITY</b><small>PLACE YOUR RESOURCES</small></span></button>
    <button data-phase="storm"><i>04</i><span><b>RIDE THE STORM</b><small>MAKE SIX FORECASTS</small></span></button>
  </nav>
  <main class="game-shell">
    <section class="map-panel" aria-label="Interactive Eastbank flood map">
      <div class="map-head"><div><span class="eyebrow">LIVE SIMULATION - NOVARA COAST</span><h1>Eastbank <em>under pressure</em></h1></div><div class="map-legend"><span><i class="dot rain"></i>RAIN</span><span><i class="dot water"></i>FLOOD WATER</span><span><i class="dot help"></i>HOSPITAL</span></div></div>
      <div class="map-tools"><span id="map-instruction">Choose a weather station on the map to inspect its signal.</span><div><button id="zoom-minus" title="Zoom out">-</button><button id="zoom-plus" title="Zoom in">+</button><button id="zoom-home" title="Reset map view">-</button></div></div>
      <div id="game"><div class="map-loading">Connecting to Eastbank-</div></div>
      <div class="map-foot"><span id="map-selection">Click a weather station, road or building to inspect it.</span><span id="map-layer-label">CITY VIEW - 32 - 24 GRID</span></div>
    </section>
    <aside class="play-panel"><div id="console"></div></aside>
  </main>
  <div class="toast" id="toast" role="status" aria-live="polite"></div>
  <section class="briefing-overlay" id="briefing" role="dialog" aria-modal="true" aria-labelledby="briefing-title" aria-describedby="briefing-story">
    <div class="briefing-scene"><div class="briefing-rain"></div><div class="briefing-topline"><span>- NOVARA COASTAL EMERGENCY NETWORK</span><span>LIVE FIELD BRIEFING - EASTBANK</span><button id="briefing-skip" type="button" disabled>ENTER FIELD -</button></div>
      <article class="briefing-card">
        <div class="briefing-portrait"><div class="portrait-orbit orbit-one"></div><div class="portrait-orbit orbit-two"></div><svg viewBox="0 0 100 120" role="img" aria-label="Maya Reyes, Eastbank field lead">
          <ellipse cx="51" cy="113" rx="37" ry="7" fill="#0b211d55"/><path d="M16 112c2-25 12-36 34-37 24 0 33 13 36 37" fill="#cf754f"/><path d="M35 77l16 17 17-18 9 13-26 26-26-23z" fill="#f4eee0"/><path d="M31 36c-1-19 10-28 25-27 18 1 23 15 20 34l-5 25-41-4z" fill="#29372f"/><ellipse cx="53" cy="43" rx="22" ry="26" fill="#bd805e"/><path d="M31 39c-2-19 10-30 26-30 14 0 24 8 23 27-7-2-13-7-17-14-6 9-17 15-32 17z" fill="#303c34"/><path d="M35 49c5-2 9-2 12 0M60 49c4-2 8-1 11 1" fill="none" stroke="#44352f" stroke-width="2" stroke-linecap="round" class="briefing-eyes"/><path d="M49 62c4 3 8 3 12 0" fill="none" stroke="#78483f" stroke-width="2" stroke-linecap="round" class="briefing-mouth"/><path d="M28 41c-7 1-8 10-2 14M76 43c7 0 8 9 2 13" fill="none" stroke="#bd805e" stroke-width="4"/><path d="M28 29c-4-16 10-28 27-28 14 0 25 9 25 24-8-4-13-10-15-16-7 12-20 18-37 20z" fill="#29372f"/><path d="M15 105c4-19 12-28 24-31l12 20 12-20c13 3 22 13 25 31l-3 9H19z" fill="#d9845d"/><path d="M42 77l9 17 9-17" fill="none" stroke="#f0e9d9" stroke-width="4"/><rect x="67" y="83" width="13" height="17" rx="3" fill="#e4bc59"/><path d="M73 87v9m-4-4h8" stroke="#725631" stroke-width="2"/>
        </svg><div class="portrait-name"><b>MAYA REYES</b><span>FIELD LEAD - EASTBANK</span></div><i class="portrait-radio"></i></div>
        <aside class="maya-message"><span>MAYA TO CHIEF ENGINEER</span><p id="maya-message">Chief Engineer, I have the readings ready. Let us find the signal before the next rain band reaches the hospital road.</p></aside>
        <div class="briefing-content"><div class="briefing-alert"><i></i><span id="briefing-kicker">SIX HOURS TO LANDFALL - COMMAND CHANNEL OPEN</span></div>
          <h1 id="briefing-title">Chief Engineer, Eastbank is running out of time.</h1>
          <p class="briefing-story" id="briefing-story">A storm band is rolling in from the coast. Eastbank General sits behind the lowest road in the district-and the first rain burst is already confusing our gauges.</p>
          <div class="briefing-separator"><i></i><span>THE FIELD PLAN</span></div>
          <div class="briefing-instruction"><b id="briefing-tech-label">YOUR DATA-SCIENCE TASK</b><p id="briefing-tech">Tune a moving average to reveal the rainfall trend. Then adjust a linear-regression line, place a limited response resource, and use forecasts to guide the flood response.</p></div>
          <div class="briefing-score" id="briefing-score" hidden><div class="briefing-score-main"><b id="briefing-score-number">0</b><span>MISSION SCORE</span></div><div class="briefing-score-details" id="briefing-score-details"></div></div>
          <div class="briefing-directive"><span>WHAT TO DO NEXT</span><b id="briefing-next">Compare the measured rain with the smoothed signal. A wide window is calmer, but can hide a sudden burst.</b></div>
          <footer class="briefing-footer"><span id="briefing-loading">Preparing Eastbank-s weather record-</span><button id="briefing-continue" disabled>ENTER THE FIELD <i>-</i></button></footer>
        </div>
      </article>
      <div class="briefing-bottom"><span>STORMWATCH - LEARN BY MAKING THE CALL</span><span>SIMULATED CITY - SYNTHETIC WEATHER</span></div>
    </div>
  </section>`;
document.body.classList.add('briefing-open');
function setGameInert(inert: boolean) {
  document.querySelectorAll<HTMLElement>('.topbar,.phase-nav,.game-shell').forEach(element=>{element.inert=inert;});
}
setGameInert(true);

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
let gameState: GameState | null = null;
let scene: EastbankScene;
let sceneReady = false;
let phase: Phase = 'signal';
let stationId = 'weather-central';
let windowSize = 5;
let smoothValues: number[] = [];
let rawStats = 0;
let smoothStats = 0;
let regression: Awaited<ReturnType<typeof fitRegression>> | null = null;
let manualSlope = 0;
let manualMae: number | null = null;
let manualScoreTimer = 0;
let modelExplored = false;
let signalExplored = false;
let deploymentMade = false;
let barrierDirection: 'N'|'E'|'S'|'W' = 'N';
let selectedResource: Resource['id'] | null = null;
let busy = false;
let round = 0;
let results: RoundResult[] = [];
let toastTimer = 0;
let audio: AmbientAudio;
let briefingReturnFocus: HTMLElement | null = null;
let briefingRetry = false;
let welcomeBriefing = true;

function message(text: string) {
  const node = $('toast'); node.textContent = text; node.classList.add('visible');
  window.clearTimeout(toastTimer); toastTimer = window.setTimeout(() => node.classList.remove('visible'), 3400);
}
function fail(error: unknown) { message(error instanceof Error ? error.message : 'The Python simulation could not complete that action.'); }
function session() { if (!gameState) throw new Error('Eastbank is still loading. Try again in a moment.'); return gameState.session_id; }
function syncState(next: GameState, initial = false) {
  gameState = next;
  if (sceneReady) scene.setMapData(next, initial);
  $('clock').textContent = `${String(Math.floor(next.elapsed_minutes / 60)).padStart(2, '0')}:${String(next.elapsed_minutes % 60).padStart(2, '0')}`;
  $('access').textContent = next.simulation.hospital_access_status === 'accessible' ? 'OPEN' : 'AT RISK';
  $('access').classList.toggle('danger', next.simulation.hospital_access_status !== 'accessible');
  $('depth').textContent = `${Math.round(next.simulation.maximum_water_depth_mm)} mm`;
  $('budget').textContent = `${next.resources.budget_remaining_credits} CR`;
  document.querySelector('.map-loading')?.remove();
}

function stationRows() {
  return (gameState?.historical_observations ?? []).filter(row => row.station_id === stationId).slice().sort((a, b) => a.timestamp.localeCompare(b.timestamp));
}
function briefingCopy(target: Phase, decision: number) {
  if(target==='signal') return welcomeBriefing ? {
    kicker:'WELCOME TO EASTBANK - EMERGENCY RESPONSE HQ',
    title:'Welcome, Chief Engineer. Eastbank needs you.',
    message:'I am Maya Reyes, your field lead. I will bring you the readings, explain what they can and cannot tell us, and stay with you through every decision.',
    story:'You are the Chief Engineer for the Eastbank response team. Eastbank General sits behind a low coastal road, and a major storm is moving in. Our goal is to keep the hospital reachable and protect the people who depend on it.',
    tech:'You will investigate noisy rainfall data, tune a moving average, test a linear regression model on unseen observations, then place response resources and forecast the moving flood.',
    next:'Start at the weather station. Explore the signal, question the model, and use evidence to guide your response. The city will react to your choices.',
  } : {
    kicker:'SIX HOURS TO LANDFALL - COMMAND CHANNEL OPEN',
    title:'Chief Engineer, Eastbank is running out of time.',
    message:'Chief Engineer, I have the readings ready. Help me separate the storm signal from the noise before the next rain band reaches the hospital road.',
    story:'A storm band is rolling in from the coast. Eastbank General sits behind the lowest road in the district - and the first rain burst is already confusing our gauges. If we misread the signal, our crews will be late.',
    tech:'Tune a moving average on the real station readings. Compare the measured rain with the smoothed line, then see what a wider window hides.',
    next:'Change the window size. Choose a signal that calms the noise without erasing a sudden burst.',
  };
  if(target==='model') return {
    kicker:'RAIN BAND APPROACHING - MODEL DESK ONLINE',
    title:'The next question is how much water the rain will leave behind.',
    message:'Chief Engineer, the dispatcher says the hospital road is vulnerable. Let us learn from earlier storms, while remembering this one may still surprise the model.',
    story:'The approach road is low, and another rain band is turning inland. Earlier storms can help us estimate what rainfall leaves behind, but they cannot guarantee this storm will behave the same way.',
    tech:'Explore linear regression. Earlier observations train the line; later unseen storms test it. Adjust the slope and use Python mean absolute error to measure the residuals.',
    next:'Move the orange trial line. Watch its average miss, then compare it with the least-squares fit.',
  };
  if(target==='deploy') return {
    kicker:'PRE-LANDFALL - DISPATCH REQUEST',
    title:'We have one chance to prepare the hospital route.',
    message:'Chief Engineer, our crews are waiting for your placement call. Think about where each tool can protect people and keep the hospital reachable.',
    story:'Eastbank General is still open. The flood-control crew has brought three tools, but the emergency fund can cover only a careful plan. A pump, barrier, or rescue boat in the wrong place will not help when water reaches the road.',
    tech:'Use your rainfall analysis to make a spatial decision. Equipment has limited inventory, a real credit cost, and a placement rule enforced by the Python flood engine.',
    next:'Choose a resource and place it on a valid map tile. The storm will reveal what your decision changed.',
  };
  if(target==='storm') {
    const hour=Math.floor((gameState?.elapsed_minutes??0)/60);
    const prior=results[results.length-1];
    return {
      kicker:`LANDFALL - DECISION ${decision+1} OF 6 - HOUR ${String(hour).padStart(2,'0')}`,
      title:decision===0?'The first rain band is crossing Eastbank. Make the call.':`Four hours later, the water has moved. Decision ${decision+1} is yours.`,
      message:decision===0?'Chief Engineer, dispatch needs your best rainfall estimate now. Read the station signal, then commit when you are ready.':`Chief Engineer, our last estimate missed by ${prior?.error.toFixed(1)??'new'} mm. Learn from that miss and make the next call.`,
      story:decision===0?'Radar is lighting up over the coast. The gauges are still noisy, the hospital road is open, and dispatch needs a rainfall estimate before committing crews for the next four hours.':`The station has recorded ${prior?.actualRain.toFixed(1)??'new'} mm/h rain and your last depth estimate missed by ${prior?.error.toFixed(1)??'-'} mm. Hospital access is ${gameState?.simulation.hospital_access_status==='accessible'?'still open':'now under threat'}. The next band is arriving.`,
      tech:'Use the selected sensor-s recent readings as evidence. Set a rainfall forecast, let the fitted regression convert it to expected depth, then compare that prediction with the same sensor after four simulated hours.',
      next:'Choose a rainfall value and lock your forecast. The flood moves only after you commit.',
    };
  }
  const mean=results.length?results.reduce((sum,item)=>sum+item.error,0)/results.length:0;
  const saved=gameState?.response_outcome.hospital_access==='accessible';
  const roadCells=gameState?.cells.filter(cell=>cell.terrain_type.toLowerCase().includes('road')).length??0;
  const forecastScore=Math.max(0,100-mean*1.25);
  const hospitalScore=saved?100:0;
  const roadScore=roadCells?Math.max(0,100-(gameState?.response_outcome.flooded_road_count??roadCells)/roadCells*100):0;
  const missionScore=Math.round(forecastScore*.5+hospitalScore*.35+roadScore*.15);
  return {
    kicker:'STORM PASSED - FIELD DEBRIEF',
    title:saved?'Eastbank General is still reachable. The city held.':'The flood cut the hospital route. We know where our plan fell short.',
    message:saved?`Chief Engineer, your mission score is ${missionScore} out of 100. Your decisions kept the hospital route reachable. Let us review what worked and where the model struggled.`:`Chief Engineer, your mission score is ${missionScore} out of 100. The storm exposed a weak point in our plan. Let us study the misses and prepare a stronger response.`,
    story:`You made ${results.length} forecast decisions with an average miss of ${mean.toFixed(1)} mm. ${gameState?.response_outcome.residents_evacuated??0} residents were evacuated, and the hospital route ${saved?'stayed open':'was flooded'}.`,
    tech:'Your score combines forecast accuracy (50%), hospital access (35%), and road safety (15%). A strong model matters most when it helps protect real places and people.',
    next:'Read the field report, then run another strategy and compare what changes.',
    score:missionScore,
    scoreDetails:[['FORECAST ACCURACY',Math.round(forecastScore)],['HOSPITAL ACCESS',Math.round(hospitalScore)],['ROAD SAFETY',Math.round(roadScore)]],
  };
}
function showBriefing(target: Phase=phase, decision=round) {
  const overlay=$('briefing'), copy=briefingCopy(target,decision);
  const isWelcome=target==='signal'&&welcomeBriefing&&!briefingRetry;
  overlay.classList.toggle('welcome',isWelcome);
  overlay.classList.toggle('debrief',target==='report');
  $('briefing-kicker').textContent=copy.kicker;
  $('briefing-title').textContent=copy.title;
  $('briefing-story').textContent=copy.story;
  $('maya-message').textContent=copy.message;
  $('briefing-tech').textContent=copy.tech;
  $('briefing-tech-label').textContent=target==='report'?'HOW YOUR SCORE IS CALCULATED':'YOUR DATA-SCIENCE TASK';
  $('briefing-next').textContent=copy.next;
  const scorePanel=$('briefing-score');
  scorePanel.hidden=target!=='report';
  if(target==='report'&&'score' in copy&&'scoreDetails' in copy&&Array.isArray(copy.scoreDetails)) {
    $('briefing-score-number').textContent=String(copy.score);
    $('briefing-score-details').innerHTML=copy.scoreDetails.map(([label,value])=>`<span><b>${label}</b><em>${value}</em></span>`).join('');
  }
  const button=$('briefing-continue') as HTMLButtonElement;
  button.disabled=busy;
  ($('briefing-skip') as HTMLButtonElement).disabled=busy;
  button.innerHTML=busy?'PREPARING THE FIELD- <i>-</i>':isWelcome?'START THE MISSION <i>-</i>':target==='report'?'OPEN THE FIELD REPORT <i>-</i>':target==='signal'&&gameState?'BEGIN THE OPERATION <i>-</i>':'CONTINUE TO THE FIELD <i>-</i>';
  $('briefing-loading').textContent=busy?'Loading live station data and the Eastbank flood map-':'Maya is standing by on the field channel.';
  if(overlay.hidden) {
    briefingReturnFocus=document.activeElement instanceof HTMLElement?document.activeElement:null;
    overlay.hidden=false; document.body.classList.add('briefing-open');
    overlay.classList.remove('entering'); void overlay.offsetWidth; overlay.classList.add('entering');
  }
  setGameInert(true);
  if(!busy) button.focus();
}
function dismissBriefing() {
  if($('briefing').classList.contains('welcome')) {
    welcomeBriefing=false;
    render();
  }
  const overlay=$('briefing'); overlay.hidden=true; overlay.classList.remove('entering'); document.body.classList.remove('briefing-open'); setGameInert(false);
  briefingReturnFocus?.focus(); briefingReturnFocus=null;
}
function esc(value: string) { return value.replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]!); }
function chartFrame(title: string, subtitle: string, content: string, xLabel: string, yLabel: string) {
  return `<div class="chart-title"><div><b>${title}</b><span>${subtitle}</span></div><span class="chart-live"><i></i> PYTHON DATA</span></div>
    <div class="chart-wrap"><span class="axis-y">${yLabel}</span><svg viewBox="0 0 720 260" role="img" aria-label="${title} chart">${content}</svg><span class="axis-x">${xLabel}</span></div>`;
}
function rainfallSvg(raw: number[], smoothed: number[]) {
  const W = 720, H = 260, left = 42, right = 15, top = 14, bottom = 30;
  const max = Math.max(10, ...raw) * 1.15, x = (i: number) => left + i * (W - left - right) / Math.max(1, raw.length - 1), y = (v: number) => top + (H - top - bottom) * (1 - v / max);
  const grid = [0, .25, .5, .75, 1].map(f => { const yy = top + f * (H - top - bottom); return `<line x1="${left}" y1="${yy}" x2="${W-right}" y2="${yy}" class="gridline"/><text x="${left-8}" y="${yy+4}" text-anchor="end" class="tick">${Math.round(max*(1-f))}</text>`; }).join('');
  const rawPoints = raw.map((v, i) => `${x(i)},${y(v)}`).join(' ');
  const start = Math.max(0, windowSize - 1);
  const avgPoints = smoothed.map((v, i) => `${x(start + i)},${y(v)}`).join(' ');
  const dots = raw.map((v, i) => `<circle cx="${x(i)}" cy="${y(v)}" r="2.8" class="raw-dot"><title>Reading ${i + 1}: ${v.toFixed(1)} mm/h</title></circle>`).join('');
  return `${grid}<polyline points="${rawPoints}" class="raw-line"/>${dots}<polyline points="${avgPoints}" class="smooth-line"/>`;
}
function renderHeader() {
  for (const button of document.querySelectorAll<HTMLButtonElement>('.phase-nav button')) {
    const key = button.dataset.phase as Phase;
    button.classList.toggle('active', phase === key);
    button.classList.toggle('complete', ['signal','model','deploy'].indexOf(key) < ['signal','model','deploy','storm','report'].indexOf(phase));
    button.disabled = busy || (Boolean(gameState?.scenario_progress.started) && key !== 'storm') || (key === 'model' && (!regression || !signalExplored)) || (key === 'deploy' && !modelExplored) || (key === 'storm' && !gameState?.scenario_progress.started && phase !== 'storm');
  }
}
function bindSignal() {
  const slider = $('window-size') as HTMLInputElement;
  slider.addEventListener('input', async () => {
    signalExplored=true;
    renderHeader();
    const continueButton=document.getElementById('to-model') as HTMLButtonElement|null;
    if(continueButton) { continueButton.disabled=false; continueButton.innerHTML='USE THIS SIGNAL <span>-</span>'; }
    windowSize = Number(slider.value); $('window-value').textContent = `${windowSize} readings`;
    const rows = stationRows();
    try {
      const [avg, raw] = await Promise.all([
        calculateMovingAverage(rows.map(row => row.rainfall_mm_hr), windowSize, rows.map(row => row.timestamp), session()),
        calculateStatistics(rows.map(row => row.rainfall_mm_hr), session()),
      ]);
      const smooth = await calculateStatistics(avg.values, session());
      smoothValues = avg.values; rawStats = raw.standard_deviation; smoothStats = smooth.standard_deviation;
      renderConsole();
    } catch (error) { fail(error); }
  });
  $('station-select').addEventListener('change', async event => {
    stationId = (event.currentTarget as HTMLSelectElement).value;
    await loadSignal(); renderConsole();
  });
  $('to-model').addEventListener('click', async () => { if(!signalExplored) return; phase = 'model'; await loadModel(); render(); showBriefing('model',0); });
}
function bindModel() {
  const slider = $('slope-range') as HTMLInputElement;
  slider.addEventListener('input', () => {
    modelExplored = true;
    renderHeader();
    const continueButton=document.getElementById('to-deploy') as HTMLButtonElement|null;
    if(continueButton) continueButton.disabled=false;
    manualSlope = Number(slider.value); $('slope-readout').textContent = manualSlope.toFixed(2);
    const rows = stationRows();
    const xs = rows.map(row => row.rainfall_mm_hr), ys = rows.map(row => row.water_depth_mm);
    const intercept = regression?.intercept ?? 0;
    $('manual-error').textContent = 'Python is scoring your line-';
    $('model-graph').innerHTML = scatterSvg(xs, ys, regression?.slope ?? 0, intercept, manualSlope);
    window.clearTimeout(manualScoreTimer);
    manualScoreTimer=window.setTimeout(async()=>{
      try {
        const minX=Math.min(...xs),maxX=Math.max(...xs);
        const scored=await fitRegression(xs,ys,session(),{x:[minX,maxX],y:[manualSlope*minX+intercept,manualSlope*maxX+intercept]});
        manualMae=scored.manual_line?.mae ?? null;
        const scoreLabel=document.getElementById('manual-error');
        if(scoreLabel) scoreLabel.textContent=manualMae===null?'Could not score line':`${manualMae.toFixed(1)} mm average miss`;
      } catch(error) { const scoreLabel=document.getElementById('manual-error'); if(scoreLabel) scoreLabel.textContent='Python score unavailable'; fail(error); }
    },220);
  });
  $('to-deploy').addEventListener('click', () => { if(!modelExplored) return; phase = 'deploy'; render(); showBriefing('deploy',0); });
}
function scatterSvg(xs: number[], ys: number[], bestSlope: number, intercept: number, trialSlope: number) {
  const W=720,H=260,l=46,r=15,t=15,b=31, minX=Math.min(...xs), maxX=Math.max(...xs), minY=Math.min(0,...ys), maxY=Math.max(...ys)*1.12;
  const x=(v:number)=>l+(v-minX)/(maxX-minX||1)*(W-l-r), y=(v:number)=>t+(1-(v-minY)/(maxY-minY||1))*(H-t-b);
  const grid=[0,.25,.5,.75,1].map(f=>{const yy=t+f*(H-t-b);return `<line x1="${l}" y1="${yy}" x2="${W-r}" y2="${yy}" class="gridline"/>`;}).join('');
  const dots=xs.map((v,i)=>`<circle cx="${x(v)}" cy="${y(ys[i])}" r="${i<Math.ceil(xs.length*.8)?3:4}" class="${i<Math.ceil(xs.length*.8)?'train-dot':'test-dot'}"><title>${i<Math.ceil(xs.length*.8)?'Training':'Unseen test'} - ${v.toFixed(1)} mm/h rain, ${ys[i].toFixed(1)} mm depth</title></circle>`).join('');
  const x0=minX,x1=maxX;
  const line=(s:number,cls:string)=>`<line x1="${x(x0)}" y1="${y(s*x0+intercept)}" x2="${x(x1)}" y2="${y(s*x1+intercept)}" class="${cls}"/>`;
  return `${grid}${dots}${line(bestSlope,'best-fit')}${line(trialSlope,'trial-fit')}`;
}
function bindDeploy() {
  for (const button of document.querySelectorAll<HTMLButtonElement>('.resource-card')) button.addEventListener('click', () => {
    selectedResource = button.dataset.resource!; scene.setPlacementMode(true);
    const directionField=document.getElementById('barrier-direction-wrap');
    if(directionField) directionField.hidden=selectedResource!=='barrier';
    $('map-instruction').textContent = `Place ${button.dataset.name} on a valid tile. Click the map to deploy it.`;
    document.querySelectorAll('.resource-card').forEach(el => el.classList.toggle('chosen', el === button));
  });
  const direction=document.getElementById('barrier-direction') as HTMLSelectElement|null;
  direction?.addEventListener('change',()=>{barrierDirection=direction.value as typeof barrierDirection;});
  $('begin-storm').addEventListener('click', async () => {
    if(!deploymentMade) { message('Place at least one response resource on the map before landfall.'); return; }
    busy = true; renderHeader();
    try { syncState(await startFloodScenario(session())); phase = 'storm'; round = 0; results = []; busy=false; render(); showBriefing('storm',0); message('Storm live. Make a rainfall call before each four-hour advance.'); }
    catch (error) { fail(error); busy = false; render(); }
  });
}
function bindStorm() {
  const slider=$('rain-guess') as HTMLInputElement;
  const modelRain=Number(slider.value), estimate=(regression?.slope ?? 0)*modelRain+(regression?.intercept ?? 0);
  const update=()=>{
    const rain=Number(slider.value), depth=Math.max(0,(regression?.slope ?? 0)*rain+(regression?.intercept ?? 0));
    $('rain-guess-value').textContent=`${rain.toFixed(0)} mm/h`;
    $('depth-estimate').textContent=`${depth.toFixed(0)} mm`;
    $('forecast-marker').style.left=`${Math.min(100,Math.max(0,depth/250*100))}%`;
  };
  slider.addEventListener('input',update); update();
  $('forecast-now').addEventListener('click', async () => {
    busy=true; render();
    const rain=Number(slider.value), predictedDepth=Math.max(0,(regression?.slope ?? 0)*rain+(regression?.intercept ?? 0));
    try {
      let next=gameState!;
      for(let i=0;i<4;i++) next=await advanceGame(session(),6);
      const sensor=next.locations.find(item=>item.id===stationId);
      const sensorCell=sensor?next.cells[sensor.y*next.columns+sensor.x]:null;
      const actualDepth=sensorCell?.water_depth_mm ?? next.simulation.maximum_water_depth_mm;
      const actualRain=sensorCell?.rainfall_intensity_mm_hr ?? next.rainfall_mm_per_hour;
      results.push({guessRain:rain,actualRain,predictedDepth,actualDepth,error:Math.abs(predictedDepth-actualDepth)});
      syncState(next); round++;
      if(round>=6 || next.scenario_progress.complete) phase='report';
      busy=false; render();
      message(`Forecast miss: ${Math.abs(predictedDepth-actualDepth).toFixed(1)} mm. Compare your estimate with the simulated peak.`);
      showBriefing(phase,round);
    } catch(error) { busy=false; fail(error); render(); }
  });
}
function render() { renderHeader(); renderConsole(); }
function renderConsole() {
  const panel=$('console');
  if(phase==='signal') {
    const stations=(gameState?.locations ?? []).filter(location=>location.kind==='weather_station');
    const rows=stationRows(), raw=rows.map(row=>row.rainfall_mm_hr);
    const options=stations.map(station=>`<option value="${esc(station.id)}" ${station.id===stationId?'selected':''}>${esc(station.name)}</option>`).join('');
    panel.innerHTML=`<div class="step-tag"><i>FIELD STUDY 01</i><span>01 / 04</span></div><h2>Find the storm signal</h2><p class="lede">Rain gauges jump around. Tune the averaging window until you can see the storm-s shape without hiding its sharpest burst.</p>
      <label class="control-label" for="station-select">Choose a monitoring station</label><select class="station-select" id="station-select">${options}</select>
      <div class="range-head"><label for="window-size">Smoothing window</label><output id="window-value">${windowSize} readings</output></div><input id="window-size" class="range" type="range" min="2" max="12" value="${windowSize}" ${busy?'disabled':''}>
      ${chartFrame('RAIN GAUGE','Raw readings vs. moving average',rainfallSvg(raw,smoothValues),'OBSERVATIONS - TIME','RAINFALL - mm/h')}
      <div class="legend"><span><i class="line raw"></i>Measured rain</span><span><i class="line smooth"></i>${windowSize}-reading average</span></div>
      <div class="discovery"><span class="discovery-icon">-</span><div><b>What changed when the window grew?</b><p>Signal variation fell from ${rawStats.toFixed(1)} to ${smoothStats.toFixed(1)} mm/h. A smoother line is easier to read, but can lag behind a sudden burst.</p></div></div>
      <div class="learning-note"><b>DATA SCIENCE - MOVING AVERAGE</b><span>Each point averages the latest ${windowSize} readings. You chose the trade-off between noise and detail.</span></div>
      <button id="to-model" class="primary" ${busy||!signalExplored?'disabled':''}>${signalExplored?'USE THIS SIGNAL':'CHANGE THE WINDOW TO EXPERIMENT'} <span>-</span></button>`;
    bindSignal();
  } else if(phase==='model') {
    const rows=stationRows(), xs=rows.map(row=>row.rainfall_mm_hr), ys=rows.map(row=>row.water_depth_mm);
    const slope=regression?.slope ?? 0, intercept=regression?.intercept ?? 0;
    const range=Math.max(.1,Math.abs(slope)*1.8), min=slope-range, max=slope+range;
    if(manualSlope===0) manualSlope=slope;
    panel.innerHTML=`<div class="step-tag"><i>FIELD STUDY 02</i><span>02 / 04</span></div><h2>Teach a line to predict</h2><p class="lede">Use past storms to connect rainfall with water depth. Orange points are held out: the model must predict them without seeing their depths.</p>
      ${chartFrame('RAINFALL - WATER DEPTH','Earlier storms train the model - later storms test it',`<g id="model-graph">${scatterSvg(xs,ys,slope,intercept,manualSlope)}</g>`,'RAINFALL - mm/h','WATER DEPTH - mm')}
      <div class="legend"><span><i class="dot train"></i>Training data</span><span><i class="dot test"></i>Unseen test data</span><span><i class="line best"></i>Python best fit</span><span><i class="line trial"></i>Your line</span></div>
      <div class="range-head"><label for="slope-range">Adjust your line-s slope</label><output id="slope-readout">${manualSlope.toFixed(2)}</output></div><input id="slope-range" class="range" type="range" min="${min}" max="${max}" step="${Math.max(.01,(max-min)/200)}" value="${manualSlope}">
      <div class="score-row"><div><small>PYTHON BEST-FIT SLOPE</small><b>${slope.toFixed(2)}</b></div><div><small>YOUR LINE - TRAINING MISS</small><b id="manual-error">${manualMae===null?'Move the slope slider':`${manualMae.toFixed(1)} mm average miss`}</b></div></div>
      <div class="learning-note"><b>DATA SCIENCE - REGRESSION & GENERALIZATION</b><span>The best-fit line minimizes squared errors on training data. The unseen points reveal whether that pattern travels to a new storm.</span></div>
      <button id="to-deploy" class="primary" ${modelExplored?'':'disabled'}>${modelExplored?'PUT THE MODEL TO WORK':'MOVE THE SLOPE TO TEST IT'} <span>-</span></button>`;
    bindModel();
  } else if(phase==='deploy') {
    const resources=gameState?.resources;
    const defs=[['pump','-','Pump','Draw water away from low ground.',40,resources?.inventory.pumps ?? 0],['barrier','-','Barrier','Block a narrow path into the hospital road.',25,resources?.inventory.barriers ?? 0],['rescue-boat','-','Rescue boat','Reach homes if roads become impassable.',35,resources?.inventory.rescue_boats ?? 0]] as const;
    const deployed=(resources?.pumps.length ?? 0)+(resources?.barriers.length ?? 0)+(resources?.rescue_boats.length ?? 0);
    panel.innerHTML=`<div class="step-tag"><i>FIELD STUDY 03</i><span>03 / 04</span></div><h2>Prepare the hospital route</h2><p class="lede">Your forecast is only useful if the city is ready. Select a tool, then place it on the map where you think it will help most. You have ${resources?.budget_remaining_credits ?? 0} credits.</p>
      <div class="resource-list">${defs.map(([id,icon,name,desc,cost,count])=>`<button class="resource-card ${selectedResource===id?'chosen':''}" data-resource="${id}" data-name="${name}" ${count<1||cost>(resources?.budget_remaining_credits??0)?'disabled':''}><i>${icon}</i><span><b>${name}</b><small>${desc}</small></span><em>${cost} CR - ${count} left</em></button>`).join('')}</div>
      <label class="barrier-direction" id="barrier-direction-wrap" ${selectedResource==='barrier'?'':'hidden'}>Barrier edge direction<select id="barrier-direction"><option value="N">North edge</option><option value="E">East edge</option><option value="S">South edge</option><option value="W">West edge</option></select></label>
      <div class="placement-status ${selectedResource?'armed':''}">${selectedResource?'MAP PLACEMENT ARMED - CLICK A CLEAR CITY TILE':'SELECT A RESPONSE TOOL TO BEGIN'}</div>
      <div class="deployment-summary"><span>DEPLOYED</span><b>${deployed} assets</b><span>HOSPITAL ACCESS</span><b>${gameState?.simulation.hospital_access_status ?? 'unknown'}</b></div>
      <div class="learning-note"><b>DECISION SCIENCE - LIMITED RESOURCES</b><span>Placement has a cost and a location. Protecting one route can leave another exposed-watch the map while choosing.</span></div>
      <button id="begin-storm" class="primary danger-button" ${busy||!deploymentMade?'disabled':''}>${deploymentMade?'START THE 24-HOUR STORM':'PLACE AN ASSET TO PREPARE'} <span>-</span></button>`;
    bindDeploy();
  } else if(phase==='storm') {
    const rows=stationRows();
    const recent=rows.slice(-windowSize).map(row=>row.rainfall_mm_hr);
    const expected=recent.reduce((sum,value)=>sum+value,0)/Math.max(1,recent.length);
    const meanError=results.length?results.reduce((s,r)=>s+r.error,0)/results.length:0;
    panel.innerHTML=`<div class="storm-banner"><span><i></i>LANDFALL - DECISION ${round+1} OF 6</span><b>+${Math.max(0,4-Math.floor((gameState?.elapsed_minutes ?? 0)/360))} HOURS</b></div>
      <h2>Call the next rainfall</h2><p class="lede">Use the station trend to estimate the next stretch of rain. Your regression line turns that estimate into a predicted water depth.</p>
      <div class="recent-signal"><span>RECENT GAUGE SIGNAL</span><b>${expected.toFixed(1)} <small>mm/h</small></b><div>${recent.map(v=>`<i style="height:${Math.max(8,v/120*100)}%" title="${v.toFixed(1)} mm/h"></i>`).join('')}</div></div>
      <div class="range-head"><label for="rain-guess">Your rainfall forecast</label><output id="rain-guess-value">${expected.toFixed(0)} mm/h</output></div><input id="rain-guess" class="range" type="range" min="0" max="120" value="${Math.round(expected)}">
      <div class="prediction-card"><span>MODEL PREDICTS DEPTH AT ${esc(gameState?.locations.find(item=>item.id===stationId)?.name ?? 'STATION')}</span><b id="depth-estimate">-</b><div class="depth-scale"><i id="forecast-marker"></i><span>DRY</span><span>DEEP WATER</span></div></div>
      ${results.length?`<div class="last-result"><span>LAST FORECAST MISS</span><b>${results[results.length-1].error.toFixed(1)} mm</b><small>Average miss so far ${meanError.toFixed(1)} mm</small></div>`:''}
      <div class="learning-note"><b>DATA SCIENCE - PREDICTION ERROR</b><span>After you commit, the flood engine advances four hours. We compare your estimate with the same station-s simulated depth-the gap is a residual.</span></div>
      <button id="forecast-now" class="primary forecast-commit" ${busy?'disabled':''}>${busy?'ADVANCING THE FLOOD-':'LOCK FORECAST & ADVANCE 4 HOURS'} <span>-</span></button>
      <div class="round-progress">${Array.from({length:6},(_,i)=>`<i class="${i<round?'done':i===round?'current':''}"></i>`).join('')}</div>`;
    bindStorm();
  } else {
    const average=results.length?results.reduce((s,r)=>s+r.error,0)/results.length:0;
    const best=results.reduce((a,b)=>b.error<a.error?b:a,results[0] ?? {guessRain:0,actualRain:0,predictedDepth:0,actualDepth:0,error:0});
    panel.innerHTML=`<div class="step-tag"><i>FIELD REPORT</i><span>MISSION COMPLETE</span></div><div class="report-emblem">-</div><h2>${gameState?.scenario_progress.complete?'The storm has passed':'Eastbank report'}</h2><p class="lede">Your predictions drove every four-hour decision. Here is what the city and your model learned together.</p>
      <div class="report-score"><span>AVERAGE FORECAST ERROR</span><b>${average.toFixed(1)} <small>mm</small></b><div class="error-bars">${results.map((r,i)=>`<i title="Decision ${i+1}: ${r.error.toFixed(1)} mm" style="height:${Math.max(8,Math.min(100,r.error/Math.max(1,...results.map(x=>x.error))*100))}%"></i>`).join('')}</div></div>
      <div class="report-grid"><div><small>HOSPITAL ROUTE</small><b>${gameState?.response_outcome.hospital_access==='accessible'?'STAYED OPEN':'WAS FLOODED'}</b></div><div><small>WATER AT PEAK</small><b>${gameState?.response_outcome.remaining_water_depth_mm.toFixed(0)} mm</b></div><div><small>ROADS FLOODED</small><b>${gameState?.response_outcome.flooded_road_count}</b></div><div><small>RESIDENTS EVACUATED</small><b>${gameState?.response_outcome.residents_evacuated}</b></div></div>
      <div class="discovery"><span class="discovery-icon">-</span><div><b>Best call: ${best.guessRain.toFixed(0)} mm/h</b><p>Its predicted depth was ${best.error.toFixed(1)} mm from the simulation. Forecast quality is measured by the size of the residual, not whether a line looks convincing.</p></div></div>
      <div class="learning-note"><b>WHAT YOU DISCOVERED</b><span>Averaging reveals trends, regression turns patterns into estimates, and the flood simulation tests those estimates against consequences.</span></div>
      <button id="play-again" class="primary">RUN IT AGAIN <span>-</span></button>`;
    $('play-again').addEventListener('click',()=>void startGame());
  }
}
async function loadSignal() {
  if(!gameState) return;
  const rows=stationRows(), rain=rows.map(row=>row.rainfall_mm_hr);
  if(rows.length<windowSize) { windowSize=Math.max(2,Math.min(12,rows.length)); }
  const [avg, raw]=await Promise.all([
    calculateMovingAverage(rain,windowSize,rows.map(row=>row.timestamp),session()),
    calculateStatistics(rain,session()),
  ]);
  const smooth=await calculateStatistics(avg.values,session());
  smoothValues=avg.values; rawStats=raw.standard_deviation; smoothStats=smooth.standard_deviation;
}
async function loadModel() {
  if(!gameState) return;
  const rows=stationRows(); regression=await fitRegression(rows.map(row=>row.rainfall_mm_hr),rows.map(row=>row.water_depth_mm),session());
  manualSlope=regression.slope; manualMae=null;
}
async function startGame() {
  busy=true; phase='signal'; round=0; results=[]; windowSize=5; selectedResource=null; regression=null; manualMae=null; modelExplored=false; signalExplored=false; deploymentMade=false; window.clearTimeout(manualScoreTimer); renderHeader();
  welcomeBriefing=true;
  briefingRetry=false; showBriefing('signal',0);
  $('console').innerHTML='<div class="step-tag"><i>FIELD STUDY 01</i><span>PREPARING EASTBANK</span></div><h2>Opening the field station-</h2><p class="lede">Python is preparing the weather record and flood map. This usually takes a moment.</p><div class="loading-track"><i></i></div>';
  $('map-instruction').textContent='Loading city grid and monitoring stations-';
  try {
    const next=await newGame(2406); syncState(next,true);
    stationId=next.locations.find(item=>item.kind==='weather_station')?.id ?? 'weather-central';
    await loadSignal(); await loadModel();
    busy=false; render(); showBriefing('signal',0);
  } catch(error) {
    busy=false; fail(error);
    $('console').innerHTML=`<div class="step-tag"><i>CONNECTION ISSUE</i></div><h2>Eastbank did not load</h2><p class="lede">${esc(error instanceof Error?error.message:'The Python simulation could not load.')}</p><button id="retry-game" class="primary">TRY AGAIN <span>-</span></button>`;
    briefingRetry=true;
    $('briefing-kicker').textContent='FIELD CHANNEL - CONNECTION LOST';
    $('briefing-title').textContent='We cannot reach the Eastbank field station.';
    $('briefing-story').textContent=error instanceof Error?error.message:'The Python flood simulation is unavailable.';
    $('briefing-tech').textContent='This operation needs the local Python service to load real station readings and calculate the flood.';
    $('briefing-next').textContent='Check that the backend is running, then try the connection again.';
    ($('briefing-continue') as HTMLButtonElement).disabled=false; $('briefing-continue').innerHTML='RETRY CONNECTION <i>-</i>';
    ($('briefing-skip') as HTMLButtonElement).disabled=false; $('briefing-skip').textContent='RETRY CONNECTION -';
    $('briefing-loading').textContent='The operation is paused until the field service responds.';
  }
}
async function onMapCell(cell: MapCell) {
  if(phase==='deploy' && selectedResource) {
    busy=true; renderHeader();
    try {
      const next=await placeResource(session(),{resource_type:selectedResource as 'pump'|'barrier'|'rescue-boat',x:cell.x,y:cell.y,...(selectedResource==='barrier'?{direction:barrierDirection}:{})});
      selectedResource=null; deploymentMade=true; scene.setPlacementMode(false); syncState(next); busy=false; render();
      $('map-instruction').textContent='Good placement. You can place another asset or start the storm.';
      message('Resource deployed. Its impact will be calculated by the flood simulation.');
    } catch(error) { busy=false; scene.setPlacementMode(false); selectedResource=null; render(); fail(error); }
    return;
  }
  const station=gameState?.locations.find(item=>item.kind==='weather_station' && cell.x>=item.x && cell.x<item.x+item.width && cell.y>=item.y && cell.y<item.y+item.height);
  if(station) {
    stationId=station.id;
    if(phase==='signal') { try { await loadSignal(); renderConsole(); } catch(error) { fail(error); } }
    $('map-selection').textContent=`${station.name} selected - its readings are shown in the field console.`;
  } else {
    $('map-selection').textContent=`Grid ${cell.x}, ${cell.y} - ${cell.terrain_type} - ${cell.elevation_mm.toFixed(0)} m elevation - current depth ${cell.water_depth_mm.toFixed(1)} mm`;
  }
}

const callbacks={
  onCellSelected:onMapCell,
  onCellHovered:(cell:MapCell|null)=>{if(cell && phase==='deploy'&&selectedResource) $('map-instruction').textContent=`${cell.terrain_type.toUpperCase()} - click to place ${selectedResource}`;},
  onPlacementTarget:onMapCell,
  onPlacementHover:(cell:MapCell|null)=>{
    if(!cell||!selectedResource||phase!=='deploy'){scene.setPlacementPreview(null);return;}
    const resourceId=selectedResource as 'pump'|'barrier'|'rescue-boat';
    const valid=resourceId==='pump'
      ? !cell.building_id&&['grass','park','road'].includes(cell.terrain_type)&&cell.can_water_flow
      : resourceId==='rescue-boat'
        ? ['river','canal','road'].includes(cell.terrain_type)
        : !cell.building_id&&(barrierDirection==='N'?cell.y>0:barrierDirection==='S'?cell.y<gameState!.rows-1:barrierDirection==='W'?cell.x>0:cell.x<gameState!.columns-1);
    scene.setPlacementPreview({cell,valid,resourceId,direction:barrierDirection});
  },
};
scene=new EastbankScene(callbacks);
scene.setReadyCallback(()=>{sceneReady=true;if(gameState) scene.setMapData(gameState,true);});
const phaser=new Phaser.Game({type:Phaser.AUTO,parent:'game',backgroundColor:'#a8c3ac',scale:{mode:Phaser.Scale.ENVELOP,width:1024,height:768,autoCenter:Phaser.Scale.CENTER_BOTH},scene:[scene],render:{antialias:false,pixelArt:true}});
document.querySelector('#zoom-minus')!.addEventListener('click',()=>scene.zoomBy(-.25));
document.querySelector('#zoom-plus')!.addEventListener('click',()=>scene.zoomBy(.25));
document.querySelector('#zoom-home')!.addEventListener('click',()=>scene.resetCamera());
document.querySelector('#restart')!.addEventListener('click',()=>void startGame());
$('briefing-continue').addEventListener('click',()=>{
  if(busy) return;
  if(briefingRetry) { void startGame(); return; }
  dismissBriefing();
});
$('briefing-skip').addEventListener('click',()=>{if(!busy&&!briefingRetry) dismissBriefing();else if(briefingRetry) void startGame();});
$('maya-help').addEventListener('click',()=>{if(!busy) showBriefing(phase,round);});
document.querySelectorAll<HTMLButtonElement>('.phase-nav button').forEach(button=>button.addEventListener('click',()=>{
  const target=button.dataset.phase;
  if(target==='signal'&&gameState) phase='signal';
  if(target==='model'&&regression) phase='model';
  if(target==='deploy'&&regression&&!gameState?.scenario_progress.started) phase='deploy';
  render(); showBriefing(phase,round);
}));
audio=new AmbientAudio();
$('sound').addEventListener('click',async()=>{
  const button=$('sound'),enabled=button.getAttribute('aria-pressed')!=='true';
  if(enabled) { try { await audio.start(); } catch { message('Audio could not start in this browser.'); return; } }
  else audio.stop();
  button.setAttribute('aria-pressed',String(enabled)); button.textContent=enabled?'- AUDIO ON':'- AUDIO OFF';
});
void startGame();
