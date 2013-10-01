.PHONY: build

build: bin/buildout
	bin/buildout

bin/buildout:
	virtualenv -ppython2.7 .
	bin/python bootstrap.py

clean:
	rm -rf bin/ include/ lib/ .installed.cfg .mr.developer.cfg develop-eggs/ eggs/ var/ downloads/ parts/ tmp/ lib/python2.7/site-packages/pygame*
	find src/ -maxdepth 1 -mindepth 1 -type d|grep -v yss|xargs rm -rf
