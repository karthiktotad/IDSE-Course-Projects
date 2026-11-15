/** Quiet procedural rain and synth ambience. Audio starts only after a player gesture. */
export class AmbientAudio {
  private context: AudioContext | null = null;
  private master: GainNode | null = null;
  private chimeTimer: number | null = null;
  private chimeIndex = 0;

  async start() {
    if (!this.context) this.createSoundscape();
    if (this.context!.state === 'suspended') await this.context!.resume();
    const now = this.context!.currentTime;
    this.master!.gain.cancelScheduledValues(now);
    this.master!.gain.setTargetAtTime(0.22, now, 0.8);
    if (this.chimeTimer === null) this.chimeTimer = window.setInterval(() => this.playChime(), 3200);
  }

  stop() {
    if (!this.context || !this.master) return;
    if (this.chimeTimer !== null) window.clearInterval(this.chimeTimer);
    this.chimeTimer = null;
    const now = this.context.currentTime;
    this.master.gain.cancelScheduledValues(now);
    this.master.gain.setTargetAtTime(0, now, 0.35);
  }

  private createSoundscape() {
    const context = new AudioContext();
    const master = context.createGain();
    master.gain.value = 0;
    master.connect(context.destination);
    this.context = context;
    this.master = master;

    // A slow three-note pad gives the rain a gentle, game-like musical bed.
    [130.81, 164.81, 196, 261.63].forEach((frequency, index) => {
      const oscillator = context.createOscillator();
      const tone = context.createGain();
      const filter = context.createBiquadFilter();
      oscillator.type = index === 1 ? 'sine' : 'triangle';
      oscillator.frequency.value = frequency;
      filter.type = 'lowpass';
      filter.frequency.value = 420;
      tone.gain.value = index === 3 ? 0.035 : 0.07;
      oscillator.connect(filter).connect(tone).connect(master);
      oscillator.start();
    });

    // Loop filtered noise as soft rainfall, not a loud alert effect.
    const frameCount = context.sampleRate * 3;
    const buffer = context.createBuffer(1, frameCount, context.sampleRate);
    const samples = buffer.getChannelData(0);
    for (let index = 0; index < frameCount; index += 1) samples[index] = (Math.random() * 2 - 1) * 0.35;
    const noise = context.createBufferSource();
    const rainFilter = context.createBiquadFilter();
    const rainGain = context.createGain();
    noise.buffer = buffer;
    noise.loop = true;
    rainFilter.type = 'lowpass';
    rainFilter.frequency.value = 1050;
    rainGain.gain.value = 0.12;
    noise.connect(rainFilter).connect(rainGain).connect(master);
    noise.start();
  }

  private playChime() {
    if (!this.context || !this.master || this.context.state !== 'running') return;
    const now = this.context.currentTime;
    const scale = [523.25, 659.25, 783.99, 659.25, 587.33, 783.99];
    const oscillator = this.context.createOscillator();
    const envelope = this.context.createGain();
    oscillator.type = 'sine';
    oscillator.frequency.value = scale[this.chimeIndex++ % scale.length];
    envelope.gain.setValueAtTime(0.0001, now);
    envelope.gain.exponentialRampToValueAtTime(0.045, now + 0.06);
    envelope.gain.exponentialRampToValueAtTime(0.0001, now + 1.7);
    oscillator.connect(envelope).connect(this.master);
    oscillator.start(now);
    oscillator.stop(now + 1.75);
  }
}
