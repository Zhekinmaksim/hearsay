import { Easing, interpolate } from "remotion";
import beats from "./beats.json";

/* Every cut in the film reads its time from beats.json, which was measured off
 * the track: onset strength, a 92.25 BPM grid for the body, and the measured
 * pulses of the outro, which slows to about 87.6. Nothing below is placed by
 * eye, so picture and music move on the same numbers. */
export const FPS = 30;
export const BEAT = 60 / beats.bpm;
export const D: number[] = beats.downbeats;

// Body downbeats d0..d16, then the outro pulses o0..o6.
export const d = (i: number) => D[i];
export const o = (i: number) => D[17 + i];
export const beat = (bar: number, k: number) => D[bar] + k * BEAT;

export const ease = Easing.bezier(0.2, 0.7, 0.2, 1);

/** 0→1 over `dur` seconds starting at `at`. */
export const prog = (t: number, at: number, dur = 0.32) =>
  interpolate(t, [at, at + dur], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });

/** Enter: fade and rise. Motion only where something changes. */
export const enter = (t: number, at: number, dur = 0.32, rise = 18) => {
  const p = prog(t, at, dur);
  return { opacity: p, transform: `translateY(${(1 - p) * rise}px)` };
};

/** A hard stamp: arrives slightly large and settles, on the hit. */
export const stamp = (t: number, at: number) => {
  const p = prog(t, at, 0.22);
  return {
    opacity: p > 0 ? 1 : 0,
    transform: `scale(${1 + (1 - p) * 0.06})`,
    transformOrigin: "left center",
  };
};

export const between = (t: number, a: number, b: number) => t >= a && t < b;
