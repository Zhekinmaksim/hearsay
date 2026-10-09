import React from "react";
import { AbsoluteFill, Audio, staticFile, useCurrentFrame } from "remotion";
// @ts-ignore — the page's own module, imported unchanged
import { cascade } from "./lib.mjs";
import corpus from "./corpus.json";
import checkpoint from "./checkpoint.json";
import { DARK, LIGHT, MONO, SANS, SERIF, Theme, loadFonts } from "./tokens";
import { BEAT, FPS, beat, between, d, enter, o, prog, stamp } from "./time";

loadFonts();

const W = 1920;
const LEFT = 150;

type Row = (typeof corpus.entries)[number];
const byId = new Map<number, Row>(corpus.entries.map((e) => [e.entry_id, e]));
const injection = corpus.entries.find((e) => e.entry_class === "direct_injection")!;
const split = corpus.entries.find((e) => e.votes.b === "unread")!;
const honest = corpus.report.honest_attempts;
const honestRefused = honest - corpus.report.honest_admitted;
const judged = corpus.entries.length;

/* The cascade on screen is computed, not choreographed: the same function the
 * page runs, over the same corpus, revoking the same root. */
const ROOT = 0;
const walk = cascade(corpus.entries, ROOT, corpus.policy.cascade_depth) as {
  steps: Array<{ id: number; depth: number | null; became: string; rejudged?: boolean }>;
};

// ------------------------------------------------------------------- theme

const themeAt = (t: number): Theme => (between(t, d(10), d(14)) ? DARK : LIGHT);

// ------------------------------------------------------------- primitives

const Mark: React.FC<{ size: number; color: string; t?: number; at?: number }> = ({
  size,
  color,
  t,
  at,
}) => {
  // Drawn from its own geometry. Animated, the upright lands first, then the
  // claim that crosses, then the claim that stops short of it.
  const a = at === undefined || t === undefined ? 1 : prog(t, at, 0.3);
  const b = at === undefined || t === undefined ? 1 : prog(t, at + BEAT * 0.5, 0.36);
  const c = at === undefined || t === undefined ? 1 : prog(t, at + BEAT, 0.3);
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" style={{ display: "block", overflow: "visible" }}>
      <g fill="none" stroke={color} strokeWidth={6} strokeLinecap="butt">
        <path d={`M39 ${32 - 24 * a} V${32 + 24 * a}`} />
        <path d={`M6 23 H${6 + 52 * b}`} />
        <path d={`M6 43 H${6 + 23 * c}`} />
      </g>
    </svg>
  );
};

const Masthead: React.FC<{ th: Theme }> = ({ th }) => (
  <div
    style={{
      position: "absolute",
      top: 64,
      left: LEFT,
      right: LEFT,
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
    }}
  >
    <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
      <Mark size={34} color={th.ink} />
      <span style={{ fontFamily: SERIF, fontSize: 34, color: th.ink, letterSpacing: "-0.01em" }}>
        Hearsay
      </span>
    </div>
    <span style={{ fontFamily: SANS, fontSize: 24, color: th.faint }}>hearsay.run</span>
  </div>
);

const Headline: React.FC<{
  th: Theme;
  t: number;
  at: number;
  size?: number;
  children: React.ReactNode;
  color?: string;
  weight?: number;
}> = ({ th, t, at, size = 104, children, color, weight = 300 }) => (
  <div
    style={{
      fontFamily: SERIF,
      fontWeight: weight,
      fontSize: size,
      lineHeight: 1.08,
      letterSpacing: "-0.022em",
      color: color ?? th.ink,
      ...enter(t, at),
    }}
  >
    {children}
  </div>
);

const Label: React.FC<{ th: Theme; t: number; at: number; children: React.ReactNode; color?: string }> = ({
  th,
  t,
  at,
  children,
  color,
}) => (
  <div style={{ fontFamily: SANS, fontSize: 30, color: color ?? th.soft, ...enter(t, at) }}>{children}</div>
);

const VOTE: Record<string, string> = {
  yes: "yes",
  no: "no",
  unread: "unread",
  unasked: "not asked",
  "": "not reached",
  none: "no conflict",
};

