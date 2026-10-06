// Soft hyphens for long Polish words in narrow phone columns ("Psy-chia-tria" instead of
// "Psychiatri / a"). A light syllable heuristic - the browser only breaks where it must.

const VOWELS = new Set("aąeęioóuyAĄEĘIOÓUY");
const DIGRAPHS = new Set(["ch", "cz", "dz", "dź", "dż", "rz", "sz"]);
const SONORANTS = new Set(["r", "l", "ł", "m", "n", "j"]);
const SHY = "­";

function units(word: string): string[] {
  const result: string[] = [];
  for (let index = 0; index < word.length; index += 1) {
    const pair = word.slice(index, index + 2).toLowerCase();
    if (DIGRAPHS.has(pair)) {
      result.push(word.slice(index, index + 2));
      index += 1;
    } else {
      result.push(word[index]);
    }
  }
  return result;
}

const isVowel = (unit: string) => VOWELS.has(unit[0]);
const isLetter = (unit: string) => /\p{L}/u.test(unit);

function hyphenateWord(word: string): string {
  if (word.length < 8) return word;
  const parts = units(word);
  const breaks = new Set<number>(); // break *before* parts[index]
  for (let index = 0; index < parts.length; index += 1) {
    if (!isVowel(parts[index])) continue;
    let next = index + 1;
    while (next < parts.length && isLetter(parts[next]) && !isVowel(parts[next])) next += 1;
    const consonants = next - index - 1;
    if (next >= parts.length || !isVowel(parts[next]) || consonants === 0) continue;
    // V-CV, V-CCV, but VR-CV when the cluster starts with r/l/ł/m/n/j ("Chi-rur-gia", "an-giel-ski").
    const at = consonants >= 2 && SONORANTS.has(parts[index + 1].toLowerCase()) ? index + 2 : index + 1;
    breaks.add(at);
  }
  let out = "";
  let letters = 0;
  const total = parts.reduce((sum, part) => sum + part.length, 0);
  parts.forEach((part, index) => {
    if (breaks.has(index) && letters >= 2 && total - letters >= 3) out += SHY;
    out += part;
    letters += part.length;
  });
  return out;
}

export function hyphenate(text: string): string {
  return text.replace(/\p{L}+/gu, hyphenateWord);
}
