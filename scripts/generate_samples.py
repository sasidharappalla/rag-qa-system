"""Generate the sample PDFs used for demos + tests + evaluation.

Run via the console script after install::

    rag-generate-samples

or directly::

    python -m scripts.generate_samples

Binary PDFs aren't committed to git — regenerate on a fresh clone.
"""

from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

SAMPLE_DIR = Path("data/sample")

SAMPLES: dict[str, list[tuple[str, str]]] = {
    "sample1_acme_handbook.pdf": [
        ("Acme Robotics Corporation — Employee Handbook", "Title"),
        (
            "Mission. Acme Robotics builds autonomous warehouse robots that reduce "
            "manual handling injuries and increase throughput. The company was founded "
            "in 2019 in Boston, Massachusetts and now employs 312 people across four "
            "offices.",
            "BodyText",
        ),
        (
            "Benefits. Full-time employees receive medical, dental, and vision insurance "
            "with 90% of premiums paid by Acme. Acme contributes 6% to every employee's "
            "401(k) regardless of personal contribution. Paid parental leave is 16 weeks "
            "for the primary caregiver and 8 weeks for the secondary caregiver.",
            "BodyText",
        ),
        (
            "Remote Work Policy. Engineering and design staff may work remotely up to "
            "three days per week. All staff must be on-site Tuesdays and Thursdays for "
            "collaboration time. International remote work requires written approval from "
            "HR and is capped at 30 days per calendar year.",
            "BodyText",
        ),
        (
            "Code of Conduct. Acme prohibits harassment and discrimination on the basis "
            "of race, gender, sexual orientation, religion, disability, or age. "
            "Violations should be reported to the Ethics Hotline at ext. 4500 or via the "
            "confidential web form on the internal portal. Retaliation against "
            "good-faith reporters is itself a terminable offense.",
            "BodyText",
        ),
        (
            "Expense Reimbursement. Business expenses must be submitted within 30 days "
            "via the Acme Expense portal. Meals during overnight travel are reimbursed "
            "up to 75 US dollars per day. Rideshare and taxi fares are reimbursed at "
            "actual cost with a receipt.",
            "BodyText",
        ),
    ],
    "sample2_vector_db_primer.pdf": [
        ("A Short Primer on Vector Databases", "Title"),
        (
            "What is a vector database? A vector database is a specialized data store "
            "that indexes high-dimensional embedding vectors to support similarity "
            "search. Instead of exact-match queries, users ask for the k nearest "
            "vectors to a query vector under a distance metric such as cosine or L2.",
            "BodyText",
        ),
        (
            "Indexing strategies. Modern vector stores use approximate-nearest-neighbor "
            "indexes such as HNSW (Hierarchical Navigable Small World) or IVF-PQ "
            "(Inverted File with Product Quantization). HNSW trades memory for fast "
            "low-latency lookups; IVF-PQ trades recall for a much smaller memory "
            "footprint and is preferred for billion-scale collections.",
            "BodyText",
        ),
        (
            "Use cases. The most common use case is retrieval-augmented generation "
            "(RAG), where relevant document chunks are retrieved by vector similarity "
            "and injected into a language model prompt. Other uses include "
            "recommendation systems, deduplication, and semantic image search.",
            "BodyText",
        ),
        (
            "Choosing a store. For local development, Chroma and FAISS are the most "
            "popular options because they run in-process with no network dependency. "
            "For production, managed services like Pinecone, Weaviate Cloud, and "
            "pgvector on PostgreSQL are common. The query API is broadly similar "
            "across all of them — the main differences are operational.",
            "BodyText",
        ),
    ],
    "sample3_quarterly_review.pdf": [
        ("Acme Robotics — Q3 2026 Business Review (Excerpt)", "Title"),
        (
            "Revenue. Q3 revenue was 42.1 million US dollars, up 28 percent year over "
            "year. Recurring software revenue contributed 11.3 million, which is the "
            "first time software has crossed the 10 million quarterly mark.",
            "BodyText",
        ),
        (
            "Customer metrics. Net new logos in Q3 totaled 14, bringing the active "
            "customer count to 137. Gross revenue retention was 96 percent and net "
            "revenue retention was 118 percent, driven primarily by expansion at the "
            "top ten accounts.",
            "BodyText",
        ),
        (
            "Operational highlights. The Gen-4 warehouse robot shipped to its first "
            "three customers in September. Field reliability across the installed "
            "fleet exceeded 99.2 percent uptime. The engineering team opened a new "
            "office in Austin, Texas, bringing total headcount to 312.",
            "BodyText",
        ),
        (
            "Outlook. Q4 pipeline coverage stands at 2.7 times target, with the "
            "largest open opportunity being a 7 million dollar expansion at a "
            "top-three retail customer. Management reaffirms full-year guidance of "
            "160 to 170 million dollars in revenue.",
            "BodyText",
        ),
    ],
}


def _build_pdf(path: Path, blocks: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(path), pagesize=LETTER, title=path.stem)
    styles = getSampleStyleSheet()
    flow = []
    for text, style_name in blocks:
        flow.append(Paragraph(text, styles[style_name]))
        flow.append(Spacer(1, 12))
    doc.build(flow)


def generate(target_dir: Path = SAMPLE_DIR) -> list[Path]:
    """Create all sample PDFs under ``target_dir``. Returns the list of paths written."""
    written: list[Path] = []
    for name, blocks in SAMPLES.items():
        out = target_dir / name
        _build_pdf(out, blocks)
        written.append(out)
    return written


def main() -> int:
    out = generate()
    for p in out:
        print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
