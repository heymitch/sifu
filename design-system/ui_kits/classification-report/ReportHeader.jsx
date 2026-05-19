function ReportHeader() {
  return (
    <header className="rh">
      <div className="rh-top">
        <div className="rh-id">
          <span className="eyebrow">Workflow · 0042</span>
          <span className="rh-sep">·</span>
          <span className="eyebrow">Support</span>
          <span className="rh-sep">·</span>
          <span className="eyebrow">Tuesday cohort</span>
        </div>
        <span className="stamp">CLASSIFIED</span>
      </div>
      <h1 className="rh-title">Ticket triage, Tuesday mornings</h1>
      <p className="rh-lead">I see you do this 14 times a week. The pattern is consistent.</p>
    </header>
  );
}
window.ReportHeader = ReportHeader;
