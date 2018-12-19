.PHONY: build

build: bin/buildout
	bin/buildout

bin/buildout:
	virtualenv -ppython3.7 .
	bin/pip install -U setuptools
	bin/python bootstrap.py

clean:
	rm -rf bin/ include/ lib/ .installed.cfg .mr.developer.cfg develop-eggs/ eggs/ var/ downloads/ parts/ tmp/
	find src/ -maxdepth 1 -mindepth 1 -type d|grep -v yss|xargs rm -rf
