from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.auth.deps import require_analyst
from core.database import get_db
from core.errors import NotFound
from services import audit_service, outbox_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/stats")
def stats(db: Session = Depends(get_db), _: str = Depends(require_analyst)):
    ok, broken_at = audit_service.verify_chain(db)
    return {**outbox_service.stats(db), "audit_chain_ok": ok, "audit_chain_broken_at": broken_at}


@router.get("/dead")
def dead(db: Session = Depends(get_db), _: str = Depends(require_analyst)):
    return outbox_service.dead_letters(db)


@router.post("/dead/{dead_id}/replay")
def replay(dead_id: int, db: Session = Depends(get_db), actor: str = Depends(require_analyst)):
    row = outbox_service.replay_dead(db, dead_id)
    if row is None:
        raise NotFound("dead letter not found or already replayed")
    audit_service.append(db, actor=actor, action="job.replayed", data={"dead_letter_id": dead_id, "outbox_id": row.id})
    db.commit()
    return {"outbox_id": row.id}
