"""Run the evaluation suite and persist results."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.core.evaluation import load_dataset, run_evaluation
from app.llm.base import LLMProvider, get_llm_provider
from app.observability import get_logger
from app.schemas.evaluation import EvalReport

router = APIRouter(prefix="/evaluate", tags=["evaluation"])
logger = get_logger(__name__)

DEFAULT_DATASET = Path("eval/dataset.json")
RESULTS_DIR = Path("eval/results")


@router.get("", response_model=EvalReport, summary="Run the eval suite over eval/dataset.json")
async def run_eval(
    k: int = 4,
    provider: LLMProvider = Depends(get_llm_provider),
) -> EvalReport:
    if not DEFAULT_DATASET.exists():
        raise HTTPException(status_code=404, detail=f"Eval dataset not found at {DEFAULT_DATASET}")

    dataset = load_dataset(DEFAULT_DATASET)
    if not dataset:
        raise HTTPException(status_code=400, detail="Eval dataset is empty")

    report = await run_evaluation(dataset, provider=provider, k=k)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_path = RESULTS_DIR / f"{stamp}.json"
    out_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    logger.info(
        "eval.complete",
        extra={
            "dataset_size": report.dataset_size,
            "mean_faithfulness": report.mean_faithfulness,
            "mean_retrieval_precision": report.mean_retrieval_precision,
            "results_path": str(out_path),
        },
    )
    return report
