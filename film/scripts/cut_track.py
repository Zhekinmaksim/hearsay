#!/usr/bin/env python3
"""Cut the 60-second soundtrack and write the beat file the film reads.

    python3 scripts/cut_track.py path/to/Unresolved_Chord.mp3

Claude cannot hear the track, so every decision below was made from the
waveform. The numbers are measured from this particular track and are kept here
as constants so the cut is reproducible; a different track needs them measured
again (the analysis that produced them is described inline).

  body tempo   92.25 BPM, found by autocorrelating spectral-flux onsets over
               20–150 s; the strongest transients (42.89, 50.67, 53.27, 55.87,
               58.47) land one bar apart, which fixes the downbeat phase.
  outro        slows to about 87.6 BPM. A continuous grid across the splice is
               therefore impossible, and the first attempt — aligning the seam
               to the body grid — put the hit 143 ms early. The outro is cut on
               its own measured pulses instead.
  splice       body 15.125–61.069 s, one-beat equal-power crossfade into the
               outro so that its first strong pulse (180.272 s) lands on the
               film's downbeat at 45.944 s. The silent tail is trimmed so the
               total is exactly 60.000 s.
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BPM = 92.25
BEAT = 60 / BPM
A0, A1 = 15.125, 61.069471821248825
B_HIT = 180.272
OUTRO_PULSES = [180.272, 181.642, 183.035, 184.446, 185.874, 187.319, 188.805]
# Body downbeats in film time, each one refined to the measured transient peak
# and corrected for the detector's 25 ms bias. Kept as measured values rather
# than regenerated from an ideal grid: the grid alone drifts up to 53 ms from
# what the film was cut to.
BODY_DOWNBEATS = [1.827, 4.428, 7.005, 9.606, 12.207, 14.807, 17.408, 19.985, 22.586, 25.187, 27.787, 30.388, 32.965, 35.566, 38.167, 40.767, 43.368]


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "Unresolved_Chord.mp3"
    xf = BEAT
    b0 = B_HIT - xf
    len_a = A1 - A0
    splice = len_a - xf
    b_end = b0 + (60.0 - splice)

    flt = (f"[0:a]atrim={A0}:{A1},asetpts=PTS-STARTPTS[a];"
           f"[0:a]atrim={b0}:{b_end},asetpts=PTS-STARTPTS[b];"
           f"[a][b]acrossfade=d={xf:.4f}:c1=qsin:c2=qsin,"
           f"afade=t=in:st=0:d=0.35,atrim=0:60,apad=whole_dur=60[out]")
    out = os.path.join(HERE, "public", "track.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-filter_complex", flt,
                    "-map", "[out]", "-ar", "48000", "-ac", "2", out], check=True)

    body = [v for v in BODY_DOWNBEATS if v < splice]
    tail = [round(splice + (p - b0), 3) for p in OUTRO_PULSES if splice + (p - b0) < 60]
    json.dump({"fps": 30, "bpm": BPM, "duration": 60.0, "downbeats": body + tail,
               "splice": round(splice, 3), "outro_pulses": tail,
               "note": "body at 92.25 BPM; the outro slows to ~87.6, so its pulses are measured onsets"},
              open(os.path.join(HERE, "src", "beats.json"), "w"), indent=1)
    print("wrote public/track.wav and src/beats.json")
    print("downbeats:", body + tail)


if __name__ == "__main__":
    main()
