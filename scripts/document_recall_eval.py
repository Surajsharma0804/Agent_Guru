"""How well document search finds the passage that answers a question, on the real embedder.

Usage:
    python scripts/document_recall_eval.py [--sweep]

Writes the documents below to a temporary folder, adds them to a temporary
DocumentStore (the owner's documents.db is not touched) and asks each
question through DocumentStore.search. For every question it reports the
passages that came back against the document that should have answered:

    found    a passage from the expected document came back
    missed   none did
    leaked   a passage from any other document came back

Questions with no expected document are about things none of the
documents cover, and should bring nothing.

--sweep prints the same counts for a range of cutoffs, which is how
RELEVANT_PASSAGE in platform/features/documents.py was chosen.

Exits 1 if any question misses or leaks at the current cutoff.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DOCUMENTS: dict[str, str] = {
    "lease.txt": """RESIDENTIAL LEASE AGREEMENT

This agreement is made between the landlord, Mr. Anil Deshpande, and the tenant for the flat at
B-204, Green Meadows, Baner, Pune.

1. Rent. The monthly rent is Rs. 22,000, payable on or before the 5th of each month by bank
transfer. A late fee of Rs. 500 applies after the 10th.

2. Security deposit. The tenant pays a refundable deposit of Rs. 66,000. It is returned within
30 days of the tenant vacating, less the cost of any damage beyond normal wear and tear.

3. Notice period. Either party may end this agreement by giving two months' written notice.
The tenant may not leave during the first six months (lock-in period).

4. Pets. Small pets such as cats and dogs are allowed with the landlord's written consent.
The tenant is responsible for any damage caused by pets.

5. Maintenance. The tenant pays the society maintenance charge of Rs. 2,500 per month.
Major repairs to plumbing and electrical wiring are the landlord's responsibility.
""",
    "washing_machine_warranty.txt": """WARRANTY CARD - FRONT LOAD WASHING MACHINE, MODEL WM8-1400

Thank you for your purchase. This product is covered by a warranty of 2 years on the whole
machine and 10 years on the motor, counted from the date on the invoice.

What is covered: defects in materials and workmanship under normal household use.

What is not covered: damage from voltage fluctuations without a stabilizer, rust on the body,
damage from moving the machine, plastic parts, and use for commercial laundry.

How to claim: call the service centre on 1800-200-5566 or register the complaint on the website.
Keep the invoice and this card; a claim without the invoice is not accepted.

Care: clean the drain filter once a month and run an empty hot wash with descaler every
three months to keep the drum free of limescale.
""",
    "goa_itinerary.md": """# Goa trip, 14 to 18 November

## Travel
Flight 6E 523 from Pune to Goa (Mopa) departs 07:40 on 14 November, arrives 08:50.
Return flight 6E 524 departs Goa 19:30 on 18 November.

## Stay
Hotel: Casa Palmeira, Candolim. Check-in from 14:00, check-out by 11:00.
Booking reference CPX-88412. Breakfast is included.

## Plans
15 November: Old Goa churches in the morning, Panjim market in the afternoon.
16 November: Dudhsagar falls day trip, jeep booked for 07:00 pickup from the hotel.
17 November: beach day at Palolem, dinner at Martin's Corner.
""",
    "health_insurance.txt": """HEALTH INSURANCE POLICY SCHEDULE

Policy number: HI-4471-2209. Sum insured: Rs. 5,00,000 per year, family floater covering the
policyholder, spouse and two children.

Waiting periods: 30 days for any illness from the policy start, except accidents. Two years for
named conditions such as cataract, hernia and joint replacement. Three years for pre-existing
diseases declared at the time of buying the policy.

Cashless treatment is available at network hospitals. Inform the insurer within 24 hours of an
emergency admission and 48 hours before a planned one.

Room rent is capped at 1% of the sum insured per day. A co-payment of 10% applies to claims
for members above 60 years of age.
""",
    "dal_recipe.txt": """Dal tadka for four

