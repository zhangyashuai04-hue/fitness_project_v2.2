import asyncio
from unittest.mock import Mock
from fitness.ui.charts import build_chart

def test_single_point_has_date_details_action():
    callback=Mock()
    point=dict(day='2026-10-01',value=75,set_ids=['a'],missing_elapsed=0)
    chart=build_chart(dict(name='体重',unit='kg',points=[point]),callback)
    button=chart.controls[-1].controls[0]
    asyncio.run(button.on_click(None))
    callback.assert_called_once_with(point)
