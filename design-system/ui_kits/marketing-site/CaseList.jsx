function CaseList() {
  const cases = [
    { id: '0042', title: 'Ticket triage, Tuesday mornings', tag: 'Support', obs: 312 },
    { id: '0039', title: 'Weekly status note from raw notes', tag: 'Writing', obs: 88 },
    { id: '0035', title: 'Invoice reconciliation, end of month', tag: 'Finance', obs: 24 },
    { id: '0028', title: 'Standup prep from yesterday\'s work', tag: 'Engineering', obs: 156 },
    { id: '0021', title: 'Customer-call follow-up email', tag: 'Sales', obs: 71 },
  ];
  return (
    <section id="cases" className="cases">
      <div className="eyebrow">Cases</div>
      <h2 className="section-title">Workflows Sifu has classified.</h2>
      <ul className="case-list">
        {cases.map(c => (
          <li key={c.id} className="case-row">
            <span className="case-id">Workflow · {c.id}</span>
            <a href="#" className="case-title">{c.title}</a>
            <span className="case-tag">{c.tag}</span>
            <span className="case-obs"><b>{c.obs}</b> observations</span>
            <span className="case-arrow">→</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
window.CaseList = CaseList;
