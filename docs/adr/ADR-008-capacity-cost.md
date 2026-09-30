# ADR-008: Capacity and cost (nonprofit budget)

**Facts to know:**

- F-SKUs are **smoothed**: background jobs over 24 hours, interactive over about 5 minutes.
- **Bursting** lets short spikes exceed the SKU.
- Sustained overuse leads to **throttling**: interactive delay, then interactive rejection, then background rejection.
- The **Capacity Metrics app** shows CU consumption per item and operation.
- The capacity can be **paused**, and reservations are cheaper than pay-as-you-go.

## Decision

1. **Start with one capacity**, sized from the pilots' Capacity Metrics data rather than guessed. Review monthly.
2. **Isolate production reporting when budget allows**, which moves us from Microsoft's deployment Pattern 2 to *Pattern 3, per-environment capacities*. A PROD capacity separate from DEV/TEST means a runaway notebook can't throttle the CIO's dashboard. Until then, schedule heavy ETL and maintenance off-hours (05:00 load, Sunday 03:00 maintenance).
3. **Engineer for efficiency:**
   - Incremental loads (watermarks, hash-based MERGE)
   - V-Order + OPTIMIZE
   - Direct Lake instead of Import refreshes
   - Dataflow Gen2 only where the business owns the logic (ADR-002)
4. **Pause DEV capacity** outside hours if it's a separate pay-as-you-go SKU.

**Detailed sizing:** see the [capacity sizing reference](../05-capacity-sizing.md) for SKU prices, the F32 vs. F64 licensing break-even, per-environment recommendations (reserved F32 PROD + pausable PAYG F4 DEV/TEST), and scale-up/down triggers.

**Say it in 30 seconds:** "I size from evidence, not guesswork. I keep heavy jobs away from business hours, and every design choice, from incremental loads to Direct Lake, is also a cost choice."