Wash one cup of toor dal and pressure cook it with three cups of water, turmeric and salt
for four whistles.

For the tadka, heat two tablespoons of ghee, add cumin seeds, then chopped garlic, dried red
chillies and a pinch of hing. Add one chopped onion and cook until golden, then two chopped
tomatoes until soft.

Pour the tadka into the dal, simmer for five minutes, and finish with chopped coriander and a
squeeze of lemon. Serve with rice or jeera rice.
""",
}

#: (question, the document that answers it, or None when none does).
CASES: list[tuple[str, str | None]] = [
    ("How much notice do I have to give my landlord", "lease.txt"),
    ("Can I keep a dog in my flat", "lease.txt"),
    ("When is the rent due", "lease.txt"),
    ("When will I get my deposit back", "lease.txt"),
    ("Who pays for plumbing repairs", "lease.txt"),
    ("Is the washing machine motor still under warranty", "washing_machine_warranty.txt"),
    ("What is the service centre number for the washing machine", "washing_machine_warranty.txt"),
    ("How often should I clean the drain filter", "washing_machine_warranty.txt"),
    ("What time is my flight to Goa", "goa_itinerary.md"),
    ("What is the hotel booking reference", "goa_itinerary.md"),
    ("When is the Dudhsagar pickup", "goa_itinerary.md"),
    ("What is the waiting period for cataract surgery", "health_insurance.txt"),
    ("How soon do I have to tell the insurer about a hospital admission", "health_insurance.txt"),
    ("Is there a limit on hospital room rent", "health_insurance.txt"),
    ("How many whistles for the dal", "dal_recipe.txt"),
    ("What goes into the tadka", "dal_recipe.txt"),
    # none of the documents answers these
    ("Who won the cricket match yesterday", None),
    ("What is the capital of Australia", None),
    ("Tell me a joke", None),
    ("How do I reset my wifi router", None),
    ("What should I gift my sister", None),
    ("Set a timer for ten minutes", None),
    ("How does a black hole form", None),
    ("What is the weather in Pune today", None),
]


def _counts(results: list[tuple[str | None, list[tuple[str, float]]]], cutoff: float) -> tuple[int, int, int]:
    right = missed = leaked = 0
    for want, hits in results:
        got = {name for name, score in hits if score >= cutoff}
        miss = want is not None and want not in got
        leak = bool(got - {want})
        missed += miss
        leaked += leak
        right += not miss and not leak
    return right, missed, leaked


async def run(sweep: bool) -> int:
    from Agent_Guru.platform.features.documents import RELEVANT_PASSAGE, DocumentStore

    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        store = DocumentStore(root / "documents.db")
        for name, text in DOCUMENTS.items():
            (root / name).write_text(text, encoding="utf-8")
            await store.add(root / name)
        results = []
        for question, want in CASES:
            hits = [(p.document, p.score) for p in await store.search(question, limit=3, min_score=-1.0)]
            results.append((want, hits))
            got = {name for name, score in hits if score >= RELEVANT_PASSAGE}
            ok = (want is None or want in got) and not got - {want}
            top = ", ".join(f"{name} {score:.2f}" for name, score in hits[:2])
            print(f"{'ok    ' if ok else 'WRONG '}{question!r:70} want={want} top: {top}")

    right, missed, leaked = _counts(results, RELEVANT_PASSAGE)
    print(f"\ncutoff {RELEVANT_PASSAGE}: {right}/{len(CASES)} right, {missed} missed, {leaked} leaked")
    if sweep:
        for step in range(15, 56, 5):
            cutoff = step / 100
            print("  cutoff {:.2f}: {}/{} right, {} missed, {} leaked".format(cutoff, *_counts(results, cutoff)[:1], len(CASES), *_counts(results, cutoff)[1:]))
    return 0 if right == len(CASES) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--sweep", action="store_true", help="also report a range of cutoffs")
    sys.exit(asyncio.run(run(parser.parse_args().sweep)))
