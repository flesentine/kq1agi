import { CertificationHost, CertificationLayout } from './certification-host.mjs';

const { VAR, DIGEST } = CertificationLayout;

function isIdle(lane) {
  return Atomics.load(lane.vars, VAR.IN_TICK) === 0;
}

function cloneArrayBuffer(buffer) {
  if (!(buffer instanceof ArrayBuffer)) throw new TypeError('encodedGameFileBuffer must be an ArrayBuffer');
  return buffer.slice(0);
}

function waitTurn() {
  return new Promise(resolve => setTimeout(resolve, 0));
}

/**
 * Phase -1D replay host. Phase -1B remains frozen: this subclass adds only the
 * recorded random stream, recorded sound-end timing, recorded transport provenance,
 * and recorded logical cycle-release schedule needed to reproduce a normal PLAY session.
 */
export class ReplayCertificationHost extends CertificationHost {
  constructor(options = {}) {
    const randomReplaySpec = String(options.randomReplaySpec ?? '');
    const recordedExternalTiming = options.recordedExternalTiming !== false;
    super({
      ...options,
      checkpointContext: {
        ...(options.checkpointContext ?? {}),
        randomReplaySpec,
        recordedExternalTiming,
      },
    });
    this.randomReplaySpec = randomReplaySpec;
    this.recordedExternalTiming = recordedExternalTiming;
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
    await this._bindCheckpointGameIdentity(encodedGameFileBuffer);
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
          certificationCheckpointSAB: lane.certificationCheckpointSAB,
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

  getReplayRandomDrawCounts() {
    return {
      truth: Atomics.load(this.truth.digest, DIGEST.RANDOM_DRAWS) >>> 0,
      edited: Atomics.load(this.edited.digest, DIGEST.RANDOM_DRAWS) >>> 0,
    };
  }

  /**
   * Put the two certification lanes at the transport phase recorded by normal PLAY
   * before an idle-phase transport write is replayed. Busy-phase writes use the
   * synchronous afterClockAdvance hook in pulse(), before either worker gets an
   * event-loop turn after that logical pulse.
   *
   * An idle transport write stamped at logical tick T proves normal PLAY's worker
   * completed at T. Replay may take longer in wall-clock time, so this helper waits
   * at the same logical tick rather than converting CPU speed into simulated time.
   */
  async prepareTransportPhase(phase, options = {}) {
    if (!this.started || !this.truth.ready || !this.edited.ready) {
      throw new Error('ReplayCertificationHost is not ready.');
    }
    const expected = phase === 'busy' ? 'busy' : 'idle';
    const truthIdle = isIdle(this.truth);
    const editedIdle = isIdle(this.edited);

    if (expected === 'busy') {
      if (!truthIdle && !editedIdle) {
        return {
          status: 'BUSY', tick: this.logicalTick, cycle: this.cycle,
          truthIdle: false, editedIdle: false, transportPhase: 'busy',
        };
      }
      return {
        status: 'REPLAY_TIMING_MISS',
        reason: 'transport-phase',
        expectedPhase: 'busy',
        tick: this.logicalTick,
        cycle: this.cycle,
        truthIdle,
        editedIdle,
      };
    }

    if (truthIdle && editedIdle && this.cycle <= this.comparedCycle) {
      return {
        status: 'IDLE', tick: this.logicalTick, cycle: this.cycle,
        truthIdle: true, editedIdle: true, transportPhase: 'idle',
      };
    }
    const maxWaitMs = options.maxWaitMs ?? this.barrierTimeoutMs;
    return this.settleCurrentCycle('transport-idle', maxWaitMs);
  }

  /**
   * Finish an in-flight interpreter cycle without advancing logical time. This is
   * used both for recorded idle-phase transport writes and for the final recording
   * boundary. REPLAY MATCH is not authoritative until every released cycle in the
   * frozen window reaches the same common-barrier comparison used by Phase -1B.
   */
  async settleCurrentCycle(reason = 'final-cycle', maxWaitMs = this.barrierTimeoutMs) {
    if (!this.started || !this.truth.ready || !this.edited.ready) {
      throw new Error('ReplayCertificationHost is not ready.');
    }

    const quitBefore = await this._resolveQuitIfObserved();
    if (quitBefore) return quitBefore;

    const waitBudget = Number.isFinite(Number(maxWaitMs))
      ? Math.max(0, Number(maxWaitMs)) : this.barrierTimeoutMs;
    const startedAt = Date.now();
    while (!isIdle(this.truth) || !isIdle(this.edited)) {
      if ((Date.now() - startedAt) >= waitBudget) {
        return {
          status: 'REPLAY_TIMING_MISS',
          reason: `${reason}-timeout`,
          tick: this.logicalTick,
          cycle: this.cycle,
          maxWaitMs: waitBudget,
          truthIdle: isIdle(this.truth),
          editedIdle: isIdle(this.edited),
        };
      }
      await waitTurn();
      const quit = await this._resolveQuitIfObserved();
      if (quit) return quit;
    }

    if (this.cycle > this.comparedCycle) {
      const snapshotEpoch = await this._synchronizeBarrierSnapshot();
      const result = this.compare(snapshotEpoch);
      this.comparedCycle = this.cycle;
      return { ...result, replaySettled: true, settleReason: reason };
    }

    return {
      status: 'IDLE',
      tick: this.logicalTick,
      cycle: this.cycle,
      truthIdle: true,
      editedIdle: true,
      replaySettled: true,
      settleReason: reason,
    };
  }

  /**
   * Consume one recorded logical pulse. allowCycleRelease is the release decision
   * observed in normal PLAY for this exact total-tick value. afterClockAdvance is
   * a synchronous Phase -1D injection point: it runs after the clock/release writes
   * but before yielding to either worker, so busy-phase transport reaches both
   * aligned lanes at the same deterministic boundary.
   */
  async pulse(options = {}) {
    if (!this.started || !this.truth.ready || !this.edited.ready) throw new Error('ReplayCertificationHost is not ready.');
    const allowCycleRelease = options.allowCycleRelease !== false;
    const afterClockAdvance = typeof options.afterClockAdvance === 'function' ? options.afterClockAdvance : null;
    const quitBefore = await this._resolveQuitIfObserved();
    if (quitBefore) return quitBefore;
    const bothIdleBefore = isIdle(this.truth) && isIdle(this.edited);
    const quitAtBarrier = await this._resolveQuitIfObserved();
    if (quitAtBarrier) return quitAtBarrier;

    // Recorded replay owns the logical release schedule. If a cycle finishes earlier
    // on this machine than it did during normal PLAY, do not publish a barrier merely
    // because wall-clock execution was faster. Defer comparison until a recorded
    // release, an idle-phase event, or the final frozen boundary. The defensive
    // barrier-only path remains only for callers requesting a release without first
    // settling an already-completed prior cycle.
    if (allowCycleRelease && bothIdleBefore && this.cycle > this.comparedCycle) {
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

    if (afterClockAdvance) {
      const injected = afterClockAdvance({
        tick: this.logicalTick,
        cycle: this.cycle,
        truthIdle: isIdle(this.truth),
        editedIdle: isIdle(this.edited),
        releasedCycle,
      });
      if (injected?.status) {
        return { ...injected, releaseRequested: allowCycleRelease, releasedCycle };
      }
    }

    await waitTurn();
    const quitAfter = await this._resolveQuitIfObserved();
    if (quitAfter) return { ...quitAfter, releaseRequested: allowCycleRelease, releasedCycle };
    const truthIdle = isIdle(this.truth);
    const editedIdle = isIdle(this.edited);

    if (!truthIdle || !editedIdle) {
      return {
        status: 'BUSY', tick: this.logicalTick, cycle: this.cycle,
        truthIdle, editedIdle, releaseRequested: allowCycleRelease, releasedCycle,
      };
    }

    // A cycle completing quickly is not itself a recorded semantic barrier. Leave it
    // idle and un-compared until the replay driver reaches the next recorded boundary.
    return {
      status: 'IDLE', tick: this.logicalTick, cycle: this.cycle,
      truthIdle: true, editedIdle: true, releaseRequested: allowCycleRelease,
      releasedCycle, comparisonDeferred: this.cycle > this.comparedCycle,
    };
  }
}

export const ReplayCertificationLayout = Object.freeze({ VAR, DIGEST });
