"""Atomically update the feed branch. Never writes an app release or manifest."""
import base64, json, subprocess, sys
from pathlib import Path
REPO='repos/Jarryd22/golfhub-perth'
def api(path, method='GET', payload=None):
    args=['gh','api',REPO+'/'+path,'--method',method]
    raw=None
    if payload is not None:
        args+=['--input','-'];raw=json.dumps(payload).encode()
    return json.loads(subprocess.check_output(args,input=raw))
if __name__=='__main__':
    path=Path(sys.argv[1]);raw=path.read_bytes();data=json.loads(raw)
    assert data['schema']==1 and len(raw)<600000 and len(data['items'])<=200
    head=api('git/ref/heads/news')['object']['sha']
    base=api('git/commits/'+head)
    blob=api('git/blobs','POST',dict(content=base64.b64encode(raw).decode(),encoding='base64'))
    tree=api('git/trees','POST',dict(base_tree=base['tree']['sha'],tree=[dict(path='public/news.json',mode='100644',type='blob',sha=blob['sha'])]))
    commit=api('git/commits','POST',dict(message='Refresh dated official course news',tree=tree['sha'],parents=[head]))
    api('git/refs/heads/news','PATCH',dict(sha=commit['sha'],force=False))
    print('Published',len(data['items']),'official announcements')
