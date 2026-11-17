import { parsePattern, readablePredicate, variableNames } from "../format.js";

const LETTERS = "abcdefghij";

// One pattern as a row of clause tiles. Shared variables carry the same letter and
// colour in every clause, so the joins the miner found are visible at a glance.
export default function PatternView({ pattern }) {
  const clauses = parsePattern(pattern);
  const vars = variableNames(clauses);
  return (
    <span className="pattern" title={pattern}>
      {clauses.map((cl, i) => (
        <span key={i} className="clause">
          <span className="clause__pred">{readablePredicate(cl.pred)}</span>
          <span className="clause__args">
            {cl.args.map((a, j) =>
              a.v ? (
                <span key={j} className={`var var--${vars.get(a.v) % 4}`}>{LETTERS[vars.get(a.v)] ?? "?"}</span>
              ) : (
                <span key={j} className="const">{a.c}</span>
              ),
            )}
          </span>
        </span>
      ))}
    </span>
  );
}
