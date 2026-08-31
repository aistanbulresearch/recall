/**
 * The demo page: a white screen, a sentence, and a conversation.
 *
 * A juror should not have to navigate anything to understand what Recall is or
 * what it did. They ask, and the answer arrives with its numbers attached.
 *
 * The important honesty property: nothing is generated when a question is
 * asked. Every answer is composed at build time from the committed artifacts
 * of one completed run, and a question the artifacts cannot support is refused
 * rather than improvised. That is the same rule the product itself follows,
 * demonstrated by the page that describes it.
 */

import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';

import './demo.css';

import { ANSWERS, byId, match } from './answers';

interface Turn {
  id: number;
  from: 'you' | 'recall';
  content: ReactNode;
  more?: { href: string; label: string };
}

/** The five a jury reaches for first: what, why, what ran, what broke, what is new. */
const OPENER_IDS = ['about', 'why', 'run', 'failure', 'innovation'];
const OPENERS = OPENER_IDS.map((id) => ANSWERS.find((answer) => answer.id === id)!).filter(
  Boolean,
);

export function DemoPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState('');
  const [asked, setAsked] = useState<Set<string>>(new Set());
  const endRef = useRef<HTMLDivElement | null>(null);
  const nextId = useRef(0);

  useEffect(() => {
    if (turns.length > 0) {
      endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
  }, [turns]);

  function ask(question: string, answerId?: string) {
    // A clicked suggestion knows exactly which answer it is; only typed text
    // goes through the matcher.
    const answer = answerId ? byId(answerId) : match(question);
    const id = nextId.current++;
    const reply: Turn = answer
      ? { id: id + 1000, from: 'recall', content: answer.body, more: answer.more }
      : {
          id: id + 1000,
          from: 'recall',
          content: (
            <>
              <p>
                I can only answer from this run’s stored artifacts, and I don’t have one that
                covers that. I would rather say so than improvise — which is the same rule the
                system itself follows.
              </p>
              <p className="quiet">Here is everything the artifacts do cover:</p>
              <p className="codes">
                {ANSWERS.slice(0, 8).map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    className="inline-chip"
                    onClick={() => ask(option.label, option.id)}
                  >
                    {option.label}
                  </button>
                ))}
              </p>
            </>
          ),
        };
    if (answer) {
      setAsked((previous) => new Set(previous).add(answer.id));
    }
    setTurns((previous) => [
      ...previous,
      { id, from: 'you', content: question },
      reply,
    ]);
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const question = draft.trim();
    if (question.length === 0) {
      return;
    }
    setDraft('');
    ask(question);
  }

  const remaining = ANSWERS.filter((answer) => !asked.has(answer.id));
  const suggestions = (turns.length === 0 ? OPENERS : remaining).slice(0, 5);

  return (
    <div className="demo">
      <div className="demo-wrap">
        <header className="demo-hero">
          <h1>Welcome to the Recall demo.</h1>
          <p className="lede">
            Recall is a zero-trust institutional agent fleet that keeps watching closed genomic
            cases after the appointment ends — and never lets a model become the scientific
            authority.
          </p>
          <p className="lede">
            Here you can interrogate a real run: 456 cases, six hours, unattended, on Google
            Cloud. Ask anything below and the answer comes back with the numbers it stands on.
          </p>
        </header>

        <div className="thread" role="log" aria-live="polite">
          {turns.map((turn) =>
            turn.from === 'you' ? (
              <div className="turn you" key={turn.id}>
                <span className="who">you</span>
                <div className="bubble">{turn.content}</div>
              </div>
            ) : (
              <div className="turn recall" key={turn.id}>
                <span className="who">recall</span>
                <div className="bubble">
                  {turn.content}
                  {turn.more ? (
                    <a className="more" href={turn.more.href}>
                      {turn.more.label} →
                    </a>
                  ) : null}
                </div>
              </div>
            ),
          )}
          <div ref={endRef} />
        </div>

        {suggestions.length > 0 ? (
          <div className="suggestions">
            {turns.length === 0 ? <span className="try">Try asking</span> : null}
            {suggestions.map((answer) => (
              <button
                key={answer.id}
                type="button"
                className="chip"
                onClick={() => ask(answer.label, answer.id)}
              >
                {answer.label}
              </button>
            ))}
          </div>
        ) : null}

        <form className="composer" onSubmit={submit}>
          <input
            type="text"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Ask about the run, the failures, the evidence, the limits…"
            aria-label="Ask about the run"
          />
          <button type="submit">Ask</button>
        </form>

        <p className="ground">
          Answers are composed from the committed artifacts of one completed execution
          (generation 27). Nothing is generated when you press Ask, and nothing is fetched while
          you read. A question the artifacts cannot support is refused rather than improvised.
        </p>

        <footer className="demo-foot">
          <a href="#/run">The run, case by case</a>
          <a href="#/story">The full story and architecture</a>
          <a href="#/demo/">The evidence surface</a>
          <span className="frame">
            NON-CLINICAL RESEARCH PROTOTYPE · SYNTHETIC RECORDS · CAPTURED PUBLIC EVIDENCE
          </span>
        </footer>
      </div>
    </div>
  );
}
