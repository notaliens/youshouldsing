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
.mr.developer.cfg develop-eggs/ eggs/ var/ downloads/ parts/ tmp/

``make pristine`` does what ``make clean`` does plus it blows away the var/
directory (which contains database files which include any songs, recordings,
etc that you've created).

Running
-------

``make start`` will start up the app.  It will be accessible on http port 6549.

``make stop`` will stop the app.

``make status`` will show the current running status of the processes that
compose the app.

