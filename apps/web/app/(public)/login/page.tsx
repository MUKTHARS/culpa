"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Button } from "@/components/ui/Button/Button";
import { Card } from "@/components/ui/Card/Card";
import { Field, Input } from "@/components/ui/Field/Field";
import { ROUTES } from "@/constants/routes";
import { useAuth } from "@/context/AuthContext";
import { useAsyncAction } from "@/hooks/useAsyncAction";

function safeNext(next: string | null): string {
  // Only same-site paths, so the login page can't be used to redirect somewhere else.
  return next && next.startsWith("/") && !next.startsWith("//") ? next : ROUTES.cases;
}

function LoginForm() {
  const { username: current, loggedIn, login, logout } = useAuth();
  const router = useRouter();
  const next = safeNext(useSearchParams()?.get("next") ?? null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const submit = useAsyncAction(async () => {
    await login(username, password);
    router.push(next);
  });

  if (loggedIn) {
    return (
      <div className="stack">
        <p>
          Signed in as <strong>{current}</strong>.
        </p>
        <div className="row">
          <Button onClick={() => router.push(next)}>Open the dispute console</Button>
          <Button variant="secondary" onClick={() => logout()}>
            Log out
          </Button>
        </div>
      </div>
    );
  }

  return (
    <form
      className="stack"
      onSubmit={(e) => {
        e.preventDefault();
        submit.run();
      }}
    >
      <Field label="Username">
        <Input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required autoFocus />
      </Field>
      <Field label="Password">
        <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
               autoComplete="current-password" required />
      </Field>
      <div className="row">
        <Button type="submit" loading={submit.pending}>
          Log in
        </Button>
      </div>
      {submit.error && <p className="error">{submit.error}</p>}
    </form>
  );
}

export default function LoginPage() {
  return (
    <main className="page" style={{ maxWidth: 480 }}>
      <Card title="Analyst login" subtitle="Sign in to the dispute console. Sessions expire after 12 hours.">
        <Suspense fallback={null}>
          <LoginForm />
        </Suspense>
      </Card>
    </main>
  );
}
