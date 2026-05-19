function Observations() {
  // 14-day series of counts (mostly Tuesdays heavy)
  const data = [0, 1, 14, 0, 0, 1, 0, 0, 2, 13, 1, 0, 0, 14];
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const max = Math.max(...data);
  return (
    <section className="obs">
      <div className="eyebrow">Observations · last 14 days</div>
      <div className="obs-chart">
        {data.map((v, i) => (
          <div key={i} className="obs-bar-wrap">
            <div className="obs-bar" style={{height: `${(v/max)*100}%`}} />
            <div className="obs-bar-label">{days[i % 7][0]}</div>
          </div>
        ))}
      </div>
      <table className="obs-table">
        <thead>
          <tr><th>Date</th><th>Day</th><th>Start</th><th>Duration</th><th>Steps</th><th>Match</th></tr>
        </thead>
        <tbody>
          <tr><td>2026-04-28</td><td>Tue</td><td>09:14</td><td>11m 02s</td><td>4 / 4</td><td>98.1%</td></tr>
          <tr><td>2026-04-21</td><td>Tue</td><td>09:08</td><td>12m 18s</td><td>4 / 4</td><td>96.4%</td></tr>
          <tr><td>2026-04-14</td><td>Tue</td><td>09:22</td><td>14m 51s</td><td>3 / 4</td><td>72.0%</td></tr>
          <tr><td>2026-04-07</td><td>Tue</td><td>09:11</td><td>10m 47s</td><td>4 / 4</td><td>97.9%</td></tr>
        </tbody>
      </table>
    </section>
  );
}
window.Observations = Observations;
