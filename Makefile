.PHONY: build

build:
	virtualenv -ppython2.7 .
	bin/pip install --upgrade setuptools
	bin/python bootstrap.py
	bin/buildout

clean:
	rm -rf bin/ include/ lib/ .installed.cfg .mr.developer.cfg develop-eggs/ eggs/ var/ downloads/ parts/ tmp/ src/wxpython/ src/substanced/ src/deform/ src/pygame share/

karaoke-gui:
	export LD_LIBRARY_PATH=parts/wxpython-cmmi/lib
	bin/py lib/python2.7/site-packages/pykaraoke.py


