import { useEffect, useState } from "react";

const QUERY = "(max-width: 639px)";

/** True on phone-sized screens, where views switch to their compact, fit-the-screen layout. */
export function useCompact(): boolean {
  const [compact, setCompact] = useState(() => typeof window !== "undefined" && window.matchMedia(QUERY).matches);
  useEffect(() => {
    const media = window.matchMedia(QUERY);
    const update = () => setCompact(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return compact;
}
