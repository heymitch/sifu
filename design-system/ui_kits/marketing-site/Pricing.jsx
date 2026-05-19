function Pricing() {
  return (
    <section id="pricing" className="pricing">
      <div className="eyebrow">Pricing</div>
      <h2 className="section-title">Two plans. No surprises.</h2>
      <div className="plan-grid">
        <article className="plan">
          <div className="plan-head">
            <span className="eyebrow">For one</span>
            <h3>Solo</h3>
          </div>
          <div className="plan-price"><span className="num">$24</span><span className="per">/ month</span></div>
          <ul className="plan-list">
            <li>Up to 5 watched workflows</li>
            <li>Weekly written report</li>
            <li>Local-only observation</li>
            <li>Export to JSON, Markdown</li>
          </ul>
          <a href="#start" className="btn btn-secondary">Start watching</a>
        </article>
        <article className="plan plan-feature">
          <div className="plan-head">
            <span className="eyebrow seal-eb">
              <span className="seal-mark">師</span> For teams
            </span>
            <h3>Studio</h3>
          </div>
          <div className="plan-price"><span className="num">$96</span><span className="per">/ seat / month</span></div>
          <ul className="plan-list">
            <li>Unlimited watched workflows</li>
            <li>Shared classification library</li>
            <li>Agent runners (beta)</li>
            <li>SSO, audit log, on-prem option</li>
          </ul>
          <a href="#start" className="btn btn-primary">Start watching</a>
        </article>
      </div>
    </section>
  );
}
window.Pricing = Pricing;
