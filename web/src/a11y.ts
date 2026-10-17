// Small helpers for motion and focus preferences.

export const prefersReducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Move focus to a field on a new turn, but only where a keyboard is likely (a fine pointer), so a
 *  phone's on-screen keyboard does not pop up by itself. */
export function focusOnTurn(node: HTMLElement): void {
  if (matchMedia("(pointer: fine)").matches) node.focus();
}
