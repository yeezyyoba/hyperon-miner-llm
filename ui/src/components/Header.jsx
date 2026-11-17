import { PROVIDER_NAMES } from "../format.js";

export default function Header({ providers }) {
  return (
    <header className="header">
      <div className="header__brand">
        <h1 className="wordmark">Pattern Miner</h1>
        <p className="header__tagline">
          An LLM decides which candidates the Hyperon miner checks first.
        </p>
      </div>
      {providers && (
        <ul className="header__providers" aria-label="LLM providers">
          {providers.providers.map((p) => (
            <li key={p.name} className={`provider-pill ${p.configured ? "is-ready" : "is-missing"}`}
                title={p.configured ? `${p.model}` : `No ${p.name.toUpperCase()}_API_KEY in .env`}>
              <span className="provider-pill__dot" aria-hidden="true" />
              {PROVIDER_NAMES[p.name]}
              <span className="provider-pill__state">{p.configured ? "key set" : "no key"}</span>
            </li>
          ))}
        </ul>
      )}
    </header>
  );
}