/** Every vote, beside the verdict. One cell per beat. */
const Bench: React.FC<{ th: Theme; t: number; at: number; votes: { a: string; b: string; conflict: string } }> = ({
  th,
  t,
  at,
  votes,
}) => {
  const cells: Array<[string, string]> = [
    ["framing one", votes.a],
    ["framing two", votes.b],
    ["consistency", votes.conflict],
  ];
  return (
    <div style={{ display: "flex", gap: 64, marginTop: 34 }}>
      {cells.map(([label, raw], i) => {
        const word = VOTE[raw] ?? `conflicts with ${raw}`;
        const loud = raw === "unread";
        const idle = raw === "" || raw === "unasked";
        return (
          <div key={label} style={{ ...enter(t, at + i * BEAT * 0.5, 0.24, 10) }}>
            <div style={{ fontFamily: SANS, fontSize: 22, color: th.faint }}>{label}</div>
            <div
              style={{
                fontFamily: SANS,
                fontWeight: idle ? 400 : 600,
                fontSize: 34,
                marginTop: 4,
                color: loud ? th.flag : idle ? th.faint : th.ink,
              }}
            >
              {word}
            </div>
          </div>
        );
      })}
    </div>
  );
};

const Typed: React.FC<{ text: string; t: number; from: number; to: number }> = ({ text, t, from, to }) => {
  const n = Math.round(text.length * prog(t, from, to - from));
  return (
    <>
      {text.slice(0, n)}
      <span style={{ opacity: n < text.length ? 1 : 0 }}>▍</span>
    </>
  );
};

// ------------------------------------------------------------------ scenes

const S0Problem: React.FC<{ t: number; th: Theme }> = ({ t, th }) => (
  <div style={{ position: "absolute", left: LEFT, top: 400, width: 1600 }}>
    <Headline th={th} t={t} at={0.25} size={116}>
      An agent reads a shared memory
    </Headline>
    <Headline th={th} t={t} at={d(0)} color={th.soft} size={116}>
      <em>and acts on what it finds there.</em>
    </Headline>
  </div>
);

const S1Anyone: React.FC<{ t: number; th: Theme }> = ({ t, th }) => (
  <div style={{ position: "absolute", left: LEFT, top: 380, width: 1600 }}>
    <Headline th={th} t={t} at={d(1)} size={128}>
      Anyone can write to it.
    </Headline>
    <div style={{ marginTop: 40 }}>
      <Label th={th} t={t} at={d(2)}>
        <span style={{ fontSize: 42, color: th.soft }}>
          One unsupported sentence can become a premise for later decisions.
        </span>
      </Label>
    </div>
  </div>
);

const OfferedClaim: React.FC<{ t: number; th: Theme; typeFrom: number; typeTo: number }> = ({
  t,
  th,
  typeFrom,
  typeTo,
}) => (
  <div style={{ position: "absolute", left: LEFT, top: 250, width: 1560 }}>
    <Label th={th} t={t} at={d(3)}>
      Something offered this to the shared memory.
    </Label>
    <div
      style={{
        marginTop: 30,
        paddingLeft: 40,
        borderLeft: `4px solid ${th.ink}`,
        fontFamily: SERIF,
        fontWeight: 300,
        fontSize: 78,
        lineHeight: 1.14,
        letterSpacing: "-0.02em",
        color: th.ink,
        minHeight: 270,
        ...enter(t, d(3) + 0.1),
      }}
    >
      <Typed text={injection.claim} t={t} from={typeFrom} to={typeTo} />
    </div>
  </div>
);

const S3Refused: React.FC<{ t: number; th: Theme }> = ({ t, th }) => (
  <div style={{ position: "absolute", left: LEFT + 44, top: 690, width: 1500 }}>
    <div style={{ fontFamily: SERIF, fontSize: 64, letterSpacing: "-0.015em", color: th.ink, ...stamp(t, d(5)) }}>
      Refused as unsourced.
    </div>
    <Bench th={th} t={t} at={d(5) + BEAT} votes={injection.votes} />
    <div style={{ marginTop: 34, fontFamily: MONO, fontSize: 27, color: th.soft, ...enter(t, d(6)) }}>
      {new URL(injection.source_url).host + new URL(injection.source_url).pathname}
      {"  scripted source snapshot "}
      {injection.snapshot_hash.slice(0, 16)}
    </div>
  </div>
);

