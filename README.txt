Prep
----

On Ubuntu 18.04:

sudo apt install build-essential timidity lame sox libsox-fmt-mp3 ffmpeg \
   redis-server supervisor fluid-soundfont-gm fluid-soundfont-gs npm

sudo touch /usr/include/gnu-crypt.h (see
https://bitbucket.org/dholth/cryptacular/issues/11/not-installing-on-ubuntu-1804
this is a ttotal hack workaround)

To get all instruments mapped during song import, edit
/etc/timidity/timidity.cfg and change:

  source /etc/timidity/freepats.cfg

To:

  source /etc/timidity/fluidr3_gm.cfg
  source /etc/timidity/fluidr3_gs.cfg

And sudo service timidity restart.

To install less so you can recompile yss.less to yss.css, etc:

  sudo npm install -g less jshint recess uglify-js

Then lessc yss.less to gen output.

You will need Python 3.7 somehow.  It doesn't ship with 18.04.  I used
https://github.com/pyenv/pyenv.

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

