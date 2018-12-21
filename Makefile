.PHONY: build

build: bin/buildout
	bin/buildout

bin/buildout:
	virtualenv -ppython3.7 .
	bin/pip install -U setuptools
	bin/python bootstrap.py

clean:
	rm -rf bin/ include/ lib/ .installed.cfg .mr.developer.cfg develop-eggs/ eggs/ downloads/ parts/ tmp/

pristine: clean
	rm -rf var/

start:
	supervisord -c etc/supervisord.conf

stop:
	supervisorctl -c etc/supervisord.conf shutdown

restart: stop start

status:
	supervisorctl -c etc/supervisord.conf status

devtunnel:
	ssh -f -N -T -R 0.0.0.0:6549:127.0.0.1:6549 bouncer.repoze.org

