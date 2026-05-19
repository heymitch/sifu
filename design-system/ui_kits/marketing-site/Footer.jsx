function Footer() {
  return (
    <footer className="site-footer">
      <div className="footer-top">
        <div className="footer-brand">
          <span className="brand-name">Sifu</span><span className="brand-dot" />
          <p className="footer-tag">Workflow classifier. Calmly.</p>
        </div>
        <div className="footer-cols">
          <div>
            <div className="eyebrow">Product</div>
            <a href="#">How it works</a>
            <a href="#">Sample reports</a>
            <a href="#">Pricing</a>
            <a href="#">Changelog</a>
          </div>
          <div>
            <div className="eyebrow">Cases</div>
            <a href="#">Support</a>
            <a href="#">Writing</a>
            <a href="#">Finance</a>
            <a href="#">Engineering</a>
          </div>
          <div>
            <div className="eyebrow">Company</div>
            <a href="#">About</a>
            <a href="#">Notes</a>
            <a href="#">Privacy</a>
            <a href="#">Contact</a>
          </div>
        </div>
      </div>
      <div className="footer-bottom">
        <span className="seal"><span className="seal-mark">師</span>Verified by Sifu</span>
        <span className="footer-meta">© 2026 · Sifu, Inc. · v0.1.4 · 2026-04-28</span>
      </div>
    </footer>
  );
}
window.Footer = Footer;
