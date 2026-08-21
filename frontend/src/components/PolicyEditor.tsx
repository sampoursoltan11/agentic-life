import { useEffect, useState } from "react";
import { fetchPolicyRules, updatePolicyRules, type Constitution, type Rule } from "../api";

type Props = {
  onClose: () => void;
};

const NEW_RULE: Rule = { id: "", text: "", penalty: -2 };

export function PolicyEditor({ onClose }: Props) {
  const [doc, setDoc] = useState<Constitution | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetchPolicyRules().then(setDoc).catch(() => setStatus("⚠ couldn't load the constitution"));
  }, []);

  const setRule = (i: number, patch: Partial<Rule>) =>
    setDoc((d) => (d ? { ...d, rules: d.rules.map((r, j) => (j === i ? { ...r, ...patch } : r)) } : d));

  const removeRule = (i: number) =>
    setDoc((d) => (d ? { ...d, rules: d.rules.filter((_, j) => j !== i) } : d));

  const addRule = () => setDoc((d) => (d ? { ...d, rules: [...d.rules, { ...NEW_RULE }] } : d));

  const setReward = (key: string, value: number) =>
    setDoc((d) => (d ? { ...d, reward: { ...d.reward, [key]: value } } : d));

  const save = async () => {
    if (!doc) return;
    setBusy(true);
    setStatus(null);
    try {
      await updatePolicyRules(doc);
      setStatus("✔ constitution updated — the judge applies it from the next action");
    } catch (e) {
      setStatus(`⚠ ${e instanceof Error ? e.message : "save failed"}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal" onClick={onClose}>
      <div className="modal__panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal__head">
          <h2>⚖️ Town constitution</h2>
          <button className="sheet__close" onClick={onClose}>
            ✕
          </button>
        </div>
        <p className="modal__hint">
          Every action a citizen proposes is judged against these rules before it can happen.
          Rules are plain language — the judge model interprets them. Penalties are the reward
          hit for breaking a rule; citizens feel it through their reflections. Changes apply
          immediately and are saved to <code>config/constitution.yaml</code>.
        </p>

        {!doc ? (
          <p className="panel__empty">{status ?? "Loading…"}</p>
        ) : (
          <>
            <div className="rules">
              {doc.rules.map((rule, i) => (
                <div className="rule" key={i}>
                  <div className="rule__top">
                    <input
                      className="rule__id"
                      value={rule.id}
                      placeholder="rule_id"
                      onChange={(e) => setRule(i, { id: e.target.value })}
                    />
                    <label className="rule__penalty">
                      penalty
                      <input
                        type="number"
                        max={0}
                        value={rule.penalty}
                        onChange={(e) => setRule(i, { penalty: Number(e.target.value) })}
                      />
                    </label>
                    <button className="rule__remove" title="Remove this rule" onClick={() => removeRule(i)}>
                      ✕
                    </button>
                  </div>
                  <textarea
                    rows={2}
                    value={rule.text}
                    placeholder="Describe the rule in plain language…"
                    onChange={(e) => setRule(i, { text: e.target.value })}
                  />
                </div>
              ))}
            </div>

            <button className="btn" onClick={addRule}>
              ＋ Add rule
            </button>

            <h3 className="rules__reward-title">Rewards</h3>
            <div className="rules__rewards">
              {Object.entries(doc.reward).map(([key, value]) => (
                <label key={key}>
                  {key.replaceAll("_", " ")}
                  <input type="number" value={value} onChange={(e) => setReward(key, Number(e.target.value))} />
                </label>
              ))}
            </div>

            <div className="modal__foot">
              <button className="btn btn--primary" onClick={save} disabled={busy || doc.rules.length === 0}>
                Enact constitution
              </button>
              {status && <span className="editor__status">{status}</span>}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