const S4Twice: React.FC<{ t: number; th: Theme }> = ({ t, th }) => (
  <div style={{ position: "absolute", left: LEFT, top: 250, width: 1600 }}>
    <Headline th={th} t={t} at={d(7)} size={84}>
      A readable source faces two support questions.
    </Headline>
    <div
      style={{
        marginTop: 46,
        paddingLeft: 40,
        borderLeft: `4px solid ${th.ink}`,
        fontFamily: SERIF,
        fontWeight: 300,
        fontSize: 56,
        lineHeight: 1.18,
        color: th.ink,
        ...enter(t, d(7) + 0.25),
      }}
    >
      {split.claim}
    </div>
    <div style={{ paddingLeft: 44 }}>
      <Bench th={th} t={t} at={d(7) + BEAT * 1.5} votes={split.votes} />
      <div style={{ marginTop: 40, fontFamily: SERIF, fontSize: 60, color: th.ink, ...stamp(t, d(8)) }}>
        Not admitted: inconclusive.
      </div>
      <div style={{ marginTop: 14, fontFamily: SANS, fontSize: 32, color: th.soft, ...enter(t, d(8) + BEAT) }}>
        Both framings must agree. An unreadable answer stays inconclusive.
      </div>
    </div>
  </div>
);

// --------------------------------------------------------------- the graph

const SHORT: Record<number, string> = {
  0: "ACME was dissolved in March.",
  1: "ACME sold its warehouse in April.",
  2: "The April sale was made by a dissolved firm.",
  17: "ACME's number is 118422.",
  14: "Its creditors dealt with no one.",
  15: "Their recovery rests on that sale.",
  16: "It was lodged in time.",
};

const COL = (depth: number) => LEFT + depth * 330;
const ROW1 = 430;
const ROW2 = 700;
const NODES: Record<number, { x: number; y: number }> = {
  0: { x: COL(0), y: ROW1 },
  1: { x: COL(0), y: ROW2 },
  2: { x: COL(1), y: ROW1 },
  17: { x: COL(1), y: ROW2 },
  14: { x: COL(2), y: ROW1 },
  15: { x: COL(3), y: ROW1 },
  16: { x: COL(4), y: ROW1 },
};
const EDGES: Array<[number, number]> = [
  [0, 2],
  [1, 2],
  [0, 17],
  [2, 14],
  [14, 15],
  [15, 16],
];
const NW = 296;
const NH = 228;

/** Map the computed walk onto the beat grid. */
const SCHEDULE: Array<{ at: number; id: number; became: string }> = (() => {
  const out: Array<{ at: number; id: number; became: string }> = [];
  const first = walk.steps.filter((s) => !s.rejudged && s.depth !== null);
  // the walk: one depth per beat from the hit
  for (const s of first) {
    const at = s.depth === 0 ? d(10) : s.became === "DEFERRED" ? d(11) : d(10) + (s.depth as number) * BEAT;
    out.push({ at, id: s.id, became: s.became });
  }
  // the rejudge and the follow-up walk: one step per beat from d12
  const rest = walk.steps.slice(first.length);
  rest.forEach((s, i) => out.push({ at: d(12) + i * BEAT * 0.5, id: s.id, became: s.became }));
  return out;
})();

const stateAt = (id: number, t: number) => {
  let st = "ADMITTED";
  for (const s of SCHEDULE) if (s.id === id && t >= s.at) st = s.became;
  return st;
};

