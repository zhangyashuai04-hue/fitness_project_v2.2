import pytest
from fitness.domain.models import Measurements

def rules():
    from fitness.domain import free_training
    return free_training

@pytest.mark.parametrize('reps,weight,value', [('', '', Measurements()),('10','',Measurements(reps=10)),('','0',Measurements(weight=0)),(' 10 ','40',Measurements(reps=10,weight=40)),('  ',' ',Measurements())])
def test_partial_values(reps,weight,value):
    r=rules()
    assert r.parse_measurements(reps,weight)==value
    assert r.should_save(value)==(value!=Measurements())

@pytest.mark.parametrize('reps,weight',[('0',''),('-1',''),('1.5',''),('abc',''),('','nan'),('','inf'),('','-1'),('','abc')])
def test_invalid_not_empty(reps,weight):
    with pytest.raises(ValueError): rules().parse_measurements(reps,weight)

@pytest.mark.parametrize('value',[Measurements(),Measurements(reps=10),Measurements(weight=0)])
def test_next_set_needs_both(value):
    with pytest.raises(ValueError): rules().validate_next_set(value)

def test_zero_weight_complete():
    rules().validate_next_set(Measurements(reps=10,weight=0))
