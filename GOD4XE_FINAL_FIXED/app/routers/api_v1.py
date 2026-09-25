import re
import secrets
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, UploadFile, File
from pydantic import BaseModel, EmailStr, Field

from app.services import users_auth as user_service
from app.services import tournaments as tournament_service
from app.services import wallet as wallet_service
from app.services import leaderboards as leaderboard_service
from app.services import social as social_service
from app.services import content_features
from app.services import settings as settings_service
from app.config import GOOGLE_CLIENT_ID, UPLOAD_DIR, WITHDRAWALS_ENABLED

router = APIRouter(prefix="/api/v1")

def get_auth_user(request: Request) -> dict:
    return user_service.get_current_user(request)

# --------------------------------------------------------------------------
# SCHEMAS
# --------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    username: str
    email: Optional[str] = None
    phone: Optional[str] = None
    password: str
    referral_code: Optional[str] = None

class LoginRequest(BaseModel):
    identity: str
    password: str

class GoogleAuthRequest(BaseModel):
    id_token: str
    referral_code: Optional[str] = None

class OTPRequest(BaseModel):
    phone: str

class OTPVerifyRequest(BaseModel):
    phone: str
    otp: str

class UpdateProfileRequest(BaseModel):
    username: Optional[str] = None
    display_name: Optional[str] = None
    ff_uid: Optional[str] = None
    ff_ign: Optional[str] = None

class UpdateFreeFireRequest(BaseModel):
    ff_uid: str
    ff_ign: str

class UpdateAvatarRequest(BaseModel):
    avatar_url: str

class JoinTournamentRequest(BaseModel):
    ff_uid: str
    ff_ign: str

class ParticipantCredentialsRequest(BaseModel):
    ff_uid: str
    ff_ign: str

class DisputeRequest(BaseModel):
    dispute_type: str = Field(..., alias="reason")
    description: str
    proof_url: Optional[str] = None

    class Config:
        allow_population_by_field_name = True

class DepositRequestSchema(BaseModel):
    amount: int
    utr_reference: str
    payment_proof_url: Optional[str] = None

class WithdrawalRequestSchema(BaseModel):
    amount: int
    upi_id: str

class RedeemCodeRequest(BaseModel):
    code: str

class SupportTicketRequest(BaseModel):
    subject: str
    category: str = "TOURNAMENT"
    priority: str = "NORMAL"
    message: str

class SupportReplyRequest(BaseModel):
    message: str


# --------------------------------------------------------------------------
# 1. AUTHENTICATION
# --------------------------------------------------------------------------
@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def api_register(req: RegisterRequest):
    try:
        data = user_service.register_user(
            username=req.username,
            email=req.email,
            phone=req.phone,
            password=req.password,
            referral_code=req.referral_code
        )
        return {"success": True, "message": "Registration successful", **data}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/auth/login")
async def api_login(req: LoginRequest, request: Request):
    ip = request.client.host if request.client else "127.0.0.1"
    user, token_or_err = user_service.authenticate_user(req.identity, req.password, ip_address=ip)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=token_or_err)
    return {"success": True, "user": user, "token": token_or_err}

@router.get("/auth/config")
async def api_auth_config():
    all_settings = settings_service.get_all_settings()
    configured_client_id = GOOGLE_CLIENT_ID or all_settings.get("google_client_id", "")
    return {
        "success": True,
        "google_client_id": configured_client_id
    }

@router.post("/auth/google")
async def api_google_auth(req: GoogleAuthRequest):
    try:
        user, token = user_service.authenticate_google_user(req.id_token, referral_code=req.referral_code)
        return {"success": True, "user": user, "token": token}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/auth/otp/request")
async def api_otp_request(req: OTPRequest):
    try:
        res = user_service.request_phone_otp(req.phone)
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/auth/otp/verify")
async def api_otp_verify(req: OTPVerifyRequest):
    try:
        user, token = user_service.verify_phone_otp(req.phone, req.otp)
        return {"success": True, "user": user, "token": token}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/auth/me")
