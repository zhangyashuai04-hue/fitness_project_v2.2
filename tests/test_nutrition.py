from datetime import date
import pytest
from fitness.services.nutrition import NutritionService


def test_optional_grams_and_expenditure(db,clock):
    s=NutritionService(db,clock)
    day=date(2026,10,1)
    identity=s.save_food(day,'米饭',230)
    assert s.foods(day)[0]['grams'] is None
    assert s.summary(day)==dict(intake=230,expenditure=None,balance=None)
    original=s.foods(day)[0]['created_at']
    clock.advance_ms(10000)
    s.save_food(day,'米饭',240,100,identity)
    assert s.foods(day)[0]['created_at']==original
    s.save_expenditure(day,100)
    assert s.summary(day)['balance']==140
    assert len(s.foods(day))==1


@pytest.mark.parametrize('name,calories,grams',[(' ',1,None),('x',-1,None),('x',float('nan'),None),('x',1,0),('x',1,float('inf')),('x',True,None)])
def test_invalid_food(db,clock,name,calories,grams):
    with pytest.raises(ValueError): NutritionService(db,clock).save_food(clock.today(),name,calories,grams)


def test_zero_calories_and_independent_expenditure(db,clock):
    s=NutritionService(db,clock)
    day=date(2026,10,3)
    s.save_expenditure(day,0)
    s.save_food(day,'水',0)
    assert s.summary(day)==dict(intake=0,expenditure=0,balance=0)
