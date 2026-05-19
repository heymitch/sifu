function AgentPlan() {
  return (
    <section className="ap">
      <div className="eyebrow">If you'd like, an agent can run this</div>
      <h2 className="rs-h2">Here's what Sifu would automate.</h2>
      <p className="rs-prose">
        You'd review the draft replies, not write them. The agent would
        defer when it sees an exception (see above). You stay the teacher.
      </p>
      <pre className="ap-code"><code>{`# workflow-0042.sifu
trigger:  schedule = "TUE 09:00 local"
defer:    inbox.unread > 40
defer:    thread.label != "enterprise" and confidence < 0.92

steps:
  01  inbox.sort(by="age", dir="desc")
  02  threads = inbox.filter(label="enterprise", age<="72h")
      threads.star()
  03  for t in threads:
        draft = snippet("T-Triage-Std").apply(t)
        await human.review(draft)
        t.reply(draft)
  04  threads.tag("triaged").archive()`}</code></pre>
      <div className="ap-actions">
        <a href="#" className="btn btn-primary">Enable agent</a>
        <a href="#" className="btn btn-tertiary">Export workflow file →</a>
      </div>
    </section>
  );
}
window.AgentPlan = AgentPlan;
