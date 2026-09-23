from fastapi import APIRouter, Request, Depends, HTTPException, status, Query, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Optional, List
from app.config import WITHDRAWALS_ENABLED, UPLOAD_DIR, GOOGLE_CLIENT_ID
from app.services import (
    users_auth as user_service,
    referrals as referrals_service,
    tournaments as tournament_service,
    wallet as wallet_service,
    matches as match_service,
    leaderboards as leaderboard_service,
    social as social_service,
    settings as settings_service
)

router = APIRouter(prefix="/api/v1")

# --------------------------------------------------------------------------
# DEPENDENCY: GET CURRENT USER
# --------------------------------------------------------------------------
def get_auth_user(request: Request) -> dict:
    return user_service.get_current_user(request)

# --------------------------------------------------------------------------
# PYDANTIC SCHEMAS
# --------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = None
    phone: Optional[str] = None
    password: Optional[str] = Field(None, min_length=6)
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

class UpdateFreeFireRequest(BaseModel):
    ff_uid: str
    ff_ign: str

class UpdateAvatarRequest(BaseModel):
    avatar_url: str

class JoinTournamentRequest(BaseModel):
    ff_uid: str
    ff_ign: str

class DepositRequestSchema(BaseModel):
    amount: int = Field(..., ge=10)
    utr_reference: str = Field(..., min_length=6)
    payment_proof_url: str = Field(..., min_length=5)

class WithdrawalRequestSchema(BaseModel):
    amount: int = Field(..., ge=100)
    upi_id: str = Field(..., min_length=5)

class RedeemCodeRequest(BaseModel):
    code: str = Field(..., min_length=3)

class SupportTicketRequest(BaseModel):
    subject: str = Field(..., min_length=5)
    category: str = Field(default="GENERAL")
    priority: str = Field(default="NORMAL")
    message: str = Field(..., min_length=10)

class SupportReplyRequest(BaseModel):
    message: str = Field(..., min_length=1)

class DisputeRequest(BaseModel):
    match_id: int
    tournament_id: int
    reason: str
    proof_url: Optional[str] = None
    description: Optional[str] = None

# --------------------------------------------------------------------------
# 1. AUTHENTICATION ENDPOINTS
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
    return {"success": True, "profile": user}

@router.put("/users/freefire")
async def api_update_freefire(req: UpdateFreeFireRequest, user: dict = Depends(get_auth_user)):
    try:
        updated = user_service.update_user_freefire(user["id"], req.ff_uid, req.ff_ign)
        return {"success": True, "profile": updated}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.put("/users/profile")
async def api_update_avatar(req: UpdateAvatarRequest, user: dict = Depends(get_auth_user)):
    updated = user_service.update_user_avatar(user["id"], req.avatar_url)
    return {"success": True, "profile": updated}

@router.get("/users/matches")
async def api_user_matches(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_auth_user)
):
    history = match_service.get_user_match_history(user["id"], limit=limit, offset=offset)
    return {"success": True, "count": len(history), "matches": history}

# --------------------------------------------------------------------------
# 3. TOURNAMENTS
# --------------------------------------------------------------------------
@router.get("/tournaments")
async def api_list_tournaments(
    status: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    tournaments = tournament_service.list_tournaments(status_filter=status, limit=limit, offset=offset)
    return {"success": True, "count": len(tournaments), "tournaments": tournaments}

@router.get("/tournaments/{tournament_id}")
async def api_tournament_detail(tournament_id: int, request: Request):
    user_id = None
    try:
        user = user_service.get_current_user(request)
        user_id = user["id"]
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

# --------------------------------------------------------------------------
# 4. WALLET & DIAMOND LEDGER
# --------------------------------------------------------------------------
@router.get("/wallet/balance")
async def api_wallet_balance(user: dict = Depends(get_auth_user)):
    info = wallet_service.get_wallet_info(user["id"])
    return {"success": True, **info}

@router.get("/wallet/transactions")
async def api_wallet_transactions(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_auth_user)
):
    txs = wallet_service.list_transactions(user["id"], limit=limit, offset=offset)
    return {"success": True, "count": len(txs), "transactions": txs}