const Graph: React.FC<{ t: number; th: Theme; drawFrom: number }> = ({ t, th, drawFrom }) => {
  const order = [0, 1, 2, 17, 14, 15, 16];
  const shownAt = (id: number) => drawFrom + order.indexOf(id) * BEAT * 0.5;
  const tone = (st: string) =>
    st === "REVOKED" ? th.flag : st === "TAINTED" ? th.flag : st === "DEFERRED" ? th.faint : th.ink;
  return (
    <>
      <svg width={W} height={1080} style={{ position: "absolute", left: 0, top: 0 }}>
        {EDGES.map(([a, b]) => {
          const A = NODES[a];
          const B = NODES[b];
          const p = prog(t, Math.max(shownAt(a), shownAt(b)), 0.3);
          const x1 = A.x + NW;
          const y1 = A.y + NH / 2;
          const x2 = B.x;
          const y2 = B.y + NH / 2;
          return (
            <line
              key={`${a}-${b}`}
              x1={x1}
              y1={y1}
              x2={x1 + (x2 - x1) * p}
              y2={y1 + (y2 - y1) * p}
              stroke={stateAt(a, t) === "REVOKED" ? th.flag : th.rule}
              strokeWidth={2}
            />
          );
        })}
        {/* the depth bound, drawn where it bites */}
        <line
          x1={COL(4) - 18}
          y1={ROW1 - 30}
          x2={COL(4) - 18}
          y2={ROW2 + NH + 10}
          stroke={th.faint}
          strokeWidth={2}
          strokeDasharray="6 8"
          opacity={prog(t, d(10) + BEAT * 0.5, 0.3)}
        />
      </svg>
      <div
        style={{
          position: "absolute",
          left: COL(4) - 18,
          top: ROW2 + NH + 22,
          fontFamily: SANS,
          fontSize: 26,
          color: th.faint,
          opacity: prog(t, d(10) + BEAT * 0.5, 0.3),
          transform: "translateX(-50%)",
        }}
      >
        depth bound {corpus.policy.cascade_depth}
      </div>
      {order.map((id) => {
        const n = NODES[id];
        const st = stateAt(id, t);
        const changed = SCHEDULE.filter((s) => s.id === id && t >= s.at).pop();
        const pulse = changed ? stamp(t, changed.at) : {};
        return (
          <div
            key={id}
            style={{
              position: "absolute",
              left: n.x,
              top: n.y,
              width: NW,
              height: NH,
              padding: "18px 20px",
              boxSizing: "border-box",
              border: `2px ${st === "DEFERRED" ? "dashed" : "solid"} ${
                st === "ADMITTED" ? th.rule : tone(st)
              }`,
              background: th.paper,
              borderRadius: 4,
              ...enter(t, shownAt(id), 0.26, 12),
            }}
          >
            <div style={{ fontFamily: SANS, fontSize: 22, color: th.faint }}>entry {id}</div>
            <div
              style={{
                fontFamily: SERIF,
                fontSize: 29,
                lineHeight: 1.2,
                // Revoked claims dim rather than strike through: at this size a
                // line through the text fuses the letters into one bar.
                color: st === "REVOKED" ? th.faint : th.ink,
                marginTop: 6,
                height: 108,
                overflow: "hidden",
              }}
            >
              {SHORT[id]}
            </div>
            <div
              style={{
                fontFamily: SANS,
                fontWeight: 600,
                fontSize: 25,
                marginTop: 10,
                color: tone(st),
                ...pulse,
              }}
            >
              {st === "ADMITTED" && changed ? "SURVIVES" : st}
            </div>
          </div>
        );
      })}
    </>
  );
};

const S5Leans: React.FC<{ t: number; th: Theme }> = ({ t, th }) => (
  <>
    <div style={{ position: "absolute", left: LEFT, top: 200, width: 1600 }}>
      <Headline th={th} t={t} at={d(9)} size={76}>
        Every entry records what it leans on.
      </Headline>
    </div>
    <Graph t={t} th={th} drawFrom={d(9) + 0.25} />
  </>
);

const CAPTIONS: Array<[number, string]> = [
  [10, "Revoke one. Everything standing on it is tainted."],
  [11, "Past the depth bound, it waits for the next walk."],
  [12, "Each is judged again, without the dead premise."],
  [13, "One stands on its own source. The rest fall."],
];