async def api_me(user: dict = Depends(get_auth_user)):
    return {"success": True, "user": user}

@router.post("/auth/logout")
async def api_logout(user: dict = Depends(get_auth_user)):
    return {"success": True, "message": "Logged out successfully"}


# --------------------------------------------------------------------------
# 2. USER PROFILE & STATS
# --------------------------------------------------------------------------
@router.get("/users/profile")
async def api_get_profile(user: dict = Depends(get_auth_user)):
    full_user = user_service.get_user_by_id(user["id"])
    return {"success": True, "profile": full_user or user}

@router.put("/users/profile")
async def api_update_profile(req: UpdateProfileRequest, user: dict = Depends(get_auth_user)):
    try:
        updated = user_service.update_user_profile(
            user_id=user["id"],
            username=req.username,
            display_name=req.display_name,
            ff_uid=req.ff_uid,
            ff_ign=req.ff_ign
        )
        return {"success": True, "profile": updated, "message": "Profile updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.put("/users/freefire")
async def api_update_freefire(req: UpdateFreeFireRequest, user: dict = Depends(get_auth_user)):
    try:
        updated = user_service.update_user_freefire(user["id"], req.ff_uid, req.ff_ign)
        return {"success": True, "profile": updated, "message": "Free Fire credentials saved"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/users/check-username")
async def api_check_username(username: str = Query(...), user: dict = Depends(get_auth_user)):
    valid, msg = user_service.check_username_availability(username, exclude_user_id=user["id"])
    return {"success": True, "available": valid, "message": msg}

@router.post("/users/avatar")
async def api_upload_avatar(file: UploadFile = File(...), user: dict = Depends(get_auth_user)):
    contents = await file.read()
    try:
        updated = user_service.upload_user_avatar(
            user_id=user["id"],
            file_bytes=contents,
            filename=file.filename,
            content_type=file.content_type
        )
        return {"success": True, "profile": updated, "message": "Profile avatar uploaded successfully!"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/users/avatar")
async def api_remove_avatar(user: dict = Depends(get_auth_user)):
    updated = user_service.remove_user_avatar(user["id"])
    return {"success": True, "profile": updated, "message": "Profile avatar removed."}

@router.get("/users/{user_id}/public-profile")
async def api_get_public_profile(user_id: int):
    public_prof = user_service.get_public_profile(user_id)
    if not public_prof:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player profile not found.")
    return {"success": True, "player": public_prof}

@router.get("/users/{user_id}/achievements")
async def api_get_achievements(user_id: int):
    achs = user_service.get_user_achievements(user_id)
    return {"success": True, "achievements": achs}


# --------------------------------------------------------------------------
# 3. TOURNAMENT CATEGORIES & GUNS
# --------------------------------------------------------------------------
@router.get("/tournaments/categories")
async def api_list_categories():
    cats = tournament_service.list_categories(only_active=True)
    return {"success": True, "categories": cats}

@router.get("/tournaments/guns")
async def api_list_guns():
    guns = tournament_service.list_guns(only_active=True)
    return {"success": True, "guns": guns}


# --------------------------------------------------------------------------
# 4. TOURNAMENTS & ARENA
# --------------------------------------------------------------------------
@router.get("/tournaments")
async def api_list_tournaments(
    status: Optional[str] = None,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    entry_type: Optional[str] = None,
    search: Optional[str] = None,
    joined: bool = False,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    request: Request = None
):
    user_id = None
    if request:
        try:
            auth_u = user_service.get_current_user(request)
            user_id = auth_u["id"]
        except Exception:
            pass

    tournaments = tournament_service.list_tournaments(
        status_filter=status,
        category_slug=category,
        subcategory_slug=subcategory,
        entry_type=entry_type,
        search_query=search,
        user_id=user_id,
        joined_only=joined,
        is_published_only=True,
        limit=limit,
        offset=offset
    )
    return {"success": True, "count": len(tournaments), "tournaments": tournaments}

@router.get("/tournaments/{tournament_id}")
async def api_tournament_detail(tournament_id: int, request: Request):
    user_id = None
    try:
        u = user_service.get_current_user(request)
        user_id = u["id"]
    except Exception:
        pass

    t = tournament_service.get_tournament_by_id(tournament_id, user_id=user_id)
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")
    return {"success": True, "tournament": t}

@router.post("/tournaments/{tournament_id}/join")
async def api_join_tournament(
    tournament_id: int,
    req: JoinTournamentRequest,
    user: dict = Depends(get_auth_user)
):
    try:
        res = tournament_service.join_tournament(
            tournament_id=tournament_id,
            user_id=user["id"],
            ff_uid=req.ff_uid,
            ff_ign=req.ff_ign
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.put("/tournaments/{tournament_id}/participant-credentials")
async def api_update_participant_credentials(
    tournament_id: int,
    req: ParticipantCredentialsRequest,
    user: dict = Depends(get_auth_user)
):
    try:
        res = tournament_service.update_participant_credentials(
            tournament_id=tournament_id,
            user_id=user["id"],
            ff_uid=req.ff_uid,
            ff_ign=req.ff_ign
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/tournaments/{tournament_id}/participants")
async def api_tournament_participants(tournament_id: int):
    parts = tournament_service.list_tournament_participants(tournament_id)
    return {"success": True, "count": len(parts), "participants": parts}

@router.get("/tournaments/{tournament_id}/results")
async def api_tournament_results(tournament_id: int):
    results = tournament_service.get_tournament_results(tournament_id)
    return {"success": True, "results": results}

@router.get("/tournaments/{tournament_id}/room")
async def api_tournament_room(
    tournament_id: int,
    user: dict = Depends(get_auth_user)
):
    try:
        credentials = tournament_service.get_tournament_room_credentials(tournament_id, user["id"])
        return {"success": True, **credentials}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

@router.post("/tournaments/{tournament_id}/favorite")
async def api_toggle_favorite(tournament_id: int, user: dict = Depends(get_auth_user)):
    fav = tournament_service.toggle_favorite(user["id"], tournament_id)
    return {"success": True, "is_favorited": fav, "message": "Saved to favorites" if fav else "Removed from favorites"}

@router.get("/tournaments/favorites/all")
@router.get("/tournaments/favorites")
async def api_list_favorites(user: dict = Depends(get_auth_user)):
    favs = tournament_service.list_user_favorites(user["id"])
    return {"success": True, "count": len(favs), "tournaments": favs}

@router.post("/tournaments/{tournament_id}/disputes", status_code=status.HTTP_201_CREATED)
async def api_create_tournament_dispute(
    tournament_id: int,
    req: DisputeRequest,
    user: dict = Depends(get_auth_user)
):
    disp = tournament_service.create_tournament_dispute(
        tournament_id=tournament_id,
        user_id=user["id"],
        dispute_type=req.dispute_type,
        description=req.description,
        proof_url=req.proof_url
    )
    return {"success": True, "message": "Dispute lodged. Admin will investigate.", "dispute": disp}

@router.get("/arena/notice")
async def api_arena_notice():
    all_settings = settings_service.get_all_settings()
    notice = all_settings.get("arena_notice_marquee", "Please be ready before match starts")
    return {"success": True, "notice": notice}


# --------------------------------------------------------------------------
# 5. WALLET & DIAMOND LEDGER
# --------------------------------------------------------------------------
@router.get("/wallet/balance")
async def api_wallet_balance(user: dict = Depends(get_auth_user)):
    info = wallet_service.get_wallet_info(user["id"])
    return {"success": True, **info}

@router.get("/wallet/rates")
async def api_wallet_rates():
    dep = wallet_service.get_deposit_settings()
    wit = wallet_service.get_withdrawal_settings()
    return {
        "success": True,
        "deposit": dep,
        "withdrawal": wit
    }

@router.get("/wallet/transactions")
async def api_wallet_transactions(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_auth_user)
):
    txs = wallet_service.list_transactions(user["id"], limit=limit, offset=offset)
    return {"success": True, "count": len(txs), "transactions": txs}

@router.get("/wallet/deposit-info")
async def api_wallet_deposit_info():
    dep_cfg = wallet_service.get_deposit_settings()
    return {"success": True, **dep_cfg}

@router.post("/wallet/upload-screenshot")
async def api_upload_payment_screenshot(
    file: UploadFile = File(...),
    user: dict = Depends(get_auth_user)
):
    allowed_exts = {"jpg", "jpeg", "png", "webp"}
    ext = file.filename.split(".")[-1].lower() if file.filename and "." in file.filename else ""
    content_type = (file.content_type or "").lower()
    if ext not in allowed_exts and content_type not in ("image/jpeg", "image/jpg", "image/png", "image/webp"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image format. Allowed formats: JPG, JPEG, PNG, WEBP."
        )
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds maximum allowed limit (5 MB)."
        )
    if len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty screenshot file uploaded."
        )
    safe_name = f"proof_{user['id']}_{secrets.token_hex(8)}.{ext if ext in allowed_exts else 'png'}"
    target_path = UPLOAD_DIR / safe_name
    with open(target_path, "wb") as f_out:
        f_out.write(contents)
    screenshot_url = f"/static/uploads/{safe_name}"
    return {
        "success": True,
        "screenshot_url": screenshot_url,
        "message": "Screenshot uploaded successfully"
    }

@router.post("/wallet/deposit-request", status_code=status.HTTP_201_CREATED)
async def api_submit_deposit(req: DepositRequestSchema, user: dict = Depends(get_auth_user)):
    try:
        created = wallet_service.create_deposit_request(
            user_id=user["id"],
            amount=req.amount,
            utr_reference=req.utr_reference,
            payment_proof_url=req.payment_proof_url
        )
        return {"success": True, "message": "Deposit request submitted. Pending admin review.", "request": created}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/wallet/deposit-requests")
async def api_my_deposit_requests(user: dict = Depends(get_auth_user)):
    requests = wallet_service.list_user_deposit_requests(user["id"])
    return {"success": True, "count": len(requests), "requests": requests}

@router.post("/wallet/withdraw", status_code=status.HTTP_201_CREATED)
async def api_withdraw(req: WithdrawalRequestSchema, user: dict = Depends(get_auth_user)):
    try:
        created = wallet_service.create_withdrawal_request(
            user_id=user["id"],
            amount=req.amount,
            upi_id=req.upi_id
        )
        return {"success": True, "message": "Withdrawal request submitted for admin review.", "withdrawal": created}
    except ValueError as e:
        if "disabled" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/wallet/withdrawals")
async def api_my_withdrawals(user: dict = Depends(get_auth_user)):
    reqs = wallet_service.list_user_withdrawal_requests(user["id"])
    return {"success": True, "count": len(reqs), "withdrawals": reqs}


# --------------------------------------------------------------------------
# 6. CONTENT, UPDATES, ANNOUNCEMENTS, COMMUNITIES, TUTORIALS
# --------------------------------------------------------------------------
@router.get("/updates/latest")
async def api_latest_updates():
    updates = content_features.list_latest_updates(only_published=True)
    return {"success": True, "updates": updates}

@router.get("/announcements")
async def api_announcements():
    ann = content_features.list_announcements(only_active=True)
    return {"success": True, "announcements": ann}

@router.get("/social/communities")
async def api_communities():
    comm = content_features.list_communities(only_active=True)
    return {"success": True, "communities": comm}

@router.get("/tutorials")
async def api_tutorials():
    tuts = content_features.list_tutorials(only_published=True)
    return {"success": True, "tutorials": tuts}

@router.get("/tutorials/{slug}")
async def api_tutorial_detail(slug: str):
    tut = content_features.get_tutorial_by_slug(slug)
    if not tut:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tutorial not found")
    return {"success": True, "tutorial": tut}


# --------------------------------------------------------------------------
# 7. LEADERBOARDS
# --------------------------------------------------------------------------
@router.get("/leaderboards")
async def api_leaderboards(
    type: str = Query("MOST_WINNING", regex="^(MOST_WINNING|MOST_KILLS|MOST_PLAYING)$"),
    limit: int = Query(50, ge=1, le=100)
):
    board = leaderboard_service.get_leaderboard(board_type=type, limit=limit)
    return {"success": True, **board}


# --------------------------------------------------------------------------
# 8. SOCIAL, REDEEM, REFERRALS, NOTIFICATIONS, SUPPORT
# --------------------------------------------------------------------------
@router.post("/redeem/apply")
async def api_redeem(req: RedeemCodeRequest, user: dict = Depends(get_auth_user)):
    try:
        res = social_service.redeem_code_for_user(user["id"], req.code)
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/referrals/stats")
async def api_referrals_stats(user: dict = Depends(get_auth_user)):
    summary = social_service.get_user_referral_summary(user["id"])
    return summary

@router.get("/notifications")
async def api_notifications(user: dict = Depends(get_auth_user)):
    notes = social_service.get_user_notifications(user["id"])
    return {"success": True, "count": len(notes), "notifications": notes}

@router.post("/notifications/{note_id}/read")
async def api_mark_notification(note_id: int, user: dict = Depends(get_auth_user)):
    social_service.mark_notification_as_read(note_id, user["id"])
    return {"success": True, "message": "Notification marked as read"}

@router.post("/notifications/read-all")
async def api_mark_all_notifications(user: dict = Depends(get_auth_user)):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE notifications SET is_read = 1 WHERE user_id = %s;", (user["id"],))
    return {"success": True, "message": "All notifications marked as read"}

@router.get("/support/tickets")
async def api_tickets(user: dict = Depends(get_auth_user)):
    tickets = social_service.list_user_support_tickets(user["id"])
    return {"success": True, "tickets": tickets}

@router.post("/support/tickets", status_code=status.HTTP_201_CREATED)
async def api_create_ticket(req: SupportTicketRequest, user: dict = Depends(get_auth_user)):
    ticket = social_service.create_support_ticket(
        user_id=user["id"],
        subject=req.subject,
        category=req.category,
        priority=req.priority,
        message=req.message
    )
    return {"success": True, "ticket": ticket}

@router.get("/support/tickets/{ticket_id}")
async def api_ticket_detail(ticket_id: int, user: dict = Depends(get_auth_user)):
    conv = social_service.get_ticket_conversation(ticket_id)
    if not conv or conv["user_id"] != user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return {"success": True, "ticket": conv}

@router.post("/support/tickets/{ticket_id}/reply")
async def api_reply_ticket(ticket_id: int, req: SupportReplyRequest, user: dict = Depends(get_auth_user)):
    conv = social_service.get_ticket_conversation(ticket_id)
    if not conv or conv["user_id"] != user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    msg = social_service.reply_to_ticket(ticket_id, "USER", user["id"], req.message)
    return {"success": True, "message": msg}

@router.post("/disputes", status_code=status.HTTP_201_CREATED)
async def api_create_dispute_legacy(req: DisputeRequest, user: dict = Depends(get_auth_user)):
    disp = social_service.create_match_dispute(
        match_id=1,
        tournament_id=1,
        reporter_user_id=user["id"],
        reason=req.dispute_type,
        proof_url=req.proof_url,
        description=req.description
    )
    return {"success": True, "message": "Dispute lodged. Admin will investigate.", "dispute": disp}

@router.get("/banners")
async def api_banners():
    banners = social_service.list_active_banners()
    return {"success": True, "banners": banners}
