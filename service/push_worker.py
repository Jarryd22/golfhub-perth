"""One bounded GitHub checker run; Firebase ADC/OIDC only, no private key in code.

Provider reads are shared across watches. Firestore transactions persist quiet
baselines and an outbox together. Delivery rechecks the watch and fresh matches.
FCM is at-least-once: a stable Android notification tag collapses crash retries.
"""
import argparse
import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import firebase_admin
from firebase_admin import firestore, messaging

from app.cache_schema import make_snapshot
from app.golfhub_core import DATA_DIR, CONFIG_FILE, load_sites, fetch_site_result, preload_weather_cache
from service.catalog import Catalog
from service.search import course_result
from service.push_logic import validate_watch, generation, transition, event_id, slot_key, valid_matches, quiet_now, delivery_ttl
from service.checker_gate import acquire, finish
from service.recurrence import sorted_dates, pending_rounds

PROJECT = 'golfhub-perth'


def now():
    return datetime.now(timezone.utc)


def acknowledgement_ref(doc):
    return doc.reference.parent.parent.collection('watchAcknowledgements').document(doc.id)


def read_acknowledgements(doc):
    value = acknowledgement_ref(doc).get()
    return value.to_dict() if value.exists else {}


def save_notification(user, identifier, title, body, data, created):
    # Persist independently of Android banner permission/delivery. Repeated
    # attempts overwrite the same immutable event, never create duplicates.
    user.collection('notifications').document(identifier).set({
        'title': title, 'body': body, 'data': data, 'created_at': created,
        'expires_at': created + timedelta(days=30),
    })


def send(devices, *, title, body, data, tag, ttl_seconds=600):
    delivered = 0
    for device in devices:
        value = device.to_dict()
        if not value.get('enabled') or not value.get('token'):
            continue
        try:
            messaging.send(messaging.Message(token=value['token'],
                notification=messaging.Notification(title=title, body=body), data=data,
                android=messaging.AndroidConfig(priority='high', ttl=timedelta(seconds=ttl_seconds),
                    notification=messaging.AndroidNotification(channel_id='tee_time_alerts',
                        icon='notification_golf', tag=tag)),
                apns=messaging.APNSConfig(
                    headers={'apns-push-type': 'alert', 'apns-priority': '10',
                             'apns-expiration': str(int((now()+timedelta(seconds=ttl_seconds)).timestamp())),
                             'apns-collapse-id': tag},
                    payload=messaging.APNSPayload(messaging.Aps(sound='default')))))
            delivered += 1
        except messaging.UnregisteredError:
            device.reference.update({'enabled': False})
        except Exception:
            # Never print a registration token or private watch document.
            logging.warning('A notification could not be delivered; it can be retried.')
    return delivered


def phone_tests(db):
    for doc in db.collection_group('pushTests').limit(100).stream():
        if len(doc.reference.path.split('/')) != 4 or not doc.reference.path.startswith('users/'):
            continue
        value = doc.to_dict()
        created = value.get('created_at')
        if not isinstance(created, datetime) or not timedelta(0) <= now()-created < timedelta(hours=1):
            doc.reference.delete()
            continue
        user = doc.reference.parent.parent
        device = user.collection('devices').document(doc.id).get()
        if device.exists:
            identifier = hashlib.sha256((doc.reference.path+str(created)).encode()).hexdigest()[:32]
            save_notification(user, identifier, 'GolfHub server test',
                'This notification travelled from the GitHub checker to your phone.',
                {'kind': 'test', 'event_id': identifier}, created)
            count = send([device], title='GolfHub server test',
                body='This notification travelled from the GitHub checker to your phone.',
                data={'kind':'test', 'event_id':identifier}, tag=identifier)
            if count:
                # Delete only this request, not a newer test queued while sending.
                @firestore.transactional
                def acknowledge(tx):
                    latest = doc.reference.get(transaction=tx)
                    if latest.exists and latest.to_dict().get('created_at') == created:
                        tx.delete(doc.reference)
                acknowledge(db.transaction())
                print('Server test accepted by FCM.')


