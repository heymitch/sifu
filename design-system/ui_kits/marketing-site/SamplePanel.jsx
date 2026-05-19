function SamplePanel() {
  return (
    <section id="sample" className="sample">
      <div className="sample-side">
        <div className="eyebrow">A real report</div>
        <h2 className="section-title">The output is a written case.</h2>
        <p className="prose">
          Sifu doesn't ship a dashboard of metrics. It ships a teacher's
          memo: what it saw, when it works, when it doesn't, and the exact
          steps it would automate.
        </p>
        <a href="#cases" className="btn btn-secondary">Read more cases →</a>
      </div>
      <article className="report-mini">
        <header className="report-mini-head">
          <span className="eyebrow">Workflow · 0042</span>
          <span className="stamp-mini">CLASSIFIED</span>
        </header>
        <h3>Ticket triage, Tuesday mornings</h3>
        <p className="report-lead">
          I see you do this 14 times a week. The pattern is consistent.
        </p>
        <hr />
        <ol className="report-steps">
          <li><span className="step-id">01</span> Open inbox, sort by age (descending).</li>
          <li><span className="step-id">02</span> Skim subjects; star anything from <code>@enterprise</code>.</li>
          <li><span className="step-id">03</span> Draft a 3-line response from the boilerplate.</li>
          <li><span className="step-id">04</span> Tag <code>triaged</code>, archive thread.</li>
        </ol>
        <hr />
        <div className="report-meta">
          <span><b>312</b> observations</span>
          <span><b>94.2%</b> confidence</span>
          <span>14 days</span>
        </div>
      </article>
    </section>
  );
}
window.SamplePanel = SamplePanel;
