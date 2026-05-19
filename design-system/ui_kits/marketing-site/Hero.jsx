function Hero() {
  return (
    <section className="hero">
      <div className="eyebrow">Workflow classifier · v0.1</div>
      <h1 className="hero-title">
        I see you do this <br/> 14 times a week.
      </h1>
      <p className="hero-sub">
        Sifu watches what you do, identifies the patterns,
        and teaches you the system you didn't know you already had.
      </p>
      <div className="hero-actions">
        <a href="#start" className="btn btn-primary">Start watching</a>
        <a href="#sample" className="btn btn-secondary">Read a sample report →</a>
      </div>
      <div className="hero-meta">
        <span><b>312</b> observations · ticket triage</span>
        <span className="dot" />
        <span><b>94.2%</b> classification confidence</span>
        <span className="dot" />
        <span>Tuesday · 09:14</span>
      </div>
    </section>
  );
}
window.Hero = Hero;