def collect(specs, catalog):
    by_name={s.name:s for s in load_sites(DATA_DIR/CONFIG_FILE)}
    requests=sorted({(day,spec['holes'],cid) for spec in specs for day in spec['dates'] for cid in spec['course_ids']})
    if len(requests)>160:
        raise RuntimeError('Private test checker limit reached: reduce watched courses/dates before enabling more alerts.')
    # Weather is supplied by the main cache; alert scans do not need another forecast request.
    preload_weather_cache({s.weather_query:{} for s in by_name.values() if s.weather_query})
    result={}
    def fetch(key):
        day,holes,cid=key
        site=by_name[catalog.courses[cid]['name']]
        if site.provider=='direct':
            return dict(site_name=site.name, direct_booking=True)
        observed=fetch_site_result(site,day,str(holes),None,None,None)
        observed['checked_at']=now().isoformat()
        return observed
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(fetch,key):key for key in requests}
        for future in as_completed(futures):
            key=futures[future]
            try: result[key]=future.result()
            except Exception: result[key]=dict(site_name=catalog.courses[key[2]]['name'],error='Refresh failed')
    return result


def rows_for(spec, raw, catalog, clock):
    rows=[]
    for day in spec['dates']:
        for cid in spec['course_ids']:
            observed=raw[(day,spec['holes'],cid)]
            # Actual collector checked_at must be preserved, never freshened at delivery.
            snapshot=make_snapshot(day,str(spec['holes']),[observed])
            row=course_result(catalog.courses[cid],observed,snapshot,spec['players'],
                spec['from_minutes'],spec['to_minutes'],clock)
            rows.append((day,cid,row))
    return rows


def evaluate(db, doc, spec, raw, catalog):
    clock=now()
    gen=generation(doc.to_dict())
    user=doc.reference.parent.parent
    state_id=hashlib.sha256((doc.reference.path+gen).encode()).hexdigest()
    root=db.collection('alertState').document(state_id)
    rows=rows_for(spec,raw,catalog,clock)
    @firestore.transactional
    def commit(tx):
        latest=doc.reference.get(transaction=tx)
        if not latest.exists or generation(latest.to_dict())!=gen:
            return
        ack = acknowledgement_ref(doc).get(transaction=tx)
        done = sorted_dates(ack.to_dict() if ack.exists else {})
        refs=[root.collection('observations').document(day+'_'+cid) for day,cid,_ in rows]
        previous=[ref.get(transaction=tx) for ref in refs]
        changed=[]; matches=[]; fresh=0
        for (day,cid,row),ref,old in zip(rows,refs,previous):
            if day in done:
                continue
            before=old.to_dict() if old.exists else None
            # Keep the pre-quiet baseline. At the next awake check only openings
            # still present in fresh provider data will qualify.
            after,new=(before,[]) if quiet_now(spec,clock) else transition(before,row,day,clock,spec.get('notify_existing', False))
            if valid_matches(row,day,clock) is not None: fresh+=1
            if after != before: changed.append((ref,after))
            for tee in new:
                matches.append(dict(date=day,course_id=cid,course_name=catalog.courses[cid]['name'],**tee))
        for ref,after in changed: tx.set(ref,after)
        for day,cid,row in rows:
            tx.set(user.collection('watchResults').document(doc.id).collection('days').document(day).collection('courses').document(cid),
                   {'watch_created_at':doc.to_dict()['created_at'],'result':row})
        tx.set(root,{'watch_path':doc.reference.path,'generation':gen,'expires_at':max(spec['dates']) if spec['dates'] else '',
                     'updated_at':clock})
        tx.set(user.collection('watchStatus').document(doc.id),{'last_checked_at':clock,'fresh_courses':fresh,
                     'total_course_dates':len(rows),'state':'quiet' if quiet_now(spec,clock) else 'monitoring' if spec['dates'] else 'expired'})
        if matches:
            # Same slot can reopen twice; each observation needs its own event.
            # Each notification belongs to one round, so acknowledging Monday
            # cannot silently acknowledge a different date in the same message.
            for day in sorted({m['date'] for m in matches}):
                daily = [m for m in matches if m['date'] == day]
                identifier=event_id(doc.reference.path,gen + clock.isoformat(),daily)
                tx.set(db.collection('alertOutbox').document(identifier),{'watch_path':doc.reference.path,'generation':gen,
                    'created_at':clock,'matches':daily,'players':spec['players'],'holes':spec['holes']})
    commit(db.transaction())


