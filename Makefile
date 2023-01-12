.PHONY: start setup stop restart clean reset integ start_dc stop_dc update_git update

start:
	./deployments/start-prod.sh

setup: start
setup:
	./deployments/setup-sql.sh

stop:
	./deployments/stop-prod.sh

restart: stop
restart: start

clean: stop
clean:
	./deployments/clear-data.sh

reset: clean
reset: setup

start_dc:
	./deployments/start-deps.sh
	./deployments/setup-sql.sh

integ:
	# NOTE: Verify the installed Python in your environment before testing!
	python -m unittest discover tests.integration -v --locals

stop_dc:
	./deployments/stop-deps.sh

update_git:
	git pull

update: update_git
update: restart
