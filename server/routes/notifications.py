"""
Notification Management Routes

This module handles user notifications including invitation acceptances
and other system events that users should be aware of.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..dependencies import AuthContext, authenticate_api_key, mongo_db
from ..utils.datetime_helpers import utc_now
from ..utils.permission_helpers import get_user_by_kratos_id
from ..utils.validators import validate_object_id

router = APIRouter(prefix="/api/notifications", tags=["notifications"])
logger = logging.getLogger(__name__)


class NotificationResponse(BaseModel):
    """Response model for notification"""

    id: str
    type: str
    title: str
    message: str
    metadata: dict
    read: bool
    createdAt: str


@router.get("", summary="List user notifications")
def list_notifications(auth: AuthContext = Depends(authenticate_api_key)):
    """
    List all notifications for authenticated user.

    Returns notifications sorted by most recent first.
    Includes unread count for badge display.
    """
    # Get user MongoDB ObjectId
    try:
        user = get_user_by_kratos_id(mongo_db, auth.user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None

    user_obj_id = user["_id"]

    # Get notifications sorted by most recent
    notifications = list(
        mongo_db.notifications.find({"userId": user_obj_id})
        .sort("createdAt", -1)
        .limit(50)  # Last 50 notifications
    )

    # Count unread
    unread_count = mongo_db.notifications.count_documents(
        {"userId": user_obj_id, "read": False}
    )

    # Format response
    notifications_list = [
        NotificationResponse(
            id=str(n["_id"]),
            type=n["type"],
            title=n["title"],
            message=n["message"],
            metadata=n["metadata"],
            read=n["read"],
            createdAt=n["createdAt"].isoformat(),
        )
        for n in notifications
    ]

    logger.info(
        f"Retrieved {len(notifications_list)} notifications for user {auth.user_id}, "
        f"unread={unread_count}"
    )

    return {"notifications": notifications_list, "unread_count": unread_count}


@router.put("/{notification_id}/read", summary="Mark notification as read")
def mark_notification_read(
    notification_id: str, auth: AuthContext = Depends(authenticate_api_key)
):
    """Mark a specific notification as read"""

    notification_obj_id = validate_object_id(notification_id, "notification_id")

    # Get user MongoDB ObjectId
    try:
        user = get_user_by_kratos_id(mongo_db, auth.user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None

    user_obj_id = user["_id"]

    # Update notification
    result = mongo_db.notifications.update_one(
        {"_id": notification_obj_id, "userId": user_obj_id},
        {"$set": {"read": True, "readAt": utc_now()}},
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")

    logger.info(
        f"Marked notification {notification_id} as read for user {auth.user_id}"
    )

    return {
        "message": "Notification marked as read",
        "notification_id": notification_id,
    }


@router.put("/read-all", summary="Mark all notifications as read")
def mark_all_notifications_read(auth: AuthContext = Depends(authenticate_api_key)):
    """Mark all notifications as read for authenticated user"""

    # Get user MongoDB ObjectId
    try:
        user = get_user_by_kratos_id(mongo_db, auth.user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None

    user_obj_id = user["_id"]

    # Update all unread notifications
    result = mongo_db.notifications.update_many(
        {"userId": user_obj_id, "read": False},
        {"$set": {"read": True, "readAt": utc_now()}},
    )

    logger.info(
        f"Marked {result.modified_count} notifications as read for user {auth.user_id}"
    )

    return {
        "message": "All notifications marked as read",
        "count": result.modified_count,
    }
