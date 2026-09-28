import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch
from service.recurrence import recurrence_dates, pending_rounds, sorted_dates
from service.push_logic import validate_watch, generation
from service.catalog import Catalog
from service.tests.test_push_delivery import DeliveryTests
from service.push_worker import deliver

def schedule(kind='weekly', **changes):
    return dict(kind=kind, anchor='2026-09-28', weekday=1, day=31, ordinal=5, **changes)

class RecurrenceTests(unittest.TestCase):
    def test_calendar_examples(self):
        self.assertEqual(recurrence_dates(schedule(),date(2026,9,28)),['2026-09-28','2026-10-05','2026-10-12','2026-10-19'])
        self.assertEqual(recurrence_dates(schedule('fortnightly'),date(2026,10,1)),['2026-10-12','2026-10-26'])
        self.assertEqual(recurrence_dates(schedule('monthly_day'),date(2026,11,1)),[])
        self.assertEqual(recurrence_dates(schedule('monthly_weekday'),date(2026,10,1)),['2026-10-26'])
        leap={**schedule('monthly_day'),'anchor':'2024-01-01','day':29}
        self.assertEqual(recurrence_dates(leap,date(2024,2,1),29),['2024-02-29'])
        self.assertEqual(recurrence_dates(leap,date(2025,2,1),28),[])

    def test_old_anchor_keeps_running_and_future_anchor_waits(self):
        raw=dict(enabled=True, dates=['2026-09-28'], course_ids=['araluen'], holes=18, players=4,
                 from_minutes=360,to_minutes=600,recurrence=schedule())
        value=validate_watch(raw,Catalog(),datetime(2027,1,1,tzinfo=timezone.utc))
        self.assertEqual(value['dates'][0],'2027-01-04')
        self.assertEqual(generation(raw),generation(dict(raw)))
        self.assertEqual(recurrence_dates({**schedule(),'anchor':'2027-01-01'},date(2026,9,28)),[])

    def test_sorted_only_skips_that_occurrence(self):
        spec={'dates':['2026-09-28','2026-10-05','2026-10-12'],'recurrence':schedule()}
        self.assertEqual(pending_rounds(spec,{}),['2026-09-28'])
        self.assertEqual(pending_rounds(spec,{'dates':['2026-09-28']}),['2026-10-05'])
        self.assertEqual(pending_rounds(spec,{'dates':[]}),['2026-09-28'])
        self.assertEqual(sorted_dates({'dates':[False,{},'2026-02-30','2026-10-05']}),{'2026-10-05'})
        del spec['recurrence']
        self.assertEqual(pending_rounds(spec,{'dates':['2026-09-28']}),['2026-10-05','2026-10-12'])

    def test_invalid_rules_are_rejected(self):
        for changes in [{'weekday':True},{'weekday':0},{'ordinal':6},{'kind':'daily'},{'anchor':'2026-02-30'},{'extra':1}]:
            with self.assertRaises((ValueError,TypeError)):
                recurrence_dates({**schedule(),**changes},date(2026,9,28))

class AcknowledgementDeliveryTests(DeliveryTests):
    def test_ack_before_or_during_delivery_stops_unsent_devices(self):
        for timeline, count in [([{'dates':['2026-09-27']}],0),([{}, {'dates':['2026-09-27']}],0),([{}, {}, {}, {'dates':['2026-09-27']}],1)]:
            self.setUp()
            with patch('service.push_worker.now',return_value=self.clock), patch('service.push_worker.read_acknowledgements',side_effect=timeline), patch('service.push_worker.save_notification'), patch('service.push_worker.send',return_value=1) as send:
                deliver(self.db,self.raw,self.catalog)
                self.assertEqual(send.call_count,count)
                self.assertTrue(self.event.deleted)

if __name__=='__main__': unittest.main()
