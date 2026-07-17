'''
    __init__.py is a special Python file used to define a directory as a Python package.
    1. Mark a directory as a package: With __init__.py, Python can treat the directory as an importable package
    2. Run initialization code: Code inside __init__.py runs when the package is imported
    3. Simplify imports
    4. Control public exports with __all__: This indicates which names are intended to be publicly available from the package
    It is completely valid for the file to be empty.Its presence alone can indicate that models is a Python package.
    In most FastAPI projects, __init__.py is either empty or used to collect commonly imported models, schemas, routers, or services.
'''
from app.schemas.daily_task import (
    DailyPlanGenerateRequest,
    DailyPlanResponse,
    DailyTaskCreate,
    DailyTaskRead,
    DailyTaskUpdate,
)
from app.schemas.automation_preference import (
    AutomationPreferenceRead,
    AutomationPreferenceUpdate,
    NotificationChannel,
    StudyPeriod,
    WorkingDay,
)
from app.schemas.notification import (
    NotificationRead,
    NotificationSend,
    NotificationStatus,
    NotificationType,
)
from app.schemas.daily_check_in import (
    DailyCheckInCreate,
    DailyCheckInRead,
    DailyCheckInUpdate,
    EnergyLevel,
    MoodLevel,
)
from app.schemas.coaching import (
    CoachingAdvice,
    CoachingContext,
    CoachingRecommendationGenerateRequest,
    CoachingRecommendationRead,
    CoachingRecommendationResponse,
    WorkloadAdjustment,
    WorkloadLevel,
)
from app.schemas.dashboard import TodayDashboardResponse, WeekDashboardResponse
from app.schemas.review import (
    DailyReviewCreate,
    DailyReviewGenerateRequest,
    DailyReviewRead,
)
from app.schemas.study_session import (
    StudySessionFinish,
    StudySessionRead,
    StudySessionStart,
)
from app.schemas.user import TokenResponse, UserCreate, UserLogin, UserRead, UserUpdate
from app.schemas.user_app_setting import (
    Integration,
    UserAppSettingRead,
    UserAppSettingUpdate,
)
from app.schemas.weekly_goal import (
    WeeklyGoalCreate,
    WeeklyGoalRead,
    WeeklyGoalUpdate,
)
from app.schemas.weekly_review import (
    WeeklyReviewAdvice,
    WeeklyReviewContext,
    WeeklyReviewGenerateRequest,
    WeeklyReviewRead,
)

__all__ = [
    "AutomationPreferenceRead",
    "AutomationPreferenceUpdate",
    "DailyPlanGenerateRequest",
    "DailyPlanResponse",
    "CoachingAdvice",
    "CoachingContext",
    "CoachingRecommendationGenerateRequest",
    "CoachingRecommendationRead",
    "CoachingRecommendationResponse",
    "WorkloadAdjustment",
    "WorkloadLevel",
    "DailyCheckInCreate",
    "DailyCheckInRead",
    "DailyCheckInUpdate",
    "DailyReviewCreate",
    "DailyReviewGenerateRequest",
    "DailyReviewRead",
    "DailyTaskCreate",
    "DailyTaskRead",
    "DailyTaskUpdate",
    "EnergyLevel",
    "MoodLevel",
    "NotificationChannel",
    "NotificationRead",
    "NotificationSend",
    "NotificationStatus",
    "NotificationType",
    "StudyPeriod",
    "StudySessionFinish",
    "StudySessionRead",
    "StudySessionStart",
    "TodayDashboardResponse",
    "TokenResponse",
    "UserCreate",
    "UserLogin",
    "UserRead",
    "UserUpdate",
    "Integration",
    "UserAppSettingRead",
    "UserAppSettingUpdate",
    "WeekDashboardResponse",
    "WeeklyGoalCreate",
    "WeeklyGoalRead",
    "WeeklyGoalUpdate",
    "WeeklyReviewAdvice",
    "WeeklyReviewContext",
    "WeeklyReviewGenerateRequest",
    "WeeklyReviewRead",
    "WorkingDay",
]
