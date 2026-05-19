function ClassifiedSteps() {
  const steps = [
    {
      id: '01',
      verb: 'Open inbox, sort by age (descending)',
      detail: 'You always sort. The default view is by-thread, but you switch within 4 seconds of opening.',
      sources: ['inbox.sort=age', 'observed 311 / 312'],
    },
    {
      id: '02',
      verb: 'Skim subjects; star anything from @enterprise',
      detail: 'Threads with the @enterprise label or sender domain in the allowlist always get starred. You skip threads older than 72h.',
      sources: ['filter:label=enterprise', 'observed 308 / 312'],
    },
    {
      id: '03',
      verb: 'Draft a 3-line response from the boilerplate',
      detail: 'Greeting, acknowledgement, next-step. You use the canned response "T-Triage-Std" and edit ~2 words on average.',
      sources: ['snippet:T-Triage-Std', 'edit-distance avg 2.1'],
    },
    {
      id: '04',
      verb: 'Tag triaged, archive thread',
      detail: 'Always in this order — tag, then archive. Never archive without tag.',
      sources: ['tag:triaged', 'observed 312 / 312'],
    },
  ];
  return (
    <section className="cs">
      <div className="eyebrow">Classified steps</div>
      <h2 className="rs-h2">Here's the pattern.</h2>
      <ol className="cs-list">
        {steps.map(s => (
          <li key={s.id} className="cs-item">
            <div className="cs-id">{s.id}</div>
            <div className="cs-body">
              <h3 className="cs-verb">{s.verb}</h3>
              <p className="cs-detail">{s.detail}</p>
              <div className="cs-sources">
                {s.sources.map(src => <code key={src}>{src}</code>)}
              </div>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
window.ClassifiedSteps = ClassifiedSteps;
