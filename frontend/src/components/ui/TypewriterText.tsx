import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// 8 chars per 20ms ≈ 400 chars/sec. A 1000-char reply takes ~2.5s — fast
// enough to feel live, slow enough to see it happening.
const CHARS_PER_TICK = 8;
const TICK_MS = 20;

type TypewriterTextProps = {
  text: string;
};

/**
 * Reveals `text` character-by-character on mount, then renders the full
 * markdown. Respects prefers-reduced-motion by snapping to the final value.
 */
export function TypewriterText({ text }: TypewriterTextProps) {
  const reduced = prefersReducedMotion();
  const [shown, setShown] = useState(reduced ? text.length : 0);

  useEffect(() => {
    if (reduced) {
      return;
    }
    const id = setInterval(() => {
      setShown((prev) => {
        const next = prev + CHARS_PER_TICK;
        if (next >= text.length) {
          clearInterval(id);
          return text.length;
        }
        return next;
      });
    }, TICK_MS);
    return () => clearInterval(id);
  // Run only on mount — text is captured at creation time via closure.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]}>
      {text.slice(0, shown)}
    </ReactMarkdown>
  );
}