@router.get("/wallet/deposit-info")
async def api_wallet_deposit_info():
    all_settings = settings_service.get_all_settings()
    upi_id = all_settings.get("upi_id", "god4xe@upi")
    payee_name = all_settings.get("upi_payee_name", "GOD4XE ESPORTS")
    min_dep = int(all_settings.get("min_deposit_diamonds", "50"))
    instructions = all_settings.get("deposit_instructions", "Scan QR or send UPI payment, then enter UTR reference.")

    upi_qr_img = all_settings.get("upi_qr_image_url", "")
    return {
        "success": True,
        "upi_id": upi_id,
        "payee_name": payee_name,
        "min_deposit_diamonds": min_dep,
        "instructions": instructions,
        "upi_qr_string": f"upi://pay?pa={upi_id}&pn={payee_name}&cu=INR",
        "upi_qr_image_url": upi_qr_img
    }


@router.post("/wallet/upload-screenshot")
async def api_upload_payment_screenshot(
    file: UploadFile = File(...),
    user: dict = Depends(get_auth_user)
):
    import secrets
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

@router.post("/wallet/withdraw")
async def api_withdraw(req: WithdrawalRequestSchema, user: dict = Depends(get_auth_user)):
    if not WITHDRAWALS_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Withdrawal features are currently review-gated and disabled pending regulatory and platform compliance."
        )
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Withdrawals are not enabled in this environment.")

# --------------------------------------------------------------------------
# 5. LEADERBOARDS
# --------------------------------------------------------------------------
@router.get("/leaderboards")
async def api_leaderboards(
    type: str = Query("MOST_WINNING", regex="^(MOST_WINNING|MOST_KILLS|MOST_PLAYING)$"),
    limit: int = Query(50, ge=1, le=100)
):
    board = leaderboard_service.get_leaderboard(board_type=type, limit=limit)
    return {"success": True, **board}

# --------------------------------------------------------------------------
# 6. SOCIAL, REDEEM, REFERRALS, NOTIFICATIONS, SUPPORT
# --------------------------------------------------------------------------
@router.post("/redeem/apply")
async def api_redeem(req: RedeemCodeRequest, user: dict = Depends(get_auth_user)):
    try:
        res = social_service.redeem_code_for_user(user["id"], req.code)
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/referrals/me")
@router.get("/referrals/stats")
async def api_referrals_me(user: dict = Depends(get_auth_user)):
    summary = referrals_service.get_user_referral_summary(user["id"])
    return summary

@router.get("/referrals/leaderboard")
async def api_referrals_leaderboard(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    board = referrals_service.get_referral_leaderboard(limit=limit, offset=offset)
    return board

@router.get("/referrals/ranks")
async def api_referrals_ranks():
    ranks = referrals_service.get_active_ranks()
    return {"success": True, "ranks": ranks}

@router.get("/notifications")
async def api_notifications(user: dict = Depends(get_auth_user)):
    notes = social_service.get_user_notifications(user["id"])
    return {"success": True, "count": len(notes), "notifications": notes}

@router.post("/notifications/{note_id}/read")
async def api_mark_notification(note_id: int, user: dict = Depends(get_auth_user)):
    social_service.mark_notification_as_read(note_id, user["id"])
    return {"success": True, "message": "Notification marked as read"}

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
async def api_create_dispute(req: DisputeRequest, user: dict = Depends(get_auth_user)):
    disp = social_service.create_match_dispute(
        match_id=req.match_id,
        tournament_id=req.tournament_id,
        reporter_user_id=user["id"],
        reason=req.reason,
        proof_url=req.proof_url,
        description=req.description
    )
    return {"success": True, "message": "Dispute lodged. Admin will investigate.", "dispute": disp}

@router.get("/banners")
async def api_banners():
    banners = social_service.list_active_banners()
    return {"success": True, "banners": banners}
