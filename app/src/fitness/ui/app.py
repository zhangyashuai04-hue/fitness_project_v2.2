from dataclasses import dataclass
from fitness.services.weight import WeightService
from fitness.services.nutrition import NutritionService
from fitness.services.plans import PlanService
from fitness.services.training import TrainingService
from fitness.services.history import HistoryService
from fitness.services.today import TodayService
from fitness.services.trends import TrendService


@dataclass(frozen=True)
class AppServices:
    weight: WeightService
    nutrition: NutritionService
    plans: PlanService
    training: TrainingService
    history: HistoryService
    today: TodayService
    trends: TrendService

    @classmethod
    def create(cls,db,clock):
        return cls(WeightService(db,clock),NutritionService(db,clock),PlanService(db,clock),
                   TrainingService(db,clock),HistoryService(db,clock),TodayService(db,clock),TrendService(db))