def deliver(db, raw, catalog):
    for event in db.collection('alertOutbox').limit(100).stream():
        value=event.to_dict(); clock=now()
        doc=db.document(value['watch_path']).get()
        if (not doc.exists or generation(doc.to_dict())!=value['generation']):
            event.reference.delete(); continue
        try: spec=validate_watch(doc.to_dict(),catalog,clock)
        except (ValueError,KeyError,TypeError): event.reference.delete(); continue
        spec['dates'] = pending_rounds(spec, read_acknowledgements(doc))
        # A delivery interrupted by quiet hours may wait through one window.
        # Its slots are checked against fresh data again before sending.
        lifetime=timedelta(hours=24) if 'quiet_from_minutes' in spec else timedelta(minutes=10)
        if clock-value['created_at']>=lifetime:
            event.reference.delete(); continue
        if quiet_now(spec,clock): continue
        valid=[]
        for match in value['matches']:
            if match['date'] not in spec['dates']: continue
            key=(match['date'],spec['holes'],match['course_id'])
            if key not in raw: continue
            row=course_result(catalog.courses[key[2]],raw[key],make_snapshot(key[0],str(key[1]),[raw[key]]),
                spec['players'],spec['from_minutes'],spec['to_minutes'],clock)
            available=valid_matches(row,key[0],clock)
            if available is not None and any(slot_key(t)==slot_key(match) for t in available): valid.append(match)
        if not valid:
            event.reference.delete(); continue
        # Final read closes the large collection/sending gap when an alert was paused.
        latest=doc.reference.get()
        if not latest.exists or generation(latest.to_dict())!=value['generation']:
            event.reference.delete(); continue
        done = sorted_dates(read_acknowledgements(doc))
        valid = [m for m in valid if m['date'] not in done]
        if not valid:
            event.reference.delete(); continue
        if quiet_now(spec,now()): continue
        first=valid[0]
        title=f"{len(valid)} matching tee {'time' if len(valid)==1 else 'times'} available"
        body=f"{first['course_name']} · {first['date']} · {first['time']} · {spec['players']} players. Check before booking."
        data={'event_id':event.id,'watch_id':doc.id,'date':first['date'],'course_id':first['course_id']}
        save_notification(doc.reference.parent.parent, event.id, title, body, data, value['created_at'])
        devices=[d for d in doc.reference.parent.parent.collection('devices').stream() if d.to_dict().get('enabled')]
        accepted=set(value.get('accepted_devices',[]))
        for device in devices:
            if device.id in accepted: continue
            if first['date'] in sorted_dates(read_acknowledgements(doc)):
                event.reference.delete(); break
            ttl=delivery_ttl(spec,now())
            if ttl <= 0: break
            count=send([device],title=title, body=body, data=data,tag=event.id,ttl_seconds=ttl)
            if count:
                accepted.add(device.id)
                event.reference.update({'accepted_devices':sorted(accepted)})
        if all(d.id in accepted for d in devices): event.reference.delete()


def check_availability(db):
    catalog=Catalog(); watches=[]; per_user={}
    for doc in db.collection_group('watches').limit(101).stream():
        if len(doc.reference.path.split('/'))!=4 or not doc.reference.path.startswith('users/'): continue
        user=doc.reference.parent.parent.path
        per_user[user]=per_user.get(user,0)+1
        if per_user[user]>10: continue
        try:
            spec=validate_watch(doc.to_dict(),catalog,now())
            spec['dates'] = pending_rounds(spec, read_acknowledgements(doc))
            # Contact-only / website-only venues cannot supply observed times.
            spec['course_ids'] = [cid for cid in spec['course_ids'] if catalog.courses[cid]['provider'] != 'direct']
            if spec['dates'] and spec['course_ids']: watches.append((doc,spec))
            else:
                doc.reference.parent.parent.collection('watchStatus').document(doc.id).set({
                    'last_checked_at': now(), 'fresh_courses': 0, 'total_course_dates': 0,
                    'state': 'contact_only' if not spec['course_ids'] else
                             'waiting_next_round' if 'recurrence' in spec else 'sorted'})
        except (ValueError,TypeError,KeyError):
            logging.warning('An invalid or disabled watch was skipped.')
    if len(watches)>100: raise RuntimeError('Private test watch limit reached')
    raw=collect([spec for _,spec in watches],catalog)
    for doc,spec in watches: evaluate(db,doc,spec,raw,catalog)
    deliver(db,raw,catalog)
    print(f'Checked {len(watches)} watches using {len(raw)} shared course/date observations.')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--tests-only',action='store_true')
    args=parser.parse_args()
    firebase_admin.initialize_app(options={'projectId':PROJECT})
    db=firestore.client()
    phone_tests(db)
    if args.tests_only: return
    owner=acquire(db)
    if owner is None:
        print('Availability scan skipped: another scan is active or just completed.')
        return
    success=False
    try:
        check_availability(db)
        success=True
    finally:
        finish(db,owner,success)


if __name__=='__main__': main()
