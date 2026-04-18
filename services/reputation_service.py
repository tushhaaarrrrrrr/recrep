from services.db_service import DBService
from utils.logger import get_logger
from config.points import REP_POINTS, SCROLL_POINTS
import re

logger = get_logger(__name__)


def extract_user_id_from_mention(mention: str) -> int:
    """Extract Discord user ID from a mention string like '<@123456789>'."""
    match = re.search(r'<@!?(\d+)>', mention)
    if match:
        return int(match.group(1))
    return None


async def award_submitter_points(submitter_id: int, form_type: str, form_id: int, points_override: int = None):
    """
    Award points to the form submitter upon approval.
    If points_override is provided, it will be used instead of the default from REP_POINTS.
    """
    points = points_override if points_override is not None else REP_POINTS.get(form_type, 0)
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