const S6Cascade: React.FC<{ t: number; th: Theme }> = ({ t, th }) => {
  const current = CAPTIONS.filter(([bar]) => t >= d(bar)).pop();
  return (
    <>
      <div style={{ position: "absolute", left: LEFT, top: 200, width: 1640 }}>
        {current && (
          <div
            key={current[0]}
            style={{
              fontFamily: SERIF,
              fontWeight: 300,
              fontSize: 64,
              lineHeight: 1.12,
              letterSpacing: "-0.018em",
              color: th.ink,
              ...enter(t, d(current[0]), 0.26),
            }}
          >
            {current[1]}
          </div>
        )}
      </div>
      <Graph t={t} th={th} drawFrom={-10} />
    </>
  );
};

const S7Number: React.FC<{ t: number; th: Theme }> = ({ t, th }) => t >= d(15) ? (
  <div style={{ position: "absolute", left: LEFT, top: 230, width: 1620 }}>
    <Label th={th} t={t} at={d(15)}>Bradbury checkpoint, {checkpoint.checked_at.slice(0, 10)}</Label>
    <div style={{ fontFamily: SERIF, fontSize: 190, fontWeight: 300, lineHeight: 1.12,
      letterSpacing: "-0.04em", color: th.ink, marginTop: 16, ...stamp(t, d(15)) }}>
      {checkpoint.coverage.honest_judged} / {checkpoint.required_honest_judgements}
    </div>
    <div style={{ fontFamily: SANS, fontSize: 38, color: th.soft, marginTop: 12, ...enter(t, d(15) + 0.12) }}>
      verified honest controls. Evaluation incomplete.
    </div>
    <div style={{ fontFamily: SANS, fontSize: 30, color: th.flag, marginTop: 24, ...enter(t, d(15) + 0.25) }}>
      {checkpoint.coverage.judged - checkpoint.coverage.honest_judged} negative-case verdicts. Accepted receipts remain provisional.
    </div>
    <div style={{ fontFamily: MONO, fontSize: 25, color: th.soft, marginTop: 30, ...enter(t, d(15) + 0.35) }}>
      {checkpoint.checked_at.replace("T", " ").replace(/\.\d+\+00:00$/, " UTC")}
    </div>
  </div>
) : (
  <div style={{ position: "absolute", left: LEFT, top: 250, width: 1620 }}>
    <Label th={th} t={t} at={d(14)}>
      Offline scripted controls
    </Label>
    <div
      style={{
        fontFamily: SERIF,
        fontWeight: 300,
        fontSize: 260,
        lineHeight: 1,
        letterSpacing: "-0.04em",
        color: th.ink,
        marginTop: 10,
        ...stamp(t, d(14) + BEAT * 0.5),
      }}
    >
      {honestRefused} of {honest}
    </div>
    <div style={{ fontFamily: SANS, fontSize: 38, color: th.soft, marginTop: 6, ...enter(t, d(14) + BEAT) }}>
      honest entries refused in the harness.
    </div>
    {/* The page carries this warning and so does the film. The judge in this
        run is a scripted stand-in; printing its number without saying so would
        be claiming a defence nobody has measured yet. */}
    <div style={{ fontFamily: SANS, fontSize: 27, color: th.flag, marginTop: 14, ...enter(t, d(14) + BEAT * 2) }}>
      Fictional sources and scripted votes. This is not live attack evidence.
    </div>
    <div
      style={{
        marginTop: 50,
        fontFamily: SERIF,
        fontSize: 54,
        color: th.ink,
        letterSpacing: "-0.012em",
        ...enter(t, d(14) + BEAT * 2.5),
      }}
    >
      {judged} of {judged} verdicts replay from the votes as cast.
    </div>
    <div style={{ fontFamily: SANS, fontSize: 30, color: th.soft, marginTop: 10, ...enter(t, d(14) + BEAT * 3) }}>
      No chain, no network, no model. Just the receipt.
    </div>
  </div>
);

