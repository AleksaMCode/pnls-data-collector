// Paris wall-clock helpers. The devices write their Firebase nodes and heartbeats in Paris time.

/** The instant at a Paris wall-clock time, e.g. parisInstant('2026-06-15T10:00:00'). */
export function parisInstant(wallTime) {
  // Paris is UTC+1 or UTC+2. Try both offsets and keep the one that formats back to the same wall time.
  for (const offset of ['+02:00', '+01:00']) {
    const instant = new Date(`${wallTime}${offset}`);
    if (parisWallTime(instant).replace(' ', 'T') === wallTime) {
      return instant;
    }
  }
  throw new Error(`${wallTime} doesn't exist in Paris (a DST gap?)`);
}

/** "YYYY-MM-DD HH:MM:SS" in Paris, the format the collector writes. */
export function parisWallTime(instant) {
  return instant.toLocaleString('sv-SE', { timeZone: 'Europe/Paris' });
}

/** "YYYY-MM-DD" in Paris. */
export function parisDate(instant) {
  return instant.toLocaleDateString('en-CA', { timeZone: 'Europe/Paris' });
}

/** The Firebase node a device writes to on a Paris day. */
export function deviceNode(device, date) {
  return `${device}-${date}`;
}
