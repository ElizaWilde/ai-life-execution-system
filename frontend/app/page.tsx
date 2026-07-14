import Link from "next/link";

export default function HomePage() {
  return (
    <section className="hero">
      <p className="eyebrow">AI Life Execution System</p>
      <h1>Check in, plan with your capacity, and review what happened.</h1>
      <p className="muted">
        Use the Phase 2 loop to describe today’s condition, generate a realistic
        workload, track execution, and create grounded daily and weekly reviews.
      </p>
      <div className="actions">
        <Link href="/check-in" className="button primary">
          Start today’s check-in
        </Link>
        <Link href="/dashboard" className="button secondary">
          View dashboard
        </Link>
      </div>
    </section>
  );
}
