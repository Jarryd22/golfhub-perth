import json,sys,os,tempfile,hashlib
from pathlib import Path
from unittest.mock import patch
root=Path(sys.argv[1]);sys.path[:0]=[str(root),str(root/'tests')]
with tempfile.TemporaryDirectory(prefix='golfhub-grid-edge-review-') as runtime:
 os.environ.update(QT_QPA_PLATFORM='offscreen',LOCALAPPDATA=runtime,TEMP=runtime,TMP=runtime)
 from PySide6.QtWidgets import QApplication,QWidget
 from app.qt_golfhub_app import ResponsiveCardGrid
 from tests.qt_test_support import cleanup_qt_widgets
 app=QApplication.instance() or QApplication([])
 out=[]
 with patch('socket.create_connection',side_effect=AssertionError('Offline review')),patch('socket.socket.connect',side_effect=AssertionError('Offline review')),patch('webbrowser.open',side_effect=AssertionError('Offline review')):
  for maximum in (1,2,3):
   for count in (0,1,2,3):
    grid=ResponsiveCardGrid([QWidget() for _ in range(count)],min_cell_width=250,max_columns=maximum)
    for width in (500,1200,683,500):
     grid.setFixedSize(width,1000);grid.show()
     for _ in range(3):app.processEvents();grid.grid.activate()
     out.append({'max_columns':maximum,'count':count,'width':width,'layout_columns':grid.grid.columnCount(),'stretches':[grid.grid.columnStretch(i) for i in range(grid.grid.columnCount())],'cards':[[w.x(),w.width()] for w in grid.widgets]})
    cleanup_qt_widgets()
 print(json.dumps({'root':str(root),'app_sha256':hashlib.sha256((root/'app/qt_golfhub_app.py').read_bytes()).hexdigest(),'cases':out},indent=2))
