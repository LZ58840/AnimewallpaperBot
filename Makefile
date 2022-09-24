.PHONY: run_docker setup_docker clean

run_docker:
	deployment/start-docker.sh

setup_docker: run_docker
setup_docker:
	deployment/setup-sql.sh

clean:
	deployment/stop-docker.sh