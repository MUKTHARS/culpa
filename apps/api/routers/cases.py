from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.auth.deps import require_analyst
from core.database import get_db
from schemas import ApproveRequest, SimulateDispute
from services import case_service

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("")
def list_cases(status: str | None = None, db: Session = Depends(get_db), _: str = Depends(require_analyst)):
    return case_service.list_cases(db, status=status)


@router.get("/review-queue")
def review_queue(db: Session = Depends(get_db), _: str = Depends(require_analyst)):
    return {"case_ids": case_service.review_queue(db)}


@router.get("/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_db), _: str = Depends(require_analyst)):
    return case_service.case_detail(db, case_id)


@router.post("/simulate")
def simulate(body: SimulateDispute, db: Session = Depends(get_db), actor: str = Depends(require_analyst)):
    case = case_service.create_simulated(db, order_id=body.order_id, reason=body.reason, claim_text=body.claim_text,
                                         actor=f"simulator:{actor}")
    db.commit()
    return case_service.case_row(case)


@router.post("/{case_id}/reanalyze")
def reanalyze(case_id: str, db: Session = Depends(get_db), actor: str = Depends(require_analyst)):
    case = case_service.reanalyze(db, case_id, actor=actor)
    db.commit()
    return case_service.case_row(case)


@router.post("/{case_id}/approve")
def approve(case_id: str, body: ApproveRequest, db: Session = Depends(get_db), actor: str = Depends(require_analyst)):
    st = case_service.approve(db, case_id, actor=actor, action=body.action, amount=body.amount, note=body.note)
    db.commit()
    return {"settlement_id": st.id, "action": st.action, "status": st.status, "amount": st.amount}
