function Exceptions() {
  const exc = [
    { date: '2026-04-14', why: 'Inbox had >40 unread; you batched into two passes.' },
    { date: '2026-03-31', why: 'Quarter-end; an enterprise thread escalated, you skipped step 03.' },
    { date: '2026-03-17', why: 'Holiday week; pattern did not run.' },
  ];
  return (
    <section className="ex">
      <div className="eyebrow">When it doesn't apply</div>
      <h2 className="rs-h2">7 exceptions in the last 14 days.</h2>
      <p className="rs-prose">
        The pattern holds on most Tuesdays. Here's when it didn't —
        these are the cases an automation would need to defer back to you.
      </p>
      <ul className="ex-list">
        {exc.map(e => (
          <li key={e.date}>
            <span className="ex-date">{e.date}</span>
            <span className="ex-why">{e.why}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
window.Exceptions = Exceptions;
