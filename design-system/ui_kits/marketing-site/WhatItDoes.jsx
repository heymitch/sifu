function WhatItDoes() {
  const steps = [
    { n: '01', verb: 'Watches', body: 'Sifu sits beside you. It records the small repeated motions that make up an hour of your work — clicks, opens, edits, sends.' },
    { n: '02', verb: 'Classifies', body: 'After enough observations, the pattern surfaces. Sifu names the workflow, scores its confidence, and notes the exceptions.' },
    { n: '03', verb: 'Teaches',    body: 'You receive a written report — the kind a careful teacher would leave on your desk. Then, if you want, an agent runs it.' },
  ];
  return (
    <section id="how" className="how">
      <div className="eyebrow">How it works</div>
      <h2 className="section-title">Three quiet steps.</h2>
      <div className="how-grid">
        {steps.map(s => (
          <div key={s.n} className="how-step">
            <div className="how-num">{s.n}</div>
            <h3 className="how-verb">{s.verb}</h3>
            <p className="how-body">{s.body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
window.WhatItDoes = WhatItDoes;
