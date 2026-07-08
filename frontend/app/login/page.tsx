"use client";

import { FormEvent, useEffect, useState } from "react";
import { getStoredUserId, setStoredUserId } from "../../lib/auth";

export default function LoginPage() {
  const [userId, setUserId] = useState("1");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setUserId(getStoredUserId());
  }, []);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStoredUserId(userId);
    setSaved(true);
  }

  return (
    <section className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Temporary auth</p>
          <h1>User header</h1>
          <p className="muted">
            The MVP backend uses <code>X-User-ID</code>. Save the test user id here.
          </p>
        </div>
      </header>

      <div className="card">
        <form className="form" onSubmit={submit}>
          <label className="field">
            <span>User ID</span>
            <input
              className="input"
              min="1"
              type="number"
              value={userId}
              onChange={(event) => setUserId(event.target.value)}
            />
          </label>
          <button className="button primary" type="submit">
            Save user id
          </button>
        </form>
        {saved ? <p className="success">Saved. Future requests will use X-User-ID: {userId}</p> : null}
      </div>
    </section>
  );
}
