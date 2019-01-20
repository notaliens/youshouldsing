Prep
----

On Ubuntu 18.04:

sudo apt install build-essential timidity lame sox libsox-fmt-mp3 ffmpeg \
   redis-server supervisor fluid-soundfont-gm fluid-soundfont-gs npm \
   libopusfile-dev libopencore-amrnb-dev libopencore-amrwb-dev libao-dev \
   libflac-dev libmp3lame-dev libtwolame-dev libltdl-dev libmad0-dev \
   libid3tag0-dev libvorbis-dev libpng-dev libsndfile1-dev libwavpack-dev \
   libpulse-dev libclalsadrv-dev libasound2-dev opus-tools sqlite3 python-dev \
   tap-plugins vlevel rev-plugins

# XXX grr... some conflict between npm wanting libssl1-dev and another
# lib wanting libssl-dev and they are mutually exclusive.

Note that all of the libXXX-dev things must be installed to support a
custom-compiled version of sox that gets put into parts/sox (the one that ships
with Ubuntu doesn't have opus support).

sudo touch /usr/include/gnu-crypt.h (see
https://bitbucket.org/dholth/cryptacular/issues/11/not-installing-on-ubuntu-1804
this is a total hack workaround)

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

Add $BUILDOUTROOT/parts/sox/bin to the $PATH of the user who is running the
server; this version of sox must be used, not the one installed globally
(the globally installed one lacks ogg-opus support).

Alternately, download sox 14.4.2 source tarball and install it via configure;
make; make install (it will go into /usr/local, and that will precede the
Ubuntu packaged one).  HOWEVER, I tried this over and over again, and for
whatever reason, trying to install this into the default /usr/local prevents
opus support.  Installing it literally anywhere else works, so use --prefix e.g
configure --prefix=/opt/sox-14.4.2-withopus and add /opt/sox-14.4.2-withopus to
the PATH of the user who will run the yss processes.

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

