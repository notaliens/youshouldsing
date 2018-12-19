Prep
----

On Ubuntu 12.04:

sudo apt-get install timidity lame sox
sudo apt-get install redis-server
cd /usr/include/linux
sudo ln -s ../libv4l1-videodev.h videodev.h


Installation
------------

Run ``make`` in this directory.  It will create a virtualenv, run bootstrap.py,
and then run the buildout.

Starting Over
-------------

``make clean`` will blow away: bin/ include/ lib/ .installed.cfg
.mr.developer.cfg develop-eggs/ eggs/ var/ downloads/ parts/ tmp/ share/

Don't do this if you have data in var/ you want to keep.

Running
-------

``bin/supervisord`` will start up the app on 6549.

Note that ``pserve`` will also work but you'll have to do::

  export LD_LIBRARY_PATH=$buildoutdir/parts/wxpython-cmmi/lib

Before executing it.
