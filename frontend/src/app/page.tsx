import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function HomePage() {
  return (
    <main className="relative flex min-h-screen flex-col overflow-hidden">
      <div
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{
          background:
            "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(245, 158, 11, 0.25), transparent)",
        }}
      />
      <header className="relative z-10 flex items-center justify-between px-6 py-5">
        <span className="font-serif text-xl text-stone-100">Socratic Learner</span>
        <div className="flex gap-3">
          <Link href="/admin">
            <Button variant="ghost">Admin</Button>
          </Link>
          <Link href="/login">
            <Button variant="ghost">Sign in</Button>
          </Link>
          <Link href="/register">
            <Button>Get started</Button>
          </Link>
        </div>
      </header>

      <section className="relative z-10 mx-auto flex max-w-3xl flex-1 flex-col justify-center px-6 pb-24 text-center">
        <p className="text-sm font-medium uppercase tracking-[0.2em] text-amber-500/90">
          Learn deeply on purpose
        </p>
        <h1 className="mt-4 font-serif text-4xl leading-tight text-stone-50 sm:text-5xl">
          AI that asks before it answers — you write the code.
        </h1>
        <p className="mx-auto mt-6 max-w-xl text-lg text-stone-400">
          Pick a course, choose your stack, unlock milestones one at a time, and
          pair with a senior-engineer coach while you build in a real sandbox.
        </p>
        <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
          <Link href="/register">
            <Button className="px-8 py-3 text-base">Start learning</Button>
          </Link>
          <Link href="/login">
            <Button variant="secondary" className="px-8 py-3 text-base">
              I have an account
            </Button>
          </Link>
        </div>

        <ul className="mt-16 grid gap-4 text-left sm:grid-cols-3">
          {[
            {
              title: "Think first",
              body: "Pre-code questions and progressive hints — no solution dumps.",
            },
            {
              title: "Build for real",
              body: "Monaco editor wired to Docker-backed Python sandboxes and tests.",
            },
            {
              title: "Prove it",
              body: "AI review gates understanding before the next milestone unlocks.",
            },
          ].map((item) => (
            <li
              key={item.title}
              className="rounded-xl border border-stone-800 bg-stone-900/40 p-4"
            >
              <p className="font-medium text-stone-200">{item.title}</p>
              <p className="mt-2 text-sm text-stone-500">{item.body}</p>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
