import { CertificationHost, CertificationLayout } from './certification-host.mjs';

const { VAR, DIGEST } = CertificationLayout;

function isIdle(lane) {
  return Atomics.load(lane.vars, VAR.IN_TICK) === 0;
}

function cloneArrayBuffer(buffer) {
  if (!(buffer instanceof ArrayBuffer)) throw new TypeError('encodedGameFileBuffer must be an ArrayBuffer');
  return buffer.slice(0);
}

/**
 * Phase -1D replay host. Phase -1B remains frozen: this subclass adds only the
 * recorded random stream, recorded sound-end timing, and recorded cycle-release
 * schedule needed to reproduce a normal PLAY session.
 */
export class ReplayCertificationHost extends CertificationHost {
  constructor(options = {}) {
    super(options);
    this.randomReplaySpec = String(options.randomReplaySpec ?? '');
    this.recordedExternalTiming = options.recordedExternalTiming !== false;
  }

  _pairSoundRequests() {
    while (this.truth.soundRequests.length && this.edited.soundRequests.length && !this.pendingExternalDivergence) {
      const truth = this.truth.soundRequests.shift();
      const edited = this.edited.soundRequests.shift();
      const same = truth.type === edited.type
        && truth.endFlag === edited.endFlag
        && truth.durationTicks === edited.durationTicks
        && truth.wavHash === edited.wavHash;
      if (!same) {
        this.pendingExternalDivergence = { type: 'sound-event', truth, edited };
        return;
      }
      // Phase -1D replays the sound completion flag at the exact logical tick
      // captured from normal PLAY. Do not approximate it from WAV duration here.
      this.pendingSoundCompletions.length = 0;
      if (!this.recordedExternalTiming && truth.type === 'play') {
        this.pendingSoundCompletions.push({
          dueTick: this.logicalTick + Math.max(1, truth.durationTicks),
          endFlag: truth.endFlag,
        });
      }
    }
  }

  async start(encodedGameFileBuffer) {
    if (this.started) throw new Error('ReplayCertificationHost.start() may only be called once.');
    this.started = true;
    const truthGame = cloneArrayBuffer(encodedGameFileBuffer);
    const editedGame = cloneArrayBuffer(encodedGameFileBuffer);
    for (const lane of [this.truth, this.edited]) {
      lane.worker.postMessage({
        name: 'Initialise',
        object: {
          keyPressQueueSAB: lane.keyPressQueueSAB,
          keysSAB: lane.keysSAB,
          oldKeysSAB: lane.oldKeysSAB,
          variableSAB: lane.variableSAB,
          pixelDataSAB: lane.pixelDataSAB,
          diagnosticTraceSAB: lane.diagnosticTraceSAB,
          certificationDigestSAB: lane.certificationDigestSAB,
          certificationMode: true,
          certificationSeed: this.seed,
          certificationRandomReplay: this.randomReplaySpec,
        },
      });
    }
    this.truth.worker.postMessage({ name: 'Start', buffer: truthGame }, [truthGame]);
    this.edited.worker.postMessage({ name: 'Start', buffer: editedGame }, [editedGame]);
    await this._waitReady();
  }

  injectSoundCompletion(endFlag) {
    const flag = Number(endFlag) & 0xff;
    for (const lane of [this.truth, this.edited]) {
      Atomics.store(lane.vars, VAR.FLAGS_OFFSET + flag, 1);
    }
  }

  /**
   * Consume one recorded logical pulse. allowCycleRelease is the release decision
   * observed in normal PLAY for this exact total-tick value.
   */
  async pulse(options = {}) {
    if (!this.started || !this.truth.ready || !this.edited.ready) throw new Error('ReplayCertificationHost is not ready.');
    const allowCycleRelease = options.allowCycleRelease !== false;
    const quitBefore = await this._resolveQuitIfObserved();
    if (quitBefore) return quitBefore;
    const bothIdleBefore = isIdle(this.truth) && isIdle(this.edited);
    const quitAtBarrier = await this._resolveQuitIfObserved();
    if (quitAtBarrier) return quitAtBarrier;

    // Preserve Phase -1B's no-skipped-barrier rule. This comparison consumes no
    // recorded logical pulse; the replay driver will retry the same schedule tick.
    if (bothIdleBefore && this.cycle > this.comparedCycle) {
      const snapshotEpoch = await this._synchronizeBarrierSnapshot();
      const result = this.compare(snapshotEpoch);
      this.comparedCycle = this.cycle;
      return { ...result, replayBarrierOnly: true };
    }

    const nextTick = this.logicalTick + 1;
    if (!this.recordedExternalTiming) this._applyExternalEvents(nextTick);
    this._advanceLogicalClock(this.truth);
    this._advanceLogicalClock(this.edited);
    this.logicalTick = nextTick;

    let releasedCycle = false;
    if (bothIdleBefore && allowCycleRelease) {
      Atomics.store(this.truth.vars, VAR.IN_TICK, 1);
      Atomics.store(this.edited.vars, VAR.IN_TICK, 1);
      this.cycle += 1;
      releasedCycle = true;
    }

    await new Promise(resolve => setTimeout(resolve, 0));
    const quitAfter = await this._resolveQuitIfObserved();
    if (quitAfter) return { ...quitAfter, releaseRequested: allowCycleRelease, releasedCycle };
    const truthIdle = isIdle(this.truth);
    const editedIdle = isIdle(this.edited);

    if (!releasedCycle && bothIdleBefore) {
      return {
        status: 'IDLE', tick: this.logicalTick, cycle: this.cycle,
        truthIdle, editedIdle, releaseRequested: allowCycleRelease, releasedCycle,
      };
    }

    if (!truthIdle || !editedIdle) {
      return {
        status: 'BUSY', tick: this.logicalTick, cycle: this.cycle,
        truthIdle, editedIdle, releaseRequested: allowCycleRelease, releasedCycle,
      };
    }

    const snapshotEpoch = await this._synchronizeBarrierSnapshot();
    const result = this.compare(snapshotEpoch);
    this.comparedCycle = this.cycle;
    return { ...result, releaseRequested: allowCycleRelease, releasedCycle };
  }
}

export const ReplayCertificationLayout = Object.freeze({ VAR, DIGEST });
