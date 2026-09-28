import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
from service.catalog import Catalog
from service.push_logic import generation
from service.push_worker import deliver, send

class Document:
    def __init__(self,id,value):
        self.id=id; self.value=value; self.exists=True; self.reference=self; self.deleted=False
    def to_dict(self): return self.value
    def get(self): return self
    def delete(self): self.deleted=True
    def update(self,value): self.value.update(value)

class Collection:
    def __init__(self,docs): self.docs=docs
    def limit(self,n): return self
    def stream(self): return iter(self.docs)

class DeliveryTests(unittest.TestCase):
    @patch('service.push_worker.messaging.send')
    def test_apple_push_uses_alert_priority_expiry_and_deduplication(self, push):
        with patch('service.push_worker.now', return_value=datetime(2026,9,26,tzinfo=timezone.utc)):
            count=send([Document('iphone',{'enabled':True,'token':'test-only'})],
                       title='A new time',body='Araluen',data={'event_id':'abc'},tag='abc')
        self.assertEqual(count,1)
        message=push.call_args.args[0]
        self.assertEqual(message.apns.headers['apns-push-type'],'alert')
        self.assertEqual(message.apns.headers['apns-priority'],'10')
        self.assertEqual(message.apns.headers['apns-collapse-id'],'abc')
        self.assertEqual(int(message.apns.headers['apns-expiration']),int(datetime(2026,9,26,tzinfo=timezone.utc).timestamp())+600)
        self.assertEqual(message.apns.payload.aps.sound,'default')
        self.assertEqual(message.android.notification.channel_id,'tee_time_alerts')

    def setUp(self):
        self.clock=datetime(2026,9,26,tzinfo=timezone.utc)
        self.spec=dict(dates=['2026-09-27'],course_ids=['araluen'],holes=18,players=4,
                      from_minutes=0,to_minutes=719,enabled=True,created_at=self.clock)
        self.devices=[Document('a',{'enabled':True,'token':'a'}),Document('b',{'enabled':True,'token':'b'})]
        self.watch=Document('watch',self.spec)
        self.watch.parent=SimpleNamespace(parent=SimpleNamespace(collection=lambda _:Collection(self.devices)))
        self.match=dict(date='2026-09-27',course_id='araluen',course_name='Araluen',minutes=420,time='07:00 am',spots=4)
        self.event=Document('event',dict(watch_path='users/test/watches/watch',generation=generation(self.spec),
                                       created_at=self.clock,matches=[self.match]))
        self.db=SimpleNamespace(collection=lambda _:Collection([self.event]),document=lambda _:self.watch)
        self.raw={('2026-09-27',18,'araluen'):dict(site_name='Araluen',checked_at=self.clock.isoformat(),
                   decorated_rows=[dict(minutes=420,time='07:00 am',spots=4)])}
        self.catalog=Catalog()

    def run_delivery(self):
        with patch('service.push_worker.now',return_value=self.clock), patch('service.push_worker.read_acknowledgements', return_value={}), patch('service.push_worker.save_notification') as save:
            deliver(self.db,self.raw,self.catalog)
            return save

    @patch('service.push_worker.send',return_value=0)
    def test_history_is_saved_even_when_phone_delivery_fails(self,send):
        save=self.run_delivery()
        save.assert_called_once()
        self.assertEqual(save.call_args.args[1], 'event')
        self.assertEqual(save.call_args.args[4]['watch_id'], 'watch')
        self.assertFalse(self.event.deleted)

    @patch('service.push_worker.send')
    def test_partial_failure_retries_only_unsent_device(self,send):
        send.side_effect=[1,0]
        self.run_delivery()
        self.assertEqual(self.event.value['accepted_devices'],['a'])
        self.assertFalse(self.event.deleted)
        send.reset_mock();send.side_effect=[1]
        self.run_delivery()
        self.assertEqual(send.call_count,1)
        self.assertEqual(send.call_args.args[0][0].id,'b')
        self.assertTrue(self.event.deleted)

    @patch('service.push_worker.send')
    def test_deleted_watch_never_sends(self,send):
        self.watch.exists=False
        self.run_delivery();send.assert_not_called();self.assertTrue(self.event.deleted)

    @patch('service.push_worker.send')
    def test_changed_threshold_or_stale_data_cannot_send(self,send):
        for spots,stamp in [(3,self.clock),(4,self.clock-timedelta(minutes=16))]:
            self.raw[('2026-09-27',18,'araluen')]['decorated_rows'][0]['spots']=spots
            self.raw[('2026-09-27',18,'araluen')]['checked_at']=stamp.isoformat()
            self.run_delivery();send.assert_not_called()

    @patch('service.push_worker.send')
    def test_reenabled_alert_rejects_previous_outbox(self,send):
        self.watch.value={**self.spec,'created_at':self.clock+timedelta(seconds=1)}
        self.run_delivery();send.assert_not_called();self.assertTrue(self.event.deleted)

if __name__=='__main__': unittest.main()
