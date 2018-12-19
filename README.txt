Prep
----

On Ubuntu 18.04:

sudo apt-get install timidity lame sox libsox-fmt-mp3 redis-server supervisor

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

``supervisord -c etc/supervisord.conf`` will start up the app on 6549.

