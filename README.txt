Prep
----

On Ubuntu 12.04:

sudo apt-get build-dep libwxgtk2.8-0
sudo apt-get build-dep python-pygame
sudo apt-get install
sudo apt-get install python-wxgtk2.8
sudo apt-get install libwxgtk2.8-dev
sudo apt-get install libsdl1.2-dev
sudo apt-get install libv4l-dev
cd /usr/include/linux
sudo ln -s ../libv4l1-videodev.h videodev.h

Installation
------------

Run ``make`` in this directory.  It will create a virtualenv, run bootstrap.py,
and then run the buildout.

Starting Over
-------------

``make clean`` will blow away: bin/ include/ lib/ .installed.cfg
.mr.developer.cfg develop-eggs/ eggs/ var/ downloads/ parts/ tmp/ src/wxpython
share/

Don't do this if you have data in var/ you want to keep.

Testing
-------

``make karaoke-gui`` should show the PyKaraoke GUI.

Running
-------

``bin/supervisord`` will start up the app on 6549.

Note that ``pserve`` will also work but you'll have to do::

  export LD_LIBRARY_PATH=$buildoutdir/parts/wxpython-cmmi/lib

Before executing it.
