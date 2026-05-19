function Header() {
  return (
    <header className="site-header">
      <a href="#" className="brand">
        <span className="brand-name">Sifu</span><span className="brand-dot" />
      </a>
      <nav className="site-nav">
        <a href="#how">How it works</a>
        <a href="#cases">Cases</a>
        <a href="#pricing">Pricing</a>
        <a href="#docs" className="mono-link">Docs ↗</a>
      </nav>
      <a href="#start" className="btn btn-primary">Start watching</a>
    </header>
  );
}
window.Header = Header;
