function ReportFooter() {
  return (
    <footer className="rf">
      <div className="rf-line">
        <span className="seal"><span className="seal-mark">師</span>Verified by Sifu</span>
        <span className="rf-meta">obs_a83f · classified 2026-04-28 14:32 · v0.1.4</span>
      </div>
      <p className="rf-note">
        This report was generated from 312 local observations over 14 days.
        Source events stay on your machine. Sifu watches; nothing leaves.
      </p>
    </footer>
  );
}
window.ReportFooter = ReportFooter;
