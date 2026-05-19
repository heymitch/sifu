function ReportSummary() {
  const metrics = [
    { label: 'Observations', value: '312' },
    { label: 'Confidence', value: '94.2%' },
    { label: 'Median duration', value: '11m 42s' },
    { label: 'Window', value: '14 days' },
    { label: 'Exceptions', value: '7' },
  ];
  return (
    <section className="rs">
      <div className="eyebrow">Summary</div>
      <p className="rs-prose">
        On most Tuesdays between 09:00 and 10:30, you triage the support
        inbox in a four-step sequence. The shape is stable across weeks:
        sort by age, identify the enterprise threads, draft a short reply
        from a boilerplate, then archive with a tag. You finish, on
        average, in <b>11 minutes 42 seconds</b>.
      </p>
      <dl className="rs-metrics">
        {metrics.map(m => (
          <div key={m.label} className="rs-metric">
            <dt>{m.label}</dt>
            <dd>{m.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
window.ReportSummary = ReportSummary;
