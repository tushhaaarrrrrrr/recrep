from services.db_service import DBService
from utils.logger import get_logger
import re

logger = get_logger(__name__)

REP_POINTS = {
    'recruitment': 7,
    'progress_report': 10,
    'progress_help': 10,
    'purchase_invoice': 5,
    'demolition_report': 3,
    'demolition_request': 3,
    'eviction_report': 2,
    'scroll_completion': 5,
    'approval': 2
}


def extract_user_id_from_mention(mention: str) -> int:
    """Extract Discord user ID from a mention string like '<@123456789>'."""
    match = re.search(r'<@!?(\d+)>', mention)
    if match:
        return int(match.group(1))
    return None


async def award_submitter_points(submitter_id: int, form_type: str, form_id: int):
    """Award points to the form submitter upon approval."""
    points = REP_POINTS.get(form_type, 0)
    if points:
        await DBService.add_reputation(
            submitter_id, points, f"Submitted {form_type}", form_type, form_id
        )
        logger.debug(f"Awarded {points} points to submitter {submitter_id} for {form_type} #{form_id}")


async def award_helper_points(helper_mention: str, form_id: int):
    """Award points to a helper mentioned in a progress report."""
    helper_id = extract_user_id_from_mention(helper_mention)
    if helper_id:
        points = REP_POINTS['progress_help']
        await DBService.add_reputation(
            helper_id, points, f"Helped in progress report {form_id}", 'progress_help', form_id
        )
        logger.debug(f"Awarded {points} points to helper {helper_id} for progress report #{form_id}")
        return True
    return False


async def award_approval_points(approver_id: int, form_type: str, form_id: int):
    """Award points to the approver."""
    points = REP_POINTS['approval']
    await DBService.add_reputation(
        approver_id, points, f"Approved {form_type}", f"{form_type}_approval", form_id
    )
    logger.debug(f"Awarded {points} points to approver {approver_id} for {form_type} #{form_id}")