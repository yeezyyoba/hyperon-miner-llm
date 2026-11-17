export const PROVIDER_NAMES = {
  groq: "Groq",
  nvidia: "NVIDIA",
  gemini: "Gemini",
  mock: "Offline mock",
  "mock:garbage": "Mock (bad answers)",
  "mock:error": "Mock (errors)",
  "mock:fatal": "Mock (outage)",
  unknown: "Unknown",
};

export const STRATEGY_NAMES = {
  llm: "LLM ranks joins",
  "llm-direct": "LLM scores every candidate",
  cardinality: "Cardinality baseline",
  heuristic: "Heuristic baseline",
  random: "Random order",
  exhaustive: "Exhaustive",
};

export function familyName(family) {
  if (!family) return "";
  const [strategy, provider] = family.split(":");
  const base = {
    llm: "LLM",
    "llm-direct": "LLM, every candidate",
    cardinality: "Cardinality",
    heuristic: "Heuristic",
    random: "Random",
    exhaustive: "Exhaustive",
    upstream: "Upstream",
  }[strategy] ?? strategy;
  return provider ? `${base} (${PROVIDER_NAMES[provider] ?? provider})` : base;
}

const int = new Intl.NumberFormat("en-US");
export const fmtInt = (n) => (n == null ? "–" : int.format(Math.round(n)));
export const fmtPct = (x, digits = 0) => (x == null ? "–" : `${(x * 100).toFixed(digits)} %`);
export const fmtSec = (s) => (s == null ? "–" : s < 10 ? `${s.toFixed(1)} s` : `${Math.round(s)} s`);
export function fmtUsd(x) {
  if (x == null) return "–";
  if (x === 0) return "$0";
  if (x < 0.01) return `$${x.toFixed(4)}`;
  return `$${x.toFixed(2)}`;
}

// "(, (ENROLLED_IN $v0 $v1) (MAJORS_IN $v0 dept_0))" -> [{pred, args:[{var|const}]}]
export function parsePattern(text) {
  const body = text.trim().replace(/^\(,\s*/, "").replace(/\)\s*$/, "");
  const clauses = [];
  const re = /\(([^()]+)\)/g;
  let m;
  while ((m = re.exec(body))) {
    const [pred, ...args] = m[1].trim().split(/\s+/);
    clauses.push({
      pred,
      args: args.map((a) => (a.startsWith("$") ? { v: a } : { c: a })),
    });
  }
  return clauses;
}

// Variables get letters in order of first appearance: $v0 -> a, $v1 -> b, ...
export function variableNames(clauses) {
  const names = new Map();
  clauses.forEach((cl) =>
    cl.args.forEach((a) => {
      if (a.v && !names.has(a.v)) names.set(a.v, names.size);
    }),
  );
  return names;
}

export const readablePredicate = (p) =>
  p.toLowerCase().replace(/_/g, " ");
