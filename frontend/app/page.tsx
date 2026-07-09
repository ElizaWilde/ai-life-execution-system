import Link from "next/link";

export default function HomePage() {
  return (
    <section className="hero">
      <p className="eyebrow">AI Life Execution System</p>
      <h1>Plan the week, execute today, review tonight.</h1>
      <p className="muted">
        Use the MVP flow to create weekly goals, generate daily tasks, track study
        sessions, and summarize progress.
      </p>
      <div className="actions">
        <Link href="/weekly-plan" className="button primary">
          Start weekly plan
        </Link>
        <Link href="/dashboard" className="button secondary">
          View dashboard
        </Link>
      </div>
    </section>
  );
}
   