const S8Gate: React.FC<{ t: number; th: Theme }> = ({ t, th }) => {
  const codes: Array<[string, string]> = [
    ["0", "admitted"],
    ["1", "refused"],
    ["2", "inconclusive / no record"],
    ["3", "malformed input"],
  ];
  return (
    <div style={{ position: "absolute", left: LEFT, top: 290, width: 1640 }}>
      <Headline th={th} t={t} at={d(16)} size={92}>
        Not a report you read.
      </Headline>
      <Headline th={th} t={t} at={d(16) + BEAT}>
        <em>A gate you install.</em>
      </Headline>
      <div style={{ display: "flex", gap: 0, marginTop: 70, borderTop: `2px solid ${th.ink}` }}>
        {codes.map(([c, w], i) => (
          <div
            key={c}
            style={{
              flex: 1, minWidth: 0,
              paddingTop: 20,
              borderLeft: i ? `1px solid ${th.rule}` : "none",
              paddingLeft: i ? 26 : 0,
              ...enter(t, d(16) + BEAT * 2 + i * BEAT * 0.33, 0.22, 10),
            }}
          >
            <div style={{ fontFamily: MONO, fontSize: 30, color: th.soft }}>exit {c}</div>
            <div style={{ fontFamily: SERIF, fontSize: 36, color: th.ink, marginTop: 6 }}>{w}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

const S9End: React.FC<{ t: number; th: Theme }> = ({ t, th }) => (
  <AbsoluteFill style={{ justifyContent: "center", paddingLeft: 260 }}>
    <div style={{ display: "flex", alignItems: "center", gap: 64 }}>
      <Mark size={230} color={th.ink} t={t} at={o(0)} />
      <div>
        <div
          style={{
            fontFamily: SERIF,
            fontWeight: 400,
            fontSize: 150,
            letterSpacing: "-0.03em",
            lineHeight: 1,
            color: th.ink,
            ...enter(t, o(1), 0.36),
          }}
        >
          Hearsay
        </div>
        <div style={{ fontFamily: SANS, fontSize: 36, color: th.soft, marginTop: 18, ...enter(t, o(2)) }}>
          Admissibility for shared agent memory.
        </div>
      </div>
    </div>
    <div
      style={{
        position: "absolute",
        left: 260,
        bottom: 170,
        fontFamily: SANS,
        fontWeight: 600,
        fontSize: 64,
        letterSpacing: "-0.01em",
        color: th.ink,
        ...stamp(t, o(3)),
      }}
    >
      hearsay.run
    </div>
    <div
      style={{
        position: "absolute",
        left: 260,
        bottom: 120,
        fontFamily: SANS,
        fontSize: 28,
        color: th.faint,
        ...enter(t, o(4)),
      }}
    >
      Built on GenLayer · Demo: hearsay-psi.vercel.app
    </div>
  </AbsoluteFill>
);

// -------------------------------------------------------------------- film

export const Film: React.FC = () => {
  const frame = useCurrentFrame();
  const t = frame / FPS;
  const th = themeAt(t);

  return (
    <AbsoluteFill style={{ background: th.paper }}>
      <Audio src={staticFile("track.wav")} />
      {t < o(0) && <Masthead th={th} />}
      {t < d(14) && <div style={{ position: "absolute", left: LEFT, top: 126,
        fontFamily: SANS, fontSize: 24, color: th.soft }}>
        Offline scripted demo · fictional sources · cascade replayed locally
      </div>}

      {between(t, 0, d(1)) && <S0Problem t={t} th={th} />}
      {between(t, d(1), d(3)) && <S1Anyone t={t} th={th} />}
      {between(t, d(3), d(7)) && (
        <OfferedClaim t={t} th={th} typeFrom={d(3) + 0.35} typeTo={d(5) - BEAT * 0.75} />
      )}
      {between(t, d(5), d(7)) && <S3Refused t={t} th={th} />}
      {between(t, d(7), d(9)) && <S4Twice t={t} th={th} />}
      {between(t, d(9), d(10)) && <S5Leans t={t} th={th} />}
      {between(t, d(10), d(14)) && <S6Cascade t={t} th={th} />}
      {between(t, d(14), d(16)) && <S7Number t={t} th={th} />}
      {between(t, d(16), o(0)) && <S8Gate t={t} th={th} />}
      {t >= o(0) && <S9End t={t} th={th} />}
    </AbsoluteFill>
  );
};
