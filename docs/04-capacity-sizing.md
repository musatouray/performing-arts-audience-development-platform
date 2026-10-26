# Capacity sizing reference: Fabric F-SKUs for a mid-size nonprofit

**Context:** companion to [ADR-008: Capacity and cost](adr/ADR-008-capacity-cost.md) and [architecture §9: deployment pattern](02-architecture.md#9-microsoft-fabric-deployment-pattern). The mock platform runs on a Fabric Trial capacity; this doc covers what a real organization of this size would run.
**Status:** reference only. The target organization's actual capacity is unknown, so treat this as an informed default to validate against real Capacity Metrics data.
**Pricing:** approximate US list prices as of 2026. Microsoft changes SKU and Pro prices periodically, so verify on the Azure/Fabric pricing page and check nonprofit offers before quoting numbers. This isn't financial advice.

---

## 1. Recommendation in one line

Run a **dedicated F32 on a 1-year reservation for production**, plus a **small pay-as-you-go (PAYG) F4 for dev/test that is paused outside working hours**. Move PROD to **F64** only when the licensing math or measured usage says so.

This is Microsoft deployment **Pattern 3, per-environment capacities**: the planned next step after this platform's Pattern 2 (see [architecture §9](02-architecture.md#9-microsoft-fabric-deployment-pattern)).

---

## 2. The deciding fact: F64 is a licensing threshold, not just a size

| Capacity | Who needs a paid Power BI license |
|---|---|
| **F2–F32** | Everyone who **views** reports needs Power BI Pro (or PPU). |
| **F64 and above** | Only **authors** need Pro. Viewers can use a free license. |

So choosing F64 is mostly about **viewer count × Pro price**, not compute.

---

## 3. Price reference (approximate, US, 2026)

| SKU | CUs | Pay-as-you-go / month | ~1-yr reserved / month (≈40% off) |
|---|---|---|---|
| F2 | 2 | ~$262 | ~$156 |
| F4 | 4 | ~$525 | ~$310 |
| F8 | 8 | ~$1,050 | ~$620 |
| F16 | 16 | ~$2,100 | ~$1,240 |
| F32 | 32 | ~$4,200 | ~$2,500 |
| F64 | 64 | ~$8,400 | ~$5,000–5,300 |

F4 and F16 are scaled linearly from the published SKUs. Pay-as-you-go prices scale linearly with CUs.

**Power BI Pro:** about $14 per user per month at commercial list price. **Nonprofit pricing is heavily discounted**, and **Microsoft 365 E5 already includes Pro**.

---

## 4. Break-even worksheet: F32 + Pro vs. F64

```
Break-even viewers = (F64 reserved − F32 reserved) ÷ Pro price per user per month
                   ≈ ($5,000–5,300 − $2,500) ÷ $14
                   ≈ 180–200 Pro-licensed viewers
```

| If... | Then... |
|---|---|
| Report consumers ≤ ~180 (commercial Pro price) | F32 + Pro is cheaper |
| Report consumers ≥ ~200, or you want license-free sharing with all staff or the board | F64 is cheaper, or simpler |
| Staff are on **nonprofit Pro** pricing | The break-even rises a lot, so F32 + Pro stays cheaper much longer |
| Staff are on **M365 E5** | Viewers are already licensed, so F64's free-viewer benefit is worth little and compute alone decides |

To fill it in with real numbers: *(F64 reserved − F32 reserved) ÷ (actual Pro price per user after nonprofit discounts) = the viewer count where F64 wins.*

---

## 5. Sizing for this organization

Assumed profile: a nonprofit, a four-person BI team, probably a few hundred staff, modest data volumes (ticketing, donors, education programs), and highly **seasonal** peaks (season launch, subscription renewals, the gala).

| Environment | Recommendation | Why |
|---|---|---|
| **PROD** | **F32, 1-yr reservation** | Handles daily ETL and report load comfortably. Direct Lake size limits at F32 are far above this data's table sizes. Isolated, so dev work can't throttle leadership dashboards. |
| **DEV/TEST** | **F4, PAYG, paused nights and weekends** | Only PAYG can be paused; reservations are billed 24/7. Running about 50 hours a week costs roughly ⅓ of always-on. |
| **Seasonal peaks** | **Temporarily scale PROD up on PAYG** | Reservations cover the baseline CUs. Extra CUs during renewal week or the gala are billed PAYG only for those days, then you scale back. |
| **Spark-heavy spikes** | Consider **Spark Autoscale Billing** (pay-per-use Spark outside the capacity) | Keeps large backfills from using up the reserved capacity's compute. |

---

## 6. When to scale up or down

**Scale PROD from F32 to F64 when any of these is true:**

- Pro-licensed viewers pass the break-even (§4).
- You want license-free sharing with all staff or board members.
- The **Capacity Metrics app** shows sustained interactive delay or rejection (throttling) at peak.

**Scale down when:**

- Average usage stays below about **40% for a full season**.

**Don't size for the peak.** Smoothing and bursting absorb short spikes (background jobs are smoothed over 24 hours, interactive over about 5 minutes). PAYG can cover planned peaks.

**Always size from evidence.** The two partner pilots already have Capacity Metrics history.

---

## 7. Cost-optimization levers (engineering choices that are also cost choices)

| Lever | Effect |
|---|---|
| Reserve only the **baseline**; cover peaks with PAYG | You don't pay reserved rates for idle headroom |
| Pause DEV/TEST when not in use (PAYG only) | About 60–70% saving on non-prod |
| Heavy ETL and maintenance **off-hours** (05:00 load, Sunday 03:00 OPTIMIZE/VACUUM) | Avoids competing with daytime interactive queries, so less throttling at the same size |
| **Incremental** loads (watermarks, hash-based MERGE) | Fewer CUs per run |
| **Direct Lake** instead of Import | No scheduled refresh CU cost |
| V-Order + OPTIMIZE | Cheaper reads for Direct Lake and the SQL endpoint |
| Use Dataflow Gen2 only where the business owns the logic | Dataflows use more CUs per GB than a Copy job or notebook |
| Separate PROD capacity | Isolation means you don't need a bigger shared SKU just to protect reports |

---

## 8. Questions to ask before sizing

1. "What capacity are the pilots running on, and what did the Capacity Metrics app show at peak?"
2. "How many people consume reports, and are they licensed through M365 E5, nonprofit Pro, or not yet?"
3. "Is there a separate dev/test capacity today, or does it share with production?"
4. "Who owns the Fabric budget, and is there a preference for reserved vs. pay-as-you-go?"

**Why these first:** capacity is a **cost and licensing decision**, not just a technical one. That matters for a budget-conscious nonprofit.

---

## 9. Summary

> [!NOTE]
> *"For an organization this size I'd run production on a reserved F32 and dev/test on a small pay-as-you-go F4 that's paused at night, then scale production up on pay-as-you-go for peaks like renewal week. F64 is really a licensing decision: above roughly 200 Pro-licensed viewers it's cheaper, because viewers no longer need Pro. Nonprofit Pro pricing or E5 licensing pushes that break-even much higher, so I'd size from the pilots' Capacity Metrics data and the actual license mix, not guess."*

---

## Sources

- [Microsoft Fabric deployment patterns (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/architecture/data-guide/technology-choices/fabric-deployment-patterns)
- [Fabric Pricing 2026: Capacity SKU Costs From F2 to F64 (AlphaVima)](https://alphavima.com/blog/microsoft-fabric-pricing/)
- [Power BI Pricing & Licensing Guide 2026](https://powerbiconsulting.com/blog/power-bi-pricing-licensing-guide-2026)
- [Microsoft Fabric Pricing Guide (Dynamics Square)](https://www.dynamicssquare.com/blog/microsoft-fabric-pricing/)
- [Microsoft Fabric Pricing Guide 2026: F-SKUs & Cost Optimization](https://dattasable.com/blog/microsoft-fabric-pricing-guide-2026